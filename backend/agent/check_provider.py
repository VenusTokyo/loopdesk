"""Prove the configured model provider actually works.

    python -m backend.agent.check_provider
    python -m backend.agent.check_provider --list

Runs the two calls LoopDesk depends on - a structured vision call and an
embedding - against whatever LLM_PROVIDER points at, and reports exactly
what failed if either does. Worth running before a demo rather than
discovering a bad model id live.
"""
from __future__ import annotations

import argparse
import base64
import json
import sys

from ..app.config import settings
from .prompts import load as load_prompt
from .providers import get_provider
from .schema import DIAGNOSE_SCHEMA, validate_diagnosis

# A 1x1 PNG. Enough to prove the image part of the request is accepted.
TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

SAMPLE_USER = """USER REPORT:
The invoice export button fails with a server error.

ROUTE: /billing
SUBPRODUCT: billing
APP VERSION: 2.4.0
USER ROLE: member

CONSOLE ERRORS:
- Invoice export failed: server error 500

FAILED REQUESTS:
- GET /api/billing/export -> 500

CANDIDATE SOLUTIONS:
[sol-1] Invoice export fails with a server error: The bulk export returns a 500 while the billing renderer is under load; a single invoice download works.
[sol-2] Charts render empty in Safari 15: Update Safari to version 16 or later.
"""


def ok(msg: str) -> None:
    print(f"  PASS  {msg}")


def fail(msg: str) -> None:
    print(f"  FAIL  {msg}")


def main(list_models: bool) -> int:
    print(f"provider configured : {settings.llm_provider}")
    provider = get_provider()
    print(f"provider in use     : {provider.name}")

    if provider.name != settings.llm_provider:
        fail(
            f"'{settings.llm_provider}' could not be constructed, so it fell back to "
            f"'{provider.name}'. Check the key and base URL for that provider."
        )
        return 1

    if provider.name == "gemma":
        print(f"model               : {settings.gemini_model}")
        print(f"embedding model     : {settings.gemini_embed_model}")
        print(f"json mode           : {'on' if provider.supports_json_mode else 'off (Gemma)'}")
    elif provider.name == "openai_compat":
        print(f"base url            : {settings.openai_compat_base_url}")
        print(f"model               : {settings.openai_compat_model}")
        print(f"embedding model     : {settings.openai_compat_embed_model}")
    print()

    if list_models and hasattr(provider, "list_models"):
        try:
            names = provider.list_models()
        except Exception as exc:  # noqa: BLE001
            fail(f"could not list models: {exc}")
            return 1
        print("models this key can call with generateContent:")
        for n in names:
            marker = "  <- configured" if n == settings.gemini_model else ""
            print(f"  {n}{marker}")
        print()
        if settings.gemini_model not in names:
            fail(f"'{settings.gemini_model}' is not in that list. Set GEMINI_MODEL to one of them.")
            return 1
        ok(f"'{settings.gemini_model}' is callable")
        return 0

    failures = 0

    # 1. Structured vision call - the one the whole pipeline rests on.
    try:
        raw = provider.vision_json(
            load_prompt("diagnose.system.md"), SAMPLE_USER, base64.b64encode(TINY_PNG).decode(), DIAGNOSE_SCHEMA
        )
        ok("vision call returned a response")
        try:
            result = validate_diagnosis(raw, {"sol-1", "sol-2"})
            ok(
                f"response validates: intent={result['intent']} "
                f"confidence={result['confidence']} matches={len(result['matches'])}"
            )
            if result["matches"] and result["matches"][0]["solution_id"] == "sol-1":
                ok("cited the right solution")
            elif result["matches"]:
                print(f"  NOTE  cited {result['matches'][0]['solution_id']}, expected sol-1")
            else:
                print("  NOTE  cited nothing, so this report would become a ticket")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            fail(f"response did not validate: {exc}")
            print(f"        raw: {json.dumps(raw)[:300]}")
    except Exception as exc:  # noqa: BLE001
        failures += 1
        fail(f"vision call failed: {type(exc).__name__}: {exc}")

    # 2. Embeddings - without these, only page-based suggestions work.
    try:
        vec = provider.embed("invoice export fails with a server error")
        if not vec:
            raise ValueError("empty vector")
        ok(f"embedding returned {len(vec)} dimensions")
    except Exception as exc:  # noqa: BLE001
        failures += 1
        fail(f"embedding failed: {type(exc).__name__}: {exc}")

    print()
    if failures:
        print(f"{failures} check(s) failed. LoopDesk still runs - the pipeline degrades to the")
        print("ticket path - but the demo will not show a cited answer.")
        return 1

    print("All checks passed.")
    if provider.name != "mock":
        print("Re-seed so embeddings match this provider:  python -m backend.seed.seed --reset")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Check the configured LLM provider")
    ap.add_argument("--list", action="store_true", help="list callable model ids and exit")
    sys.exit(main(ap.parse_args().list))
