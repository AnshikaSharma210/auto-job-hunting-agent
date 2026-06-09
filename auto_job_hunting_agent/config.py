from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load repo root .env first so it wins over stale OPENAI_* exports in the shell / IDE.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env", override=True, encoding="utf-8-sig")


def _strip_or_none(v: str | None) -> str | None:
    if v is None:
        return None
    s = v.strip()
    return s or None


def _env_lower(name: str, default: str) -> str:
    raw = os.getenv(name)
    if raw is None:
        return default
    s = raw.strip().lower()
    return s if s else default


def _resolved_embedding_provider() -> str:
    """Default local embeddings to save Gemini quota; google only when explicitly set."""
    return _env_lower("EMBEDDING_PROVIDER", "local")


@dataclass(frozen=True)
class Settings:
    # ── LLM provider: "openai" | "google" ────────────────────────────────
    llm_provider: str

    # ── Embedding provider: "google" | "openai" | "local" ───────────────
    # "google" uses gemini-embedding-001 via the same key as the chat model.
    embedding_provider: str

    # ── OpenAI (only when llm_provider / embedding_provider = "openai") ─
    openai_api_key: str | None
    openai_chat_model: str
    openai_embedding_model: str

    # ── Google Gemini ────────────────────────────────────────────────────
    google_api_key: str | None
    google_chat_model: str

    # ── Offline embeddings (only when embedding_provider = "local") ─────
    local_embedding_model: str

    # ── Job search ───────────────────────────────────────────────────────
    job_source: str
    adzuna_app_id: str | None
    adzuna_app_key: str | None
    adzuna_country: str
    jsearch_api_key: str | None
    max_results: int
    max_llm_rankings: int
    max_upload_bytes: int


def _build_settings() -> Settings:
    return Settings(
        llm_provider=_env_lower("LLM_PROVIDER", "google"),
        embedding_provider=_resolved_embedding_provider(),
        openai_api_key=_strip_or_none(os.getenv("OPENAI_API_KEY")),
        openai_chat_model=os.getenv("OPENAI_CHAT_MODEL", "gpt-4o").strip(),
        openai_embedding_model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small").strip(),
        google_api_key=_strip_or_none(os.getenv("GOOGLE_API_KEY")),
        google_chat_model=os.getenv("GOOGLE_CHAT_MODEL", "gemini-2.5-flash").strip(),
        local_embedding_model=os.getenv("LOCAL_EMBEDDING_MODEL", "all-MiniLM-L6-v2").strip(),
        job_source=_env_lower("JOB_SOURCE", "mock"),
        adzuna_app_id=_strip_or_none(os.getenv("ADZUNA_APP_ID")),
        adzuna_app_key=_strip_or_none(os.getenv("ADZUNA_APP_KEY")),
        adzuna_country=os.getenv("ADZUNA_COUNTRY", "in").strip() or "in",
        jsearch_api_key=_strip_or_none(os.getenv("JSEARCH_API_KEY")),
        max_results=int(os.getenv("MAX_RESULTS", "10")),
        max_llm_rankings=int(os.getenv("MAX_LLM_RANKINGS", "5")),
        max_upload_bytes=int(os.getenv("MAX_UPLOAD_MB", "2")) * 1024 * 1024,
    )


SETTINGS = _build_settings()
