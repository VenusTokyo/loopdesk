"""Settings loaded from the environment (see .env.example)."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    app_env: str = "dev"
    public_base_url: str = "http://localhost:8000"
    cors_origins: str = "*"

    database_url: str = "sqlite:///./data/loopdesk.db"

    llm_provider: str = "mock"
    gemini_api_key: str = ""
    gemini_model: str = "gemma-3-27b-it"
    gemini_embed_model: str = "text-embedding-004"

    openai_compat_base_url: str = "http://localhost:11434/v1"
    openai_compat_api_key: str = ""
    openai_compat_model: str = "gemma3:12b"
    openai_compat_embed_model: str = "bge-small"

    storage_backend: str = "local"
    spaces_bucket: str = ""
    spaces_region: str = "blr1"
    spaces_endpoint: str = ""
    spaces_key: str = ""
    spaces_secret: str = ""

    github_token: str = ""
    github_repo: str = ""
    github_webhook_secret: str = "dev-secret"

    # The hand-seeded open ticket used to demonstrate duplicate detection.
    # Issue numbers start at 1 in a fresh repository, so this is not a constant.
    demo_duplicate_issue: int = 42

    confidence_high: float = 0.7
    confidence_low: float = 0.4
    admin_token: str = "dev-admin"

    @property
    def data_dir(self) -> Path:
        d = REPO_ROOT / "data"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def github_enabled(self) -> bool:
        return bool(self.github_token and self.github_repo)


@lru_cache
def get_settings() -> Settings:
    # Resolve a relative sqlite path against the repo root so the server can be
    # started from anywhere.
    s = Settings()
    if s.database_url.startswith("sqlite:///./"):
        rel = s.database_url.replace("sqlite:///./", "")
        s.database_url = f"sqlite:///{(REPO_ROOT / rel).as_posix()}"
    os.environ.setdefault("LOOPDESK_READY", "1")
    return s


settings = get_settings()
