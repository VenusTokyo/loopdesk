"""Retrieval over the solutions KB.

Two layers:
  layer 1 - page-based: route pattern + subproduct + version match, no model.
  layer 2 - semantic: cosine similarity over embeddings.

Similarity is computed in Python. At demo scale (hundreds of solutions) that
is instant, and it keeps SQLite viable so `docker-compose up` needs no
extensions. Swapping in pgvector means replacing `_cosine_rank` only.
"""
from __future__ import annotations

import fnmatch
import math
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..app.models import Solution

_VERSION_RE = re.compile(r"\d+")


def version_tuple(v: str | None) -> tuple[int, ...]:
    if not v:
        return ()
    return tuple(int(p) for p in _VERSION_RE.findall(v)[:4])


def version_applies(sol: Solution, app_version: str | None) -> bool:
    """A solution applies unless the running version is outside its range."""
    if not app_version:
        return True
    cur = version_tuple(app_version)
    if not cur:
        return True
    lo, hi = version_tuple(sol.applies_from), version_tuple(sol.applies_to)
    if lo and cur < lo:
        return False
    if hi and cur > hi:
        return False
    return True


def route_matches(sol: Solution, route: str | None) -> bool:
    patterns = sol.route_patterns or []
    if not patterns or not route:
        return False
    return any(fnmatch.fnmatch(route, p) for p in patterns)


def cosine(a: list[float] | None, b: list[float] | None) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if not na or not nb:
        return 0.0
    return dot / (na * nb)


def quality_weight(sol: Solution) -> float:
    """Ratings nudge ranking, with a floor so new solutions are not buried."""
    good = sol.helpful_count
    bad = sol.unhelpful_count + sol.ticket_after_count
    total = good + bad
    if total == 0:
        return 0.85
    return max(0.5, min(1.15, 0.5 + (good / total) * 0.65))


def published(db: Session, subproduct: str | None = None) -> list[Solution]:
    stmt = select(Solution).where(Solution.status == "published")
    if subproduct and subproduct != "unknown":
        stmt = stmt.where(Solution.subproduct == subproduct)
    return list(db.scalars(stmt))


def page_suggestions(
    db: Session, route: str, subproduct: str | None, app_version: str | None, limit: int = 4
) -> list[Solution]:
    """Layer 1: what we can show the instant the panel opens, with no AI."""
    hits = [
        s
        for s in published(db, subproduct)
        if route_matches(s, route) and version_applies(s, app_version)
    ]
    hits.sort(key=quality_weight, reverse=True)
    return hits[:limit]


def semantic_candidates(
    db: Session,
    query_embedding: list[float],
    route: str | None,
    subproduct: str | None,
    app_version: str | None,
    limit: int = 5,
) -> list[tuple[Solution, float]]:
    """Layer 2: embedding similarity, filtered by subproduct and version."""
    scored: list[tuple[Solution, float]] = []
    for s in published(db, subproduct):
        if not version_applies(s, app_version):
            continue
        sim = cosine(query_embedding, s.embedding)
        if route_matches(s, route):
            sim += 0.08  # same page is weak but real evidence
        scored.append((s, sim * quality_weight(s)))
    scored.sort(key=lambda t: t[1], reverse=True)
    return [(s, round(score, 4)) for s, score in scored[:limit] if score > 0]


def merge_candidates(
    page: list[Solution], semantic: list[tuple[Solution, float]], limit: int = 6
) -> list[tuple[Solution, float]]:
    """Union of both layers, de-duplicated, page hits kept near the top."""
    out: dict[str, tuple[Solution, float]] = {}
    for s in page:
        out[s.id] = (s, 0.35)
    for s, score in semantic:
        prev = out.get(s.id)
        out[s.id] = (s, max(score, prev[1]) if prev else score)
    ranked = sorted(out.values(), key=lambda t: t[1], reverse=True)
    return ranked[:limit]


def build_query(comment: str, ctx) -> str:
    """One string that carries everything we know about the problem."""
    bits = [comment or ""]
    if getattr(ctx, "page_title", ""):
        bits.append(f"page: {ctx.page_title}")
    bits.append(f"route: {getattr(ctx, 'route', '')}")
    for err in (getattr(ctx, "console_errors", None) or [])[:5]:
        bits.append(f"console error: {err}")
    for req in (getattr(ctx, "failed_requests", None) or [])[:5]:
        url = getattr(req, "url", None) or (req.get("url") if isinstance(req, dict) else "")
        status = getattr(req, "status", None) or (req.get("status") if isinstance(req, dict) else "")
        bits.append(f"failed request: {status} {url}")
    return "\n".join(b for b in bits if b.strip())
