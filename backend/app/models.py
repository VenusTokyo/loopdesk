"""Database models. Mirrors the data model in plan.md section 7.

Embeddings are stored as JSON so the project runs on plain SQLite with no
extensions. On Postgres this is still correct; swapping in a real `vector`
column is a tracked good-first-issue (see docs/self-hosting.md).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from .db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Solution(Base):
    __tablename__ = "solutions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String(300))
    summary: Mapped[str] = mapped_column(Text, default="")
    steps_md: Mapped[str] = mapped_column(Text, default="")
    subproduct: Mapped[str] = mapped_column(String(64), index=True)
    route_patterns: Mapped[list] = mapped_column(JSON, default=list)
    applies_from: Mapped[str | None] = mapped_column(String(32), nullable=True)
    applies_to: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="draft", index=True)
    source: Mapped[str] = mapped_column(String(32), default="seed")
    source_issue_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)
    helpful_count: Mapped[int] = mapped_column(Integer, default=0)
    unhelpful_count: Mapped[int] = mapped_column(Integer, default=0)
    ticket_after_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    screenshot_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    comment: Mapped[str] = mapped_column(Text, default="")
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    intent: Mapped[str | None] = mapped_column(String(32), nullable=True)
    agent_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Rating(Base):
    __tablename__ = "ratings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    report_id: Mapped[str] = mapped_column(String(36), ForeignKey("reports.id"))
    solution_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("solutions.id"), nullable=True)
    helpful: Mapped[bool] = mapped_column(Boolean, default=False)
    raised_ticket: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    report_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("reports.id"), nullable=True)
    github_issue_number: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    github_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str] = mapped_column(String(300), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    subproduct: Mapped[str] = mapped_column(String(64), index=True, default="")
    status: Mapped[str] = mapped_column(String(16), default="open", index=True)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=False)
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)
    linked_solution_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    resolved_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Event(Base):
    """Lightweight audit trail, also powers the stats card."""

    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    kind: Mapped[str] = mapped_column(String(48), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
