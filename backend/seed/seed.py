"""Load the knowledge base so the demo is reproducible with one command.

    python -m backend.seed.seed          # solutions + one open ticket
    python -m backend.seed.seed --reset  # wipe first

Idempotent: re-running updates existing entries by title rather than
duplicating them.
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from ..agent.providers import get_provider
from ..app.config import settings
from ..app.db import SessionLocal, init_db
from ..app.models import Event, Rating, Report, Solution, Ticket

log = logging.getLogger("seed")
HERE = Path(__file__).parent

# One open ticket so the "Me too" duplicate flow has something to find.
DUPLICATE_CANDIDATE = {
    "title": "Analytics date range resets to Last 7 days",
    "body": (
        "**What the user reported**\n\n"
        "I pick Last 30 days and the chart snaps back to Last 7 days.\n\n"
        "| | |\n|---|---|\n| Route | `/demo/analytics/` |\n"
        "| Sub-product | `analytics` |\n| App version | `2.4.0` |\n"
    ),
    "subproduct": "analytics",
}


def reset(db) -> None:
    for model in (Rating, Ticket, Report, Event, Solution):
        db.query(model).delete()
    db.commit()
    log.info("cleared existing rows")


def seed(reset_first: bool = False) -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    init_db()
    provider = get_provider()
    log.info("embedding with provider: %s", provider.name)

    entries = json.loads((HERE / "seed_solutions.json").read_text(encoding="utf-8"))

    with SessionLocal() as db:
        if reset_first:
            reset(db)

        created = updated = 0
        for entry in entries:
            sol = db.query(Solution).filter(Solution.title == entry["title"]).one_or_none()
            if sol is None:
                sol = Solution()
                db.add(sol)
                created += 1
            else:
                updated += 1

            for field, value in entry.items():
                setattr(sol, field, value)
            sol.embedding = provider.embed(
                f"{entry['title']}\n{entry['summary']}\n{entry['steps_md']}"
            )

        number = settings.demo_duplicate_issue
        repo = settings.github_repo or "example/loopdesk-demo-tickets"
        ticket = db.query(Ticket).filter(Ticket.github_issue_number == number).one_or_none()
        if ticket is None:
            ticket = Ticket(
                **DUPLICATE_CANDIDATE,
                github_issue_number=number,
                status="open",
                dry_run=not settings.github_enabled,
                github_url=f"https://github.com/{repo}/issues/{number}",
            )
            ticket.embedding = provider.embed(
                f"{DUPLICATE_CANDIDATE['title']}\n{DUPLICATE_CANDIDATE['body']}"
            )
            db.add(ticket)
            log.info("added open ticket #%s for the duplicate-detection demo", number)

        db.commit()
        published = db.query(Solution).filter(Solution.status == "published").count()

    log.info("seeded: %s new, %s updated, %s published", created, updated, published)
    log.info("note: the Analytics 'range resets' bug is deliberately NOT in the KB")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Seed the LoopDesk knowledge base")
    ap.add_argument("--reset", action="store_true", help="delete all rows first")
    seed(ap.parse_args().reset)
