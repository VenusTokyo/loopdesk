"""End-to-end tests for the closed loop, on SQLite with the mock provider.

They cover the behaviour the demo depends on:
  - a known issue gets a cited answer
  - an unknown issue is NOT guessed at
  - a blocked/unknown case produces a ticket
  - closing that ticket drafts a solution, approving publishes it
  - the next user with the same problem gets the new solution
"""
from __future__ import annotations

import os
import tempfile

import pytest

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/test.db"
os.environ["LLM_PROVIDER"] = "mock"
os.environ["GITHUB_TOKEN"] = ""

from fastapi.testclient import TestClient  # noqa: E402

from backend.app.config import settings  # noqa: E402
from backend.app.db import SessionLocal, init_db  # noqa: E402
from backend.app.main import app  # noqa: E402
from backend.app.models import Solution, Ticket  # noqa: E402
from backend.seed.seed import seed  # noqa: E402

ADMIN = {"X-Admin-Token": "dev-admin"}

BILLING_CONTEXT = {
    "route": "/demo/billing/",
    "subproduct": "billing",
    "app_version": "2.4.0",
    "user_role": "member",
    "page_title": "Billing - Acme Suite",
    "console_errors": ["Invoice export failed: server error 500"],
    "failed_requests": [{"url": "/api/demo/billing/export", "status": 500, "method": "GET"}],
    "session_id": "sess_test",
}

ANALYTICS_CONTEXT = {
    "route": "/demo/analytics/",
    "subproduct": "analytics",
    "app_version": "2.4.0",
    "user_role": "member",
    "page_title": "Analytics - Acme Suite",
    "console_errors": ["TypeError: Cannot read properties of undefined (reading 'range')"],
    "failed_requests": [{"url": "/api/demo/analytics/report", "status": 500, "method": "GET"}],
    "session_id": "sess_test",
}


@pytest.fixture(scope="module", autouse=True)
def seeded():
    init_db()
    seed(reset_first=True)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health(client):
    body = client.get("/healthz").json()
    assert body["ok"] is True
    assert body["github"] == "dry-run"


def test_page_suggestions_are_route_scoped(client):
    r = client.get(
        "/api/suggestions",
        params={"route": "/demo/billing/", "subproduct": "billing", "version": "2.4.0"},
    )
    assert r.status_code == 200
    titles = [s["title"] for s in r.json()]
    assert any("Invoice export" in t for t in titles)
    assert all(s["subproduct"] == "billing" for s in r.json())


def test_deprecated_and_out_of_range_solutions_are_filtered(client):
    r = client.get(
        "/api/suggestions",
        params={"route": "/demo/analytics/", "subproduct": "analytics", "version": "2.4.0"},
    )
    titles = [s["title"] for s in r.json()]
    # Deprecated, and only applies up to 2.1.0.
    assert not any("Safari 15" in t for t in titles)


def test_known_issue_is_answered_with_a_citation(client):
    r = client.post(
        "/api/analyze",
        json={
            "screenshot": None,
            "comment": "The invoice export button fails with a server error when I export invoices",
            "context": BILLING_CONTEXT,
        },
    )
    body = r.json()
    assert body["verdict"] in ("confident", "maybe")
    assert body["solutions"], "a known issue must return at least one cited solution"
    assert "Invoice export" in body["solutions"][0]["title"]


def test_unknown_issue_is_not_guessed_at(client):
    r = client.post(
        "/api/analyze",
        json={
            "screenshot": None,
            "comment": "I pick the thirty day window and it jumps back on its own",
            "context": ANALYTICS_CONTEXT,
        },
    )
    body = r.json()
    assert body["verdict"] == "unknown"
    assert body["solutions"] == []
    assert body["needs_ticket"] is True
    assert body["suggested_title"]
    assert "Route" in body["suggested_description"]


def test_rating_a_solution_then_ticketing_counts_against_it(client):
    analyze = client.post(
        "/api/analyze",
        json={"comment": "invoice export server error", "context": BILLING_CONTEXT},
    ).json()
    solution_id = analyze["solutions"][0]["id"]

    assert client.post(
        "/api/rate",
        json={"report_id": analyze["report_id"], "solution_id": solution_id, "helpful": True},
    ).json()["ok"]

    with SessionLocal() as db:
        assert db.get(Solution, solution_id).helpful_count == 1
        assert db.get(Solution, solution_id).ticket_after_count == 0

    client.post(
        "/api/tickets",
        json={
            "report_id": analyze["report_id"],
            "title": "Export still broken",
            "description": "The workaround did not help.",
            "subproduct": "billing",
        },
    )

    with SessionLocal() as db:
        assert db.get(Solution, solution_id).ticket_after_count == 1


def test_duplicate_detection_offers_me_too(client):
    body = client.post(
        "/api/analyze",
        json={
            "comment": "Analytics date range resets to Last 7 days when I pick 30 days",
            "context": ANALYTICS_CONTEXT,
        },
    ).json()
    assert body["duplicate_of"] is not None
    # The seeded ticket's number is configuration, not a constant: a fresh
    # GitHub repository numbers its first issue 1, not 42.
    assert body["duplicate_of"]["issue_number"] == settings.demo_duplicate_issue


def test_full_resolution_loop(client):
    # 1. A user reports the unsolved analytics bug and raises a ticket.
    analyze = client.post(
        "/api/analyze",
        json={"comment": "the chart filter will not stay where I put it", "context": ANALYTICS_CONTEXT},
    ).json()
    ticket = client.post(
        "/api/tickets",
        json={
            "report_id": analyze["report_id"],
            "title": analyze["suggested_title"],
            "description": analyze["suggested_description"],
            "subproduct": "analytics",
        },
    ).json()
    assert ticket["dry_run"] is True
    number = ticket["github_issue_number"]

    # 2. A developer closes the issue -> the webhook drafts a solution.
    hook = client.post(
        "/webhooks/github",
        json={"action": "closed", "issue": {"number": number}},
        headers={"X-GitHub-Event": "issues"},
    ).json()
    assert hook["ok"] is True
    solution_id = hook["solution_id"]

    drafts = client.get("/api/admin/drafts", headers=ADMIN).json()
    assert any(d["id"] == solution_id for d in drafts)

    # 3. The developer approves it, with an edit.
    approved = client.post(
        "/api/admin/approve",
        headers=ADMIN,
        json={
            "solution_id": solution_id,
            "title": "Analytics date range resets to Last 7 days",
            "summary": "A saved range is dropped before the report query runs.",
            "steps_md": "- Update to v2.4.1 or later.\n- Reload the Analytics page.",
        },
    ).json()
    assert approved["ok"] is True
    assert approved["path"].startswith("solutions/analytics/")

    # 4. The next user with the same problem gets it straight away.
    nxt = client.post(
        "/api/analyze",
        json={
            "comment": "Analytics date range resets to Last 7 days when I choose another range",
            "context": {**ANALYTICS_CONTEXT, "session_id": "sess_other"},
        },
    ).json()
    assert nxt["verdict"] in ("confident", "maybe")
    assert any(s["id"] == solution_id for s in nxt["solutions"])

    # 5. And the original reporter sees it was fixed.
    mine = client.get("/api/reports/mine", params={"session_id": "sess_test"}).json()
    assert any(r.get("fixed_in") for r in mine)


def test_admin_requires_a_token(client):
    assert client.get("/api/admin/drafts").status_code == 401
    assert client.get("/api/admin/drafts", headers={"X-Admin-Token": "nope"}).status_code == 401


def test_webhook_ignores_issues_loopdesk_did_not_create(client):
    r = client.post(
        "/webhooks/github",
        json={"action": "closed", "issue": {"number": 999999}},
        headers={"X-GitHub-Event": "issues"},
    )
    assert r.json()["ignored"] is True


def test_stats_report_deflection(client):
    s = client.get("/api/admin/stats", headers=ADMIN).json()
    assert s["reports"] > 0
    assert 0.0 <= s["deflection_rate"] <= 1.0
    with SessionLocal() as db:
        assert db.query(Ticket).count() >= 1
