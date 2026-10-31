"""GitHub webhook: a closed issue becomes a draft solution."""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from ...agent.drafting import draft_from_issue
from ...integrations.github import get_github, verify_signature
from ..config import settings
from ..db import get_db
from ..models import Event, Ticket

log = logging.getLogger(__name__)
router = APIRouter(tags=["webhooks"])


@router.post("/webhooks/github")
async def github_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_hub_signature_256: str | None = Header(None),
    x_github_event: str | None = Header(None),
):
    body = await request.body()
    if settings.github_enabled and not verify_signature(
        settings.github_webhook_secret, body, x_hub_signature_256
    ):
        raise HTTPException(401, "bad signature")

    payload = json.loads(body or b"{}")
    event = x_github_event or payload.get("_event") or "issues"
    action = payload.get("action")

    closed_issue = event == "issues" and action == "closed"
    merged_pr = (
        event == "pull_request" and action == "closed" and (payload.get("pull_request") or {}).get("merged")
    )
    if not (closed_issue or merged_pr):
        return {"ignored": True, "event": event, "action": action}

    number = _issue_number(payload, merged_pr)
    if number is None:
        return {"ignored": True, "reason": "no linked issue"}

    # Not one_or_none: a pre-existing duplicate row must not 500 the webhook.
    ticket = (
        db.query(Ticket)
        .filter(Ticket.github_issue_number == number)
        .order_by(Ticket.created_at.desc())
        .first()
    )
    if ticket is None:
        log.info("webhook for issue #%s which LoopDesk did not create", number)
        return {"ignored": True, "reason": "unknown ticket"}
    if ticket.status == "resolved":
        return {"ok": True, "already_resolved": True, "solution_id": ticket.linked_solution_id}

    gh = get_github()
    try:
        issue = gh.get_issue(number) if gh.enabled else {}
    except Exception as exc:  # noqa: BLE001
        log.warning("could not fetch issue #%s (%s); drafting from the stored body", number, exc)
        issue = {}
    issue.setdefault("title", ticket.title)
    issue.setdefault("body", ticket.body)
    if merged_pr:
        pr = payload.get("pull_request") or {}
        issue["fix_summary"] = f"{pr.get('title', '')}\n\n{pr.get('body', '') or ''}"

    solution = draft_from_issue(db, ticket, issue)
    db.add(Event(kind="draft_created", payload={"issue": number, "solution": solution.id}))
    db.commit()
    log.info("drafted solution %s from issue #%s", solution.id, number)
    return {"ok": True, "solution_id": solution.id, "status": "draft"}


def _issue_number(payload: dict, merged_pr: bool) -> int | None:
    if not merged_pr:
        return (payload.get("issue") or {}).get("number")
    pr = payload.get("pull_request") or {}
    # "Fixes #123" in the PR body is the common way a PR closes an issue.
    import re

    m = re.search(r"(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#(\d+)", pr.get("body") or "", re.I)
    return int(m.group(1)) if m else None
