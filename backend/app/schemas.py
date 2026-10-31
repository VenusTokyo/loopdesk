"""Request/response models for the public API."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class FailedRequest(BaseModel):
    url: str = ""
    status: int | None = None
    method: str = "GET"


class WidgetContext(BaseModel):
    route: str = "/"
    url: str = ""
    subproduct: str = "unknown"
    app_version: str = "0.0.0"
    user_role: str = "member"
    browser: str = ""
    viewport: str = ""
    page_title: str = ""
    console_errors: list[str] = Field(default_factory=list)
    failed_requests: list[FailedRequest] = Field(default_factory=list)
    session_id: str | None = None


class AnalyzeRequest(BaseModel):
    screenshot: str | None = None  # data:image/png;base64,...
    comment: str = ""
    context: WidgetContext = Field(default_factory=WidgetContext)


class SolutionCard(BaseModel):
    id: str
    title: str
    summary: str
    steps_md: str
    subproduct: str
    relevance: float = 0.0
    why: str = ""
    score: float = 0.0
    source: str = "seed"
    source_issue_number: int | None = None


class AnalyzeResponse(BaseModel):
    report_id: str
    intent: Literal["bug", "how_to", "feature_request", "account_config"] = "bug"
    diagnosis: str = ""
    confidence: float = 0.0
    verdict: Literal["confident", "maybe", "unknown"] = "unknown"
    message: str = ""
    solutions: list[SolutionCard] = Field(default_factory=list)
    needs_ticket: bool = True
    suggested_title: str = ""
    suggested_description: str = ""
    likely_area: str = ""
    duplicate_of: dict[str, Any] | None = None
    screenshot_url: str | None = None
    provider: str = "mock"


class RateRequest(BaseModel):
    report_id: str
    solution_id: str | None = None
    helpful: bool


class TicketRequest(BaseModel):
    report_id: str | None = None
    title: str
    description: str
    subproduct: str = "unknown"
    me_too_issue_number: int | None = None


class TicketResponse(BaseModel):
    id: str
    github_issue_number: int | None = None
    github_url: str | None = None
    dry_run: bool = False
    me_too: bool = False
    # False when GitHub was reachable-in-principle (a token is configured) but
    # the call failed. The report is still stored; only delivery failed.
    delivered: bool = True
    error: str | None = None


class DraftApproval(BaseModel):
    solution_id: str
    title: str | None = None
    summary: str | None = None
    steps_md: str | None = None
