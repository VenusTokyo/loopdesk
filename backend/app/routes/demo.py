"""Endpoints that exist only to fail, so the demo app's bugs are real.

The widget records failed requests by wrapping fetch, and the agent reads
them. Faking the failure client-side would leave that path untested, so the
seeded bugs call endpoints that genuinely return 4xx/5xx.
"""
from __future__ import annotations

from fastapi import APIRouter, Response

router = APIRouter(prefix="/api/demo", tags=["demo"])


@router.get("/billing/export")
def billing_export() -> Response:
    return Response(
        content='{"error":"invoice_export_failed","detail":"PDF renderer timed out"}',
        media_type="application/json",
        status_code=500,
    )


@router.post("/projects/invite")
def projects_invite() -> Response:
    return Response(
        content='{"error":"permission_denied","required_role":"admin"}',
        media_type="application/json",
        status_code=403,
    )


@router.get("/analytics/report")
def analytics_report() -> Response:
    return Response(
        content='{"error":"range_unset","detail":"filter state lost before the query ran"}',
        media_type="application/json",
        status_code=500,
    )
