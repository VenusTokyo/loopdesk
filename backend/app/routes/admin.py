"""Admin API: review AI drafts, approve, publish, commit to the repo."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from ...agent.providers import get_provider
from ...integrations.github import (
    get_github,
    local_solution_file,
    solution_markdown,
    solution_path,
)
from ..config import settings
from ..db import get_db
from ..models import Event, Rating, Report, Solution, Ticket
from ..schemas import DraftApproval

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])


def require_admin(x_admin_token: str | None = Header(None)) -> None:
    if x_admin_token != settings.admin_token:
        raise HTTPException(401, "admin token required")


@router.get("/drafts", dependencies=[Depends(require_admin)])
def drafts(db: Session = Depends(get_db)):
    rows = (
        db.query(Solution)
        .filter(Solution.status == "draft")
        .order_by(Solution.created_at.desc())
        .all()
    )
    return [_as_dict(s) for s in rows]


@router.get("/solutions", dependencies=[Depends(require_admin)])
def all_solutions(db: Session = Depends(get_db)):
    rows = db.query(Solution).order_by(Solution.status, Solution.subproduct).all()
    return [_as_dict(s) for s in rows]


@router.post("/approve", dependencies=[Depends(require_admin)])
def approve(req: DraftApproval, db: Session = Depends(get_db)):
    sol = db.get(Solution, req.solution_id)
    if not sol:
        raise HTTPException(404, "unknown solution")

    # The dev can edit the AI draft before it goes live.
    if req.title:
        sol.title = req.title
    if req.summary is not None:
        sol.summary = req.summary
    if req.steps_md is not None:
        sol.steps_md = req.steps_md

    sol.status = "published"
    try:
        sol.embedding = get_provider().embed(_embed_text(db, sol))
    except Exception as exc:  # noqa: BLE001
        log.warning("embedding the published solution failed: %s", exc)

    path = solution_path(sol)
    markdown = solution_markdown(sol)
    committed: dict | None = None
    try:
        gh = get_github()
        committed = gh.put_file(
            path, markdown, f"docs(solutions): publish fix for #{sol.source_issue_number or 'manual'}"
        )
    except Exception as exc:  # noqa: BLE001
        log.error("commit failed (%s); writing the file locally", exc)
    if committed is None or committed.get("dry_run"):
        local = local_solution_file(sol)
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_text(markdown, encoding="utf-8")

    db.add(Event(kind="published", payload={"solution": sol.id, "path": path}))
    db.commit()
    return {"ok": True, "solution": _as_dict(sol), "path": path, "committed": bool(committed)}


@router.post("/reject", dependencies=[Depends(require_admin)])
def reject(req: DraftApproval, db: Session = Depends(get_db)):
    sol = db.get(Solution, req.solution_id)
    if not sol:
        raise HTTPException(404, "unknown solution")
    sol.status = "deprecated"
    db.add(Event(kind="rejected", payload={"solution": sol.id}))
    db.commit()
    return {"ok": True}


@router.get("/stats", dependencies=[Depends(require_admin)])
def stats(db: Session = Depends(get_db)):
    reports = db.query(Report).count()
    tickets = db.query(Ticket).count()
    helpful = db.query(Rating).filter(Rating.helpful.is_(True)).count()
    published = db.query(Solution).filter(Solution.status == "published").count()
    drafts_n = db.query(Solution).filter(Solution.status == "draft").count()
    deflected = max(reports - tickets, 0)
    return {
        "reports": reports,
        "tickets": tickets,
        "deflected": deflected,
        "deflection_rate": round(deflected / reports, 2) if reports else 0.0,
        "helpful_ratings": helpful,
        "published_solutions": published,
        "draft_solutions": drafts_n,
    }


@router.get("/tickets", dependencies=[Depends(require_admin)])
def tickets(db: Session = Depends(get_db)):
    rows = db.query(Ticket).order_by(Ticket.created_at.desc()).limit(50).all()
    return [
        {
            "id": t.id,
            "number": t.github_issue_number,
            "url": t.github_url,
            "title": t.title,
            "subproduct": t.subproduct,
            "status": t.status,
            "dry_run": t.dry_run,
            "linked_solution_id": t.linked_solution_id,
        }
        for t in rows
    ]


def _embed_text(db: Session, sol: Solution) -> str:
    """What the solution is indexed by.

    A published fix is written in the team's words ("date range resets"),
    while the next user reports it in theirs ("the filter will not stay on 30
    days"). Folding the originating ticket into the embedding - without
    showing it to users - is what makes the second report match the first.
    """
    text = f"{sol.title}\n{sol.summary}\n{sol.steps_md}"
    if sol.source_issue_number:
        ticket = (
            db.query(Ticket)
            .filter(Ticket.github_issue_number == sol.source_issue_number)
            .order_by(Ticket.created_at.desc())
            .first()
        )
        if ticket:
            text += f"\n{ticket.title}\n{ticket.body}"
    return text


def _as_dict(s: Solution) -> dict:
    return {
        "id": s.id,
        "title": s.title,
        "summary": s.summary,
        "steps_md": s.steps_md,
        "subproduct": s.subproduct,
        "route_patterns": s.route_patterns,
        "applies_from": s.applies_from,
        "applies_to": s.applies_to,
        "status": s.status,
        "source": s.source,
        "source_issue_number": s.source_issue_number,
        "helpful_count": s.helpful_count,
        "unhelpful_count": s.unhelpful_count,
        "ticket_after_count": s.ticket_after_count,
        "created_at": s.created_at.isoformat(),
    }
