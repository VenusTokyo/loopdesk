"""The one interface every model backend implements.

Keeping this tiny is what makes the project swappable between a hosted
multimodal model (Gemma via the Gemini API) and a self-hosted open-weight
model behind an OpenAI-compatible endpoint.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    name: str

    def vision_json(
        self,
        system: str,
        user: str,
        image_b64: str | None,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        """Return a dict that validates against `schema`."""

    def embed(self, text: str) -> list[float]:
        """Return a dense vector for `text`."""
