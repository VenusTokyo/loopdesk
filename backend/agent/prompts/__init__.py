from __future__ import annotations

from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).parent


@lru_cache
def load(name: str) -> str:
    return (HERE / name).read_text(encoding="utf-8")
