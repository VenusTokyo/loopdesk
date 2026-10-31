"""Gemma via the Gemini API - the multimodal path used in the demo.

Uses the REST endpoint directly so the only dependency is httpx.
"""
from __future__ import annotations

import base64
import json
import logging
import re
import time
from typing import Any

import httpx

from ...app.config import settings

log = logging.getLogger(__name__)
API = "https://generativelanguage.googleapis.com/v1beta"

# Observed live: Gemma 4 returns 500 INTERNAL and 503 UNAVAILABLE ("high
# demand") intermittently while the identical request succeeds on a retry.
# Transient, so retry rather than fall through to the ticket path.
RETRY_STATUS = {429, 500, 502, 503, 504}
# Measured live: an overloaded Gemma can hang ~90s before returning 500, so
# the per-request timeout matters more than the number of retries. A whole
# analyze call must stay under ~75s or the widget just spins.
BACKOFF = (0.5, 1.5)
REQUEST_TIMEOUT = 35.0
TOTAL_BUDGET = 75.0
# If the configured Gemma stays overloaded, the sibling size is usually free.
SIBLINGS = {"gemma-4-31b-it": "gemma-4-26b-a4b-it", "gemma-4-26b-a4b-it": "gemma-4-31b-it"}


class GemmaProvider:
    name = "gemma"

    def __init__(self, model: str | None = None, embed_model: str | None = None) -> None:
        self.model = model or settings.gemini_model
        self.embed_model = embed_model or settings.gemini_embed_model
        self.key = settings.gemini_api_key
        if not self.key:
            raise RuntimeError("GEMINI_API_KEY is required for LLM_PROVIDER=gemma")

    @property
    def supports_json_mode(self) -> bool:
        """Gemma models on the Gemini API reject responseMimeType with
        "JSON mode is not enabled for models/gemma-...", HTTP 400. The system
        prompt asks for JSON anyway and `_loads_lenient` digs it out of prose
        or a code fence, so dropping the flag costs nothing."""
        return not self.model.lower().startswith("gemma")

    def vision_json(
        self, system: str, user: str, image_b64: str | None, schema: dict[str, Any]
    ) -> dict[str, Any]:
        parts: list[dict[str, Any]] = [{"text": f"{system}\n\n{user}"}]
        if image_b64:
            parts.append(
                {"inline_data": {"mime_type": "image/png", "data": _raw_b64(image_b64)}}
            )
        config: dict[str, Any] = {"temperature": 0.2}
        if self.supports_json_mode:
            config["responseMimeType"] = "application/json"
        body = {"contents": [{"role": "user", "parts": parts}], "generationConfig": config}
        data = self._post_with_retry(body)
        text = "".join(
            p.get("text", "") for p in data["candidates"][0]["content"]["parts"]
        )
        return _loads_lenient(text)

    def _post_with_retry(self, body: dict[str, Any]) -> dict[str, Any]:
        """Ride out transient overload, then try the sibling model once."""
        models = [self.model]
        sibling = SIBLINGS.get(self.model)
        if sibling:
            models.append(sibling)

        deadline = time.monotonic() + TOTAL_BUDGET
        last: Exception | None = None
        for model in models:
            for attempt, pause in enumerate(BACKOFF, start=1):
                if time.monotonic() > deadline:
                    log.error("giving up on %s after %ss", self.model, TOTAL_BUDGET)
                    raise RuntimeError(
                        f"no response within {TOTAL_BUDGET:.0f}s "
                        f"({_redact(str(last), self.key) if last else 'timeout'})"
                    )
                try:
                    with httpx.Client(timeout=REQUEST_TIMEOUT) as c:
                        r = c.post(
                            f"{API}/models/{model}:generateContent",
                            params={"key": self.key},
                            json=body,
                        )
                    if r.status_code in RETRY_STATUS:
                        log.warning(
                            "%s returned %s (attempt %s/%s)", model, r.status_code, attempt, len(BACKOFF)
                        )
                        last = RuntimeError(f"{model} returned {r.status_code}")
                        time.sleep(pause)
                        continue
                    r.raise_for_status()
                    if model != self.model:
                        log.warning("fell back to %s; %s was unavailable", model, self.model)
                    return r.json()
                except httpx.HTTPStatusError as exc:
                    raise RuntimeError(_redact(str(exc), self.key)) from None
                except httpx.HTTPError as exc:
                    last = exc
                    time.sleep(pause)
        raise RuntimeError(_redact(str(last), self.key) if last else "model unavailable")

    def list_models(self) -> list[str]:
        """What this key can actually call. Model ids move; this settles it."""
        with httpx.Client(timeout=30) as c:
            r = c.get(f"{API}/models", params={"key": self.key, "pageSize": 200})
            r.raise_for_status()
            return sorted(
                m.get("name", "").removeprefix("models/")
                for m in r.json().get("models", [])
                if "generateContent" in (m.get("supportedGenerationMethods") or [])
            )

    def embed(self, text: str) -> list[float]:
        payload = {
            "model": f"models/{self.embed_model}",
            "content": {"parts": [{"text": text[:8000]}]},
        }
        last: Exception | None = None
        for pause in BACKOFF:
            try:
                with httpx.Client(timeout=REQUEST_TIMEOUT) as c:
                    r = c.post(
                        f"{API}/models/{self.embed_model}:embedContent",
                        params={"key": self.key},
                        json=payload,
                    )
                if r.status_code in RETRY_STATUS:
                    last = RuntimeError(f"embedding returned {r.status_code}")
                    time.sleep(pause)
                    continue
                r.raise_for_status()
                return r.json()["embedding"]["values"]
            except httpx.HTTPStatusError as exc:
                raise RuntimeError(_redact(str(exc), self.key)) from None
            except httpx.HTTPError as exc:
                last = exc
                time.sleep(pause)
        raise RuntimeError(_redact(str(last), self.key) if last else "embedding unavailable")


def _redact(message: str, key: str) -> str:
    """API errors echo the request URL, which carries the key. Never log it."""
    return message.replace(key, "<redacted>") if key else message


def _raw_b64(data_url: str) -> str:
    if "," in data_url and data_url.strip().startswith("data:"):
        return data_url.split(",", 1)[1]
    return data_url


def _loads_lenient(text: str) -> dict[str, Any]:
    """Models wrap JSON in prose, code fences, or follow it with commentary.

    Without JSON mode (Gemma rejects it) that is the normal case, so take the
    first balanced object rather than guessing with a regex - a greedy match
    swallows trailing prose and a lazy one truncates nested objects.
    """
    text = (text or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fence = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    if fence:
        try:
            return json.loads(fence.group(1).strip())
        except json.JSONDecodeError:
            text = fence.group(1).strip()

    obj = _first_balanced_object(text)
    if obj is None:
        raise ValueError(f"model did not return JSON: {text[:200]}")
    return json.loads(obj)


def _first_balanced_object(text: str) -> str | None:
    """Scan for the first {...} whose braces balance, ignoring braces in strings."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


# re-exported so openai_compat can share the helpers
__all__ = ["GemmaProvider", "_loads_lenient", "_raw_b64"]
