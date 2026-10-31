"""Offline provider: no API key, deterministic, good enough to demo the loop.

It does real keyword overlap against the candidate solutions passed in the
prompt, so the confidence gate behaves realistically (high for the seeded
Billing/Projects bugs, low for the unseeded Analytics bug).
"""
from __future__ import annotations

import hashlib
import math
import re
from typing import Any

EMBED_DIM = 256
_STOP = {
    "the", "a", "an", "is", "it", "to", "of", "and", "or", "in", "on", "for",
    "with", "when", "i", "my", "we", "this", "that", "but", "not", "be", "was",
}


def tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9']+", (text or "").lower()) if t not in _STOP and len(t) > 2]


class MockProvider:
    name = "mock"

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * EMBED_DIM
        for tok in tokenize(text):
            h = int(hashlib.sha1(tok.encode()).hexdigest()[:8], 16)
            vec[h % EMBED_DIM] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def vision_json(
        self, system: str, user: str, image_b64: str | None, schema: dict[str, Any]
    ) -> dict[str, Any]:
        candidates = _parse_candidates(user)
        query = _parse_section(user, "USER REPORT")
        q = set(tokenize(query))

        scored: list[tuple[float, str, str]] = []
        for sol_id, blob in candidates:
            c = set(tokenize(blob))
            if not c:
                continue
            overlap = len(q & c) / math.sqrt(len(q) * len(c) or 1)
            scored.append((round(min(overlap * 1.9, 1.0), 2), sol_id, blob))
        scored.sort(reverse=True)

        top = scored[:3]
        confidence = top[0][0] if top else 0.0
        intent = "how_to" if re.search(r"\bhow (do|to)\b", query.lower()) else "bug"
        return {
            "intent": intent,
            "diagnosis": _diagnose(query),
            "matches": [
                {"solution_id": s_id, "relevance": rel, "why": "Keyword overlap with the reported symptom."}
                for rel, s_id, _ in top
                if rel > 0.05
            ],
            "confidence": confidence,
            "needs_ticket": confidence < 0.7,
            "suggested_title": _title(query),
            "suggested_description": query.strip()[:1500],
            "likely_area": _parse_section(user, "ROUTE") or "unknown",
        }


def _parse_section(user: str, header: str) -> str:
    m = re.search(rf"^{re.escape(header)}:\s*(.*?)(?=\n[A-Z][A-Z ]+:|\Z)", user, re.S | re.M)
    return m.group(1).strip() if m else ""


def _parse_candidates(user: str) -> list[tuple[str, str]]:
    block = _parse_section(user, "CANDIDATE SOLUTIONS")
    out = []
    for line in block.splitlines():
        m = re.match(r"\s*\[([0-9a-f\-]+)\]\s*(.+)", line.strip())
        if m:
            out.append((m.group(1), m.group(2)))
    return out


def _diagnose(query: str) -> str:
    first = (query.strip().splitlines() or [""])[0][:160]
    return f"The report describes: {first}" if first else "Not enough signal in the report."


def _title(query: str) -> str:
    first = (query.strip().splitlines() or ["Issue reported from the app"])[0]
    return (first[:70] + "...") if len(first) > 70 else first or "Issue reported from the app"
