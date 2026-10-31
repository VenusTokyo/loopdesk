"""JSON schema for the diagnose call, plus a forgiving validator.

The model is asked for strict JSON. We validate, coerce the obvious mistakes
(a string where a float belongs, a missing list) and reject anything that
cites a solution id we did not offer - that is the hallucination guard.
"""
from __future__ import annotations

from typing import Any

INTENTS = {"bug", "how_to", "feature_request", "account_config"}

DIAGNOSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["intent", "diagnosis", "matches", "confidence", "needs_ticket"],
    "properties": {
        "intent": {"type": "string", "enum": sorted(INTENTS)},
        "diagnosis": {"type": "string"},
        "matches": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["solution_id", "relevance"],
                "properties": {
                    "solution_id": {"type": "string"},
                    "relevance": {"type": "number"},
                    "why": {"type": "string"},
                },
            },
        },
        "confidence": {"type": "number"},
        "needs_ticket": {"type": "boolean"},
        "suggested_title": {"type": "string"},
        "suggested_description": {"type": "string"},
        "likely_area": {"type": "string"},
    },
}


class SchemaError(ValueError):
    pass


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def validate_diagnosis(raw: Any, allowed_ids: set[str]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise SchemaError("model response was not an object")

    intent = str(raw.get("intent") or "bug").strip().lower()
    if intent not in INTENTS:
        intent = "bug"

    matches = []
    for m in raw.get("matches") or []:
        if not isinstance(m, dict):
            continue
        sol_id = str(m.get("solution_id") or "").strip()
        if sol_id not in allowed_ids:
            continue  # cited something we never offered -> drop it
        matches.append(
            {
                "solution_id": sol_id,
                "relevance": _to_float(m.get("relevance")),
                "why": str(m.get("why") or "")[:500],
            }
        )
    matches.sort(key=lambda m: m["relevance"], reverse=True)

    confidence = _to_float(raw.get("confidence"))
    if not matches:
        confidence = min(confidence, 0.2)  # no citation means no confidence

    needs_ticket = raw.get("needs_ticket")
    if not isinstance(needs_ticket, bool):
        needs_ticket = confidence < 0.7

    diagnosis = str(raw.get("diagnosis") or "").strip()
    if not diagnosis:
        raise SchemaError("model returned an empty diagnosis")

    return {
        "intent": intent,
        "diagnosis": diagnosis[:1000],
        "matches": matches,
        "confidence": confidence,
        "needs_ticket": bool(needs_ticket),
        "suggested_title": str(raw.get("suggested_title") or "")[:200],
        "suggested_description": str(raw.get("suggested_description") or "")[:4000],
        "likely_area": str(raw.get("likely_area") or "")[:200],
    }
