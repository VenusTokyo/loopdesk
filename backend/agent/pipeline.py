"""The agent pipeline behind POST /api/analyze.

store -> retrieve (layer 1 + layer 2) -> diagnose (vision) -> confidence gate
-> duplicate check. Each step degrades to something useful rather than failing.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from ..app.config import settings
from ..app.models import Event, Report, Solution, Ticket
from ..app.schemas import AnalyzeRequest, AnalyzeResponse, SolutionCard
from . import retrieval
from .prompts import load as load_prompt
from .providers import get_provider
from .schema import DIAGNOSE_SCHEMA, SchemaError, validate_diagnosis

log = logging.getLogger(__name__)

UNKNOWN_MESSAGE = (
    "I could not find a known fix for this. Raising a ticket sends your "
    "screenshot and the page details straight to the team."
)
MAYBE_MESSAGE = "This might help. If it does not, raise a ticket and we will pick it up."
CONFIDENT_MESSAGE = "Here is the known fix for this."


def analyze(db: Session, req: AnalyzeRequest, screenshot_url: str | None) -> AnalyzeResponse:
    ctx = req.context
    provider = get_provider()

    query = retrieval.build_query(req.comment, ctx)
    try:
        query_embedding = provider.embed(query) if query.strip() else []
    except Exception as exc:  # noqa: BLE001
        log.warning("embedding failed (%s); continuing with page suggestions only", exc)
        query_embedding = []

    report = Report(
        session_id=ctx.session_id,
        screenshot_url=screenshot_url,
        comment=req.comment,
        context=ctx.model_dump(),
        embedding=query_embedding or None,
    )
    db.add(report)
    db.flush()

    page = retrieval.page_suggestions(db, ctx.route, ctx.subproduct, ctx.app_version)
    semantic = (
        retrieval.semantic_candidates(
            db, query_embedding, ctx.route, ctx.subproduct, ctx.app_version
        )
        if query_embedding
        else []
    )
    candidates = retrieval.merge_candidates(page, semantic)
    by_id: dict[str, Solution] = {s.id: s for s, _ in candidates}

    result = _diagnose(provider, req, candidates, set(by_id))

    verdict, message = _gate(result["confidence"], bool(result["matches"]))
    needs_ticket = result["needs_ticket"] or verdict != "confident"
    if result["intent"] != "bug":
        needs_ticket = result["intent"] == "feature_request"

    cards: list[SolutionCard] = []
    for m in result["matches"]:
        sol = by_id.get(m["solution_id"])
        if not sol:
            continue
        cards.append(
            SolutionCard(
                id=sol.id,
                title=sol.title,
                summary=sol.summary,
                steps_md=sol.steps_md,
                subproduct=sol.subproduct,
                relevance=m["relevance"],
                why=m["why"],
                score=round(retrieval.quality_weight(sol), 2),
                source=sol.source,
                source_issue_number=sol.source_issue_number,
            )
        )
    if verdict == "unknown":
        cards = []

    duplicate = _duplicate_ticket(db, query_embedding, ctx.subproduct) if needs_ticket else None

    report.intent = result["intent"]
    report.agent_result = {**result, "verdict": verdict, "provider": provider.name}
    db.add(Event(kind="analyze", payload={"verdict": verdict, "subproduct": ctx.subproduct}))
    db.commit()

    return AnalyzeResponse(
        report_id=report.id,
        intent=result["intent"],
        diagnosis=result["diagnosis"],
        confidence=round(result["confidence"], 2),
        verdict=verdict,
        message=message,
        solutions=cards,
        needs_ticket=needs_ticket,
        suggested_title=result["suggested_title"] or "Issue reported from the app",
        suggested_description=_ticket_body(req, result),
        likely_area=result["likely_area"],
        duplicate_of=duplicate,
        screenshot_url=screenshot_url,
        provider=provider.name,
    )


def _diagnose(
    provider, req: AnalyzeRequest, candidates: list[tuple[Solution, float]], allowed: set[str]
) -> dict[str, Any]:
    system = load_prompt("diagnose.system.md")
    user = _render_user_prompt(req, candidates)

    last_error: Exception | None = None
    for attempt in (1, 2):  # one retry, then the honest fallback
        try:
            raw = provider.vision_json(system, user, req.screenshot, DIAGNOSE_SCHEMA)
            return validate_diagnosis(raw, allowed)
        except (SchemaError, ValueError, KeyError) as exc:
            last_error = exc
            log.warning("diagnose attempt %s returned unusable output: %s", attempt, exc)
        except Exception as exc:  # noqa: BLE001 - network, auth, rate limit
            last_error = exc
            log.warning("diagnose attempt %s failed: %s", attempt, exc)
            break

    log.error("diagnose unavailable (%s); falling back to the ticket path", last_error)
    return {
        "intent": "bug",
        "diagnosis": "I could not analyse this automatically.",
        "matches": [],
        "confidence": 0.0,
        "needs_ticket": True,
        "suggested_title": (req.comment or "Issue reported from the app").splitlines()[0][:70],
        "suggested_description": req.comment or "",
        "likely_area": req.context.route,
    }


def _render_user_prompt(req: AnalyzeRequest, candidates: list[tuple[Solution, float]]) -> str:
    ctx = req.context
    errors = "\n".join(f"- {e}" for e in ctx.console_errors[:5]) or "- none"
    requests = (
        "\n".join(f"- {r.method} {r.url} -> {r.status}" for r in ctx.failed_requests[:5]) or "- none"
    )
    cands = (
        "\n".join(f"[{s.id}] {s.title}: {s.summary}" for s, _ in candidates)
        or "(none retrieved - the knowledge base has nothing for this page)"
    )
    return f"""USER REPORT:
{req.comment or "(no comment given)"}

ROUTE: {ctx.route}
SUBPRODUCT: {ctx.subproduct}
APP VERSION: {ctx.app_version}
USER ROLE: {ctx.user_role}
PAGE TITLE: {ctx.page_title}
BROWSER: {ctx.browser} viewport {ctx.viewport}

CONSOLE ERRORS:
{errors}

FAILED REQUESTS:
{requests}

CANDIDATE SOLUTIONS:
{cands}
"""


def _gate(confidence: float, has_match: bool) -> tuple[str, str]:
    if confidence >= settings.confidence_high and has_match:
        return "confident", CONFIDENT_MESSAGE
    if confidence >= settings.confidence_low and has_match:
        return "maybe", MAYBE_MESSAGE
    return "unknown", UNKNOWN_MESSAGE


def _duplicate_ticket(
    db: Session, query_embedding: list[float], subproduct: str
) -> dict[str, Any] | None:
    """Before we offer a new ticket, check whether one is already open."""
    if not query_embedding:
        return None
    open_tickets = (
        db.query(Ticket).filter(Ticket.status == "open", Ticket.subproduct == subproduct).all()
    )
    best, best_sim = None, 0.0
    for t in open_tickets:
        sim = retrieval.cosine(query_embedding, t.embedding)
        if sim > best_sim:
            best, best_sim = t, sim
    if best is None or best_sim < 0.62:
        return None
    return {
        "ticket_id": best.id,
        "issue_number": best.github_issue_number,
        "url": best.github_url,
        "title": best.title,
        "similarity": round(best_sim, 2),
    }


def _ticket_body(req: AnalyzeRequest, result: dict[str, Any]) -> str:
    ctx = req.context
    errors = "\n".join(f"- `{e}`" for e in ctx.console_errors[:5]) or "- none"
    requests = (
        "\n".join(f"- `{r.method} {r.url}` -> **{r.status}**" for r in ctx.failed_requests[:5])
        or "- none"
    )
    user_said = req.comment.strip() or "(no comment given)"
    described = result["suggested_description"].strip()
    extra = described if described and described != user_said else ""
    return f"""**What the user reported**

{user_said}

**Agent diagnosis**

{result["diagnosis"]}

{extra}

| | |
|---|---|
| Route | `{ctx.route}` |
| Sub-product | `{ctx.subproduct}` |
| App version | `{ctx.app_version}` |
| User role | `{ctx.user_role}` |
| Browser | {ctx.browser} |
| Viewport | {ctx.viewport} |
| Likely area | {result["likely_area"] or "unknown"} |

**Console errors**

{errors}

**Failed requests**

{requests}
""".strip()
