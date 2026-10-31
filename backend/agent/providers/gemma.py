"""Gemma via the Gemini API - the multimodal path used in the demo.

Uses the REST endpoint directly so the only dependency is httpx.
"""
from __future__ import annotations

import base64
import json
import re
from typing import Any

import httpx

from ...app.config import settings

API = "https://generativelanguage.googleapis.com/v1beta"


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
        with httpx.Client(timeout=60) as c:
            r = c.post(
                f"{API}/models/{self.model}:generateContent",
                params={"key": self.key},
                json=body,
            )
            r.raise_for_status()
            data = r.json()
        text = "".join(
            p.get("text", "") for p in data["candidates"][0]["content"]["parts"]
        )
        return _loads_lenient(text)

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
        with httpx.Client(timeout=30) as c:
            r = c.post(
                f"{API}/models/{self.embed_model}:embedContent",
                params={"key": self.key},
                json={
                    "model": f"models/{self.embed_model}",
                    "content": {"parts": [{"text": text[:8000]}]},
                },
            )
            r.raise_for_status()
            return r.json()["embedding"]["values"]


def _raw_b64(data_url: str) -> str:
    if "," in data_url and data_url.strip().startswith("data:"):
        return data_url.split(",", 1)[1]
    return data_url


def _loads_lenient(text: str) -> dict[str, Any]:
    """Models sometimes wrap JSON in prose or a fence. Dig it out."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError(f"model did not return JSON: {text[:200]}")
    return json.loads(m.group(0))


# re-exported so openai_compat can share the helpers
__all__ = ["GemmaProvider", "_loads_lenient", "_raw_b64"]
