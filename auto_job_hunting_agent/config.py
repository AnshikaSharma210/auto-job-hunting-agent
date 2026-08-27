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


def _env_or_secret(name: str, default: str = "") -> str:
    """Read from .env first, then st.secrets (Streamlit Cloud), then default."""
    val = os.getenv(name, "").strip()
    if val:
        return val
    try:
        import streamlit as st  # noqa: PLC0415
        secret = st.secrets.get(name, "")
        if secret:
            return str(secret).strip()
    except Exception:
        pass
    return default


def _env_or_secret_lower(name: str, default: str) -> str:
    raw = _env_or_secret(name, "")
    return raw.lower() if raw else default


def _resolved_embedding_provider() -> str:
    """Default local embeddings to save Gemini quota; google only when explicitly set."""
    return _env_or_secret_lower("EMBEDDING_PROVIDER", "local")


@dataclass(frozen=True)
class Settings:
    # ── LLM provider: "openai" | "google" ────────────────────────────────
    llm_provider: str

    # ── Embedding provider: "google" | "openai" | "local" ───────────────
    embedding_provider: str

    # ── OpenAI ───────────────────────────────────────────────────────────
    openai_api_key: str | None
    openai_chat_model: str
    openai_embedding_model: str

    # ── Google Gemini ────────────────────────────────────────────────────
    google_api_key: str | None
    google_chat_model: str

    # ── Offline embeddings ───────────────────────────────────────────────
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

    # ── Extended sources (free, no auth) ─────────────────────────────────
    enable_remotive: bool
    enable_company_careers: bool
    company_list_extra: str

    # ── Groq (free, no daily quota — sign up at console.groq.com) ────────
    groq_api_key: str | None
    groq_model: str

    # ── Supabase (cloud multi-user mode) ─────────────────────────────────
    # Required for login + per-user persistence on hosted deployment.
    # Leave blank for local single-user development.
    supabase_url: str | None
    supabase_anon_key: str | None


def _build_settings() -> Settings:
    def _s(name: str, default: str = "") -> str:
        return _env_or_secret(name, default)

    def _sn(name: str) -> str | None:
        return _strip_or_none(_env_or_secret(name)) or None

    return Settings(
        llm_provider=_env_or_secret_lower("LLM_PROVIDER", "google"),
        embedding_provider=_resolved_embedding_provider(),
        openai_api_key=_sn("OPENAI_API_KEY"),
        openai_chat_model=_s("OPENAI_CHAT_MODEL", "gpt-4o"),
        openai_embedding_model=_s("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
        google_api_key=_sn("GOOGLE_API_KEY"),
        google_chat_model=_s("GOOGLE_CHAT_MODEL", "gemini-2.5-flash"),
        local_embedding_model=_s("LOCAL_EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
        job_source=_env_or_secret_lower("JOB_SOURCE", "multi"),
        adzuna_app_id=_sn("ADZUNA_APP_ID"),
        adzuna_app_key=_sn("ADZUNA_APP_KEY"),
        adzuna_country=_s("ADZUNA_COUNTRY", "in") or "in",
        jsearch_api_key=_sn("JSEARCH_API_KEY"),
        max_results=int(_s("MAX_RESULTS", "20")),
        max_llm_rankings=int(_s("MAX_LLM_RANKINGS", "5")),
        max_upload_bytes=int(_s("MAX_UPLOAD_MB", "2")) * 1024 * 1024,
        enable_remotive=_env_or_secret_lower("ENABLE_REMOTIVE", "true") == "true",
        enable_company_careers=_env_or_secret_lower("ENABLE_COMPANY_CAREERS", "true") == "true",
        company_list_extra=_s("COMPANY_LIST_EXTRA", ""),
        groq_api_key=_sn("GROQ_API_KEY"),
        groq_model=_s("GROQ_MODEL", "llama-3.3-70b-versatile"),
        supabase_url=_sn("SUPABASE_URL"),
        supabase_anon_key=_sn("SUPABASE_ANON_KEY"),
    )


SETTINGS = _build_settings()
