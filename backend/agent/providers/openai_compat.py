"""Any OpenAI-compatible endpoint: Ollama, vLLM, or a DigitalOcean GenAI
endpoint serving an open-weight model. This is the self-hosted path."""
from __future__ import annotations

from typing import Any

import httpx

from ...app.config import settings
from .gemma import _loads_lenient


class OpenAICompatProvider:
    name = "openai_compat"

    def __init__(self) -> None:
        self.base = settings.openai_compat_base_url.rstrip("/")
        self.model = settings.openai_compat_model
        self.embed_model = settings.openai_compat_embed_model
        self.key = settings.openai_compat_api_key or "not-needed"

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.key}"}

    def vision_json(
        self, system: str, user: str, image_b64: str | None, schema: dict[str, Any]
    ) -> dict[str, Any]:
        content: list[dict[str, Any]] = [{"type": "text", "text": user}]
        if image_b64:
            url = image_b64 if image_b64.startswith("data:") else f"data:image/png;base64,{image_b64}"
            content.append({"type": "image_url", "image_url": {"url": url}})
        body = {
            "model": self.model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
        }
        with httpx.Client(timeout=120) as c:
            r = c.post(f"{self.base}/chat/completions", json=body, headers=self._headers)
            r.raise_for_status()
            return _loads_lenient(r.json()["choices"][0]["message"]["content"])

    def embed(self, text: str) -> list[float]:
        with httpx.Client(timeout=60) as c:
            r = c.post(
                f"{self.base}/embeddings",
                json={"model": self.embed_model, "input": text[:8000]},
                headers=self._headers,
            )
            r.raise_for_status()
            return r.json()["data"][0]["embedding"]
