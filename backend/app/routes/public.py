"""Everything the widget calls."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ...agent import retrieval
from ...agent.pipeline import analyze as run_agent
from ...agent.providers import get_provider
from ...integrations.github import get_github, routing_for
from ...integrations.storage import save_screenshot
from ..config import settings
from ..db import get_db
from ..models import Event, Rating, Report, Solution, Ticket
from ..schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    RateRequest,
    SolutionCard,
    TicketRequest,
    TicketResponse,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["widget"])


@router.get("/suggestions", response_model=list[SolutionCard])
def suggestions(
    route: str = Query("/"),
    subproduct: str | None = Query(None),
    version: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """Layer 1: known solutions for this page, shown before any screenshot."""
    hits = retrieval.page_suggestions(db, route, subproduct, version)
    db.add(Event(kind="suggestions", payload={"route": route, "count": len(hits)}))
    db.commit()
    return [
        SolutionCard(
            id=s.id,
            title=s.title,
            summary=s.summary,
            steps_md=s.steps_md,
            subproduct=s.subproduct,
            relevance=1.0,
            why="Known issue on this page.",
            score=round(retrieval.quality_weight(s), 2),
            source=s.source,
            source_issue_number=s.source_issue_number,
        )
        for s in hits
    ]


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest, db: Session = Depends(get_db)):
    """Layer 2: the agent. Screenshot + metadata + KB -> a cited answer."""
    screenshot_url = save_screenshot(req.screenshot)
    return run_agent(db, req, screenshot_url)


@router.post("/rate")
def rate(req: RateRequest, db: Session = Depends(get_db)):
    report = db.get(Report, req.report_id)
    if not report:
        raise HTTPException(404, "unknown report")

    rating = Rating(report_id=report.id, solution_id=req.solution_id, helpful=req.helpful)
    db.add(rating)

    if req.solution_id:
        sol = db.get(Solution, req.solution_id)
        if sol:
            if req.helpful:
                sol.helpful_count += 1
            else:
                sol.unhelpful_count += 1
    db.add(Event(kind="rate", payload={"helpful": req.helpful}))
    db.commit()
    return {"ok": True}


@router.post("/tickets", response_model=TicketResponse)
def create_ticket(req: TicketRequest, db: Session = Depends(get_db)):
    gh = get_github()

    # "Me too" on an existing issue instead of opening a duplicate.
    if req.me_too_issue_number:
        existing = (
            db.query(Ticket)
            .filter(Ticket.github_issue_number == req.me_too_issue_number)
            .one_or_none()
        )
        try:
            gh.comment(
                req.me_too_issue_number,
                "Another user hit this from LoopDesk (+1). "
                f"Route `{req.subproduct}`, reported via the in-app widget.",
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("me-too comment failed: %s", exc)
        _mark_ticket_after_helpful(db, req.report_id)
        db.add(Event(kind="me_too", payload={"issue": req.me_too_issue_number}))
        db.commit()
        return TicketResponse(
            id=existing.id if existing else "",
            github_issue_number=req.me_too_issue_number,
            github_url=existing.github_url if existing else None,
            dry_run=not gh.enabled,
            me_too=True,
        )

    labels, assignees = routing_for(req.subproduct)
    try:
        issue = gh.create_issue(req.title, req.description, labels, assignees)
    except Exception as exc:  # noqa: BLE001 - never lose the user's report
        log.error("GitHub issue creation failed: %s", exc)
        issue = {"number": None, "html_url": None, "dry_run": True}

    if issue.get("dry_run"):
        issue["number"] = _next_dry_run_number(db)
        repo = settings.github_repo or "example/loopdesk-demo-tickets"
        issue["html_url"] = f"https://github.com/{repo}/issues/{issue['number']}"

    embedding = None
    report = db.get(Report, req.report_id) if req.report_id else None
    if report is not None:
        embedding = report.embedding
    if embedding is None:
        try:
            embedding = get_provider().embed(f"{req.title}\n{req.description}")
        except Exception:  # noqa: BLE001
            embedding = None

    ticket = Ticket(
        report_id=req.report_id,
        github_issue_number=issue.get("number"),
        github_url=issue.get("html_url"),
        title=req.title,
        body=req.description,
        subproduct=req.subproduct,
        status="open",
        dry_run=bool(issue.get("dry_run")),
        embedding=embedding,
    )
    db.add(ticket)
    _mark_ticket_after_helpful(db, req.report_id)
    db.add(Event(kind="ticket", payload={"subproduct": req.subproduct}))
    db.commit()

    return TicketResponse(
        id=ticket.id,
        github_issue_number=ticket.github_issue_number,
        github_url=ticket.github_url,
        dry_run=ticket.dry_run,
    )


def _next_dry_run_number(db: Session) -> int:
    """Dry-run mode still needs stable, unique issue numbers."""
    current = db.query(func.max(Ticket.github_issue_number)).scalar() or 1000
    return int(current) + 1


def _mark_ticket_after_helpful(db: Session, report_id: str | None) -> None:
    """A user who called a solution helpful and raised a ticket anyway is the
    strongest signal that the solution is wrong. Count it against it."""
    if not report_id:
        return
    for rating in db.query(Rating).filter(Rating.report_id == report_id, Rating.helpful.is_(True)):
        rating.raised_ticket = True
        if rating.solution_id:
            sol = db.get(Solution, rating.solution_id)
            if sol:
                sol.ticket_after_count += 1


@router.get("/reports/mine")
def my_reports(session_id: str = Query(...), db: Session = Depends(get_db)):
    """The widget's 'My reports' tab: closes the loop for the reporter."""
    reports = (
        db.query(Report)
        .filter(Report.session_id == session_id)
        .order_by(Report.created_at.desc())
        .limit(20)
        .all()
    )
    out = []
    for r in reports:
        ticket = db.query(Ticket).filter(Ticket.report_id == r.id).one_or_none()
        fixed_in = None
        if ticket and ticket.linked_solution_id:
            sol = db.get(Solution, ticket.linked_solution_id)
            if sol and sol.status == "published":
                fixed_in = {"title": sol.title, "version": sol.applies_from, "id": sol.id}
        out.append(
            {
                "report_id": r.id,
                "comment": r.comment,
                "route": (r.context or {}).get("route"),
                "created_at": r.created_at.isoformat(),
                "ticket": (
                    {
                        "number": ticket.github_issue_number,
                        "url": ticket.github_url,
                        "status": ticket.status,
                    }
                    if ticket
                    else None
                ),
                "fixed_in": fixed_in,
            }
        )
    return out
