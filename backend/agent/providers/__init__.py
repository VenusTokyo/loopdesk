"""Provider registry. `LLM_PROVIDER` picks one; everything else is identical."""
from __future__ import annotations

import logging

from ...app.config import settings
from .base import LLMProvider
from .mock import MockProvider

log = logging.getLogger(__name__)
_cached: LLMProvider | None = None


def get_provider(force: str | None = None) -> LLMProvider:
    global _cached
    if _cached is not None and force is None:
        return _cached

    choice = (force or settings.llm_provider or "mock").lower()
    provider: LLMProvider
    try:
        if choice == "gemma":
            from .gemma import GemmaProvider

            provider = GemmaProvider()
        elif choice == "openai_compat":
            from .openai_compat import OpenAICompatProvider

            provider = OpenAICompatProvider()
        else:
            provider = MockProvider()
    except Exception as exc:  # noqa: BLE001 - never let the demo die on config
        log.warning("provider %s unavailable (%s); falling back to mock", choice, exc)
        provider = MockProvider()

    if force is None:
        _cached = provider
    return provider


__all__ = ["LLMProvider", "MockProvider", "get_provider"]
