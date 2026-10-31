"""Turn a closed GitHub issue into a draft knowledge-base solution.

This is the half of the loop that makes the knowledge base grow by itself:
the dev closes a ticket, the agent writes the user-facing version, a human
approves it, and the next user with the same problem gets it instantly.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from sqlalchemy.orm import Session

from ..app.models import Solution, Ticket
from .prompts import load as load_prompt
from .providers import get_provider

log = logging.getLogger(__name__)

DRAFT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["title", "summary", "steps_md"],
    "properties": {
        "title": {"type": "string"},
        "summary": {"type": "string"},
        "steps_md": {"type": "string"},
        "subproduct": {"type": "string"},
        "applies_from": {"type": ["string", "null"]},
        "applies_to": {"type": ["string", "null"]},
    },
}

# Lines that must never reach a user-facing KB entry.
_NOISE = re.compile(
    r"""(^\s*(at\s+[\w$.<>]+\(|File\s+"|Traceback|\s{2,}at\s)|
         [A-Za-z]:\\[^\s]+|/(?:home|usr|var|opt|src)/[^\s]+)""",
    re.X | re.M,
)


def strip_internals(text: str) -> str:
    kept = [ln for ln in (text or "").splitlines() if not _NOISE.search(ln)]
    return "\n".join(kept).strip()


def draft_from_issue(db: Session, ticket: Ticket, issue: dict[str, Any]) -> Solution:
    provider = get_provider()
    body = strip_internals(issue.get("body") or ticket.body)
    comments = "\n\n".join(
        strip_internals(c.get("body", "")) for c in (issue.get("comments_list") or [])
    )[:6000]

    user_prompt = f"""ISSUE TITLE: {issue.get("title") or ticket.title}
ISSUE NUMBER: {ticket.github_issue_number}
SUB-PRODUCT: {ticket.subproduct}
LABELS: {", ".join(l.get("name", "") for l in (issue.get("labels") or []))}

ISSUE BODY:
{body}

DISCUSSION:
{comments or "(no comments)"}

MERGED FIX SUMMARY:
{strip_internals(issue.get("fix_summary") or "") or "(not provided)"}
"""

    try:
        raw = provider.vision_json(load_prompt("draft_solution.system.md"), user_prompt, None, DRAFT_SCHEMA)
        drafted = _validate_draft(raw)
    except Exception as exc:  # noqa: BLE001 - a human reviews drafts anyway
        log.warning("solution drafting failed (%s); writing a skeleton draft", exc)
        drafted = {
            "title": issue.get("title") or ticket.title,
            "summary": "Resolved by the engineering team. Review and rewrite before publishing.",
            "steps_md": "- Update to the latest version of the app.\n- Reload the page.",
            "subproduct": ticket.subproduct,
            "applies_from": None,
            "applies_to": None,
        }

    solution = Solution(
        title=drafted["title"],
        summary=drafted["summary"],
        steps_md=drafted["steps_md"],
        subproduct=drafted.get("subproduct") or ticket.subproduct,
        route_patterns=_routes_for(ticket),
        applies_from=drafted.get("applies_from"),
        applies_to=drafted.get("applies_to"),
        status="draft",
        source="github_issue",
        source_issue_number=ticket.github_issue_number,
    )
    db.add(solution)
    db.flush()
    ticket.linked_solution_id = solution.id
    ticket.status = "resolved"
    ticket.resolved_version = drafted.get("applies_from")
    db.commit()
    return solution


def _validate_draft(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("draft response was not an object")
    title = str(raw.get("title") or "").strip()
    summary = strip_internals(str(raw.get("summary") or ""))
    steps = strip_internals(str(raw.get("steps_md") or ""))
    if not title or not steps:
        raise ValueError("draft is missing a title or steps")
    return {
        "title": title[:200],
        "summary": summary[:800],
        "steps_md": steps[:4000],
        "subproduct": str(raw.get("subproduct") or "").strip() or None,
        "applies_from": _version_or_none(raw.get("applies_from")),
        "applies_to": _version_or_none(raw.get("applies_to")),
    }


def _version_or_none(value: Any) -> str | None:
    v = str(value or "").strip()
    return v if re.fullmatch(r"v?\d+(\.\d+){0,3}", v) else None


def _routes_for(ticket: Ticket) -> list[str]:
    """Best-effort route scoping so the new solution surfaces on the right page.

    The ticket body carries a metadata table written by the agent, so the route
    the user was actually on is recoverable from it.
    """
    route = None
    m = re.search(r"\| Route \| `([^`]+)`", ticket.body or "")
    if m:
        route = m.group(1)
    if route:
        return [route, route.rstrip("/") + "/*"]
    return [f"/{ticket.subproduct}", f"/{ticket.subproduct}/*"]
