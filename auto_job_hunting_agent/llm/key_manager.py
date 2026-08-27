"""
LLM key management with automatic provider selection.

Priority order (both invoke functions):
  1. Groq  (GROQ_API_KEY, GROQ_API_KEY_2 … GROQ_API_KEY_9)
     — No daily quota. Per-minute limits that reset every 60 s.
     — Multiple keys from different accounts rotate automatically.
     — Get free key at https://console.groq.com (60 seconds to sign up)
  2. Google Gemini (GOOGLE_API_KEY, GOOGLE_API_KEY_2 … GOOGLE_API_KEY_9)
     — 1,500 req/day free per account, resets at midnight UTC

Groq is tried first because it has no daily cap and is faster.
When one Groq key hits its per-minute limit, the next key is tried automatically.
Gemini is the fallback in case all Groq keys are rate-limited simultaneously.
"""
from __future__ import annotations

import contextvars
import logging
import os
import time
from typing import Any, Type

from pydantic import BaseModel

logger = logging.getLogger(__name__)

_QUOTA_SIGNALS = ("quota", "exhausted", "rate", "429", "resource", "too many", "limit", "not found", "404")

# ── Session quota cache: skip hammering exhausted Gemini keys ─────────────────
_gemini_exhausted_until: float = 0.0
_GEMINI_CACHE_TTL = 120  # 2 min cache — re-check after this in case quota reset

# ── Per-key Groq rate-limit cache: skip a key for 60 s after it hits RPM ─────
_groq_key_blocked_until: dict[str, float] = {}
_GROQ_BLOCK_TTL = 62  # slightly over 60 s to ensure the window has reset

# ── Per-session BYOK overrides (thread-safe via contextvars) ──────────────────
# Each Streamlit user session runs in its own thread/context, so these are
# safely isolated and never bleed between users.
_ctx_groq_keys: contextvars.ContextVar[list[str]] = contextvars.ContextVar(
    "session_groq_keys", default=[]
)
_ctx_google_keys: contextvars.ContextVar[list[str]] = contextvars.ContextVar(
    "session_google_keys", default=[]
)


def set_session_keys(groq_keys: list[str] = (), google_keys: list[str] = ()) -> None:
    """
    Inject per-user BYOK keys for this Streamlit session.
    Call this once per page render with the keys from st.session_state.
    These override the host's env-var keys for ALL LLM calls made in this session.
    """
    _ctx_groq_keys.set([k for k in groq_keys if k.strip()])
    _ctx_google_keys.set([k for k in google_keys if k.strip()])


def _is_quota_error(exc: Exception) -> bool:
    s = str(exc).lower()
    return any(k in s for k in _QUOTA_SIGNALS)


def _gemini_all_exhausted() -> bool:
    return time.time() < _gemini_exhausted_until


def _mark_gemini_exhausted() -> None:
    global _gemini_exhausted_until
    _gemini_exhausted_until = time.time() + _GEMINI_CACHE_TTL
    logger.warning("All Gemini keys exhausted — will retry after cache TTL.")


def _groq_key_blocked(key: str) -> bool:
    until = _groq_key_blocked_until.get(key, 0.0)
    return time.time() < until


def _block_groq_key(key: str) -> None:
    _groq_key_blocked_until[key] = time.time() + _GROQ_BLOCK_TTL
    logger.warning("Groq key ...%s rate-limited — skipping for %ds.", key[-6:], _GROQ_BLOCK_TTL)


# ── Key pools ─────────────────────────────────────────────────────────────────

def get_google_keys() -> list[str]:
    """Collect GOOGLE_API_KEY, GOOGLE_API_KEY_2 … GOOGLE_API_KEY_9 (deduplicated)."""
    candidates: list[str] = []
    for suffix in [""] + [f"_{i}" for i in range(2, 10)]:
        k = os.getenv(f"GOOGLE_API_KEY{suffix}", "").strip()
        if k:
            candidates.append(k)
    seen: set[str] = set()
    return [k for k in candidates if k not in seen and not seen.add(k)]  # type: ignore[func-returns-value]


def get_groq_keys() -> list[str]:
    """Collect GROQ_API_KEY, GROQ_API_KEY_2 … GROQ_API_KEY_9 (deduplicated)."""
    candidates: list[str] = []
    for suffix in [""] + [f"_{i}" for i in range(2, 10)]:
        k = os.getenv(f"GROQ_API_KEY{suffix}", "").strip()
        if k:
            candidates.append(k)
    # Also check SETTINGS for the primary key
    try:
        from auto_job_hunting_agent.config import SETTINGS
        if SETTINGS.groq_api_key and SETTINGS.groq_api_key not in candidates:
            candidates.insert(0, SETTINGS.groq_api_key)
    except Exception:
        pass
    seen: set[str] = set()
    return [k for k in candidates if k not in seen and not seen.add(k)]  # type: ignore[func-returns-value]


def _get_groq_model() -> str:
    try:
        from auto_job_hunting_agent.config import SETTINGS
        return SETTINGS.groq_model or "llama-3.3-70b-versatile"
    except Exception:
        return "llama-3.3-70b-versatile"


# ── Groq helpers (with key rotation) ─────────────────────────────────────────

def _groq_invoke(messages: list, temperature: float = 0.2):
    """Try all configured Groq keys in order; block rate-limited keys for 62 s."""
    from langchain_groq import ChatGroq
    keys = get_groq_keys()
    if not keys:
        raise RuntimeError("no_groq_key")
    last_exc: Exception | None = None
    for key in keys:
        if _groq_key_blocked(key):
            logger.debug("Groq key ...%s still rate-limited, skipping.", key[-6:])
            continue
        try:
            llm = ChatGroq(model=_get_groq_model(), groq_api_key=key, temperature=temperature)
            return llm.invoke(messages)
        except Exception as exc:
            last_exc = exc
            if _is_quota_error(exc):
                _block_groq_key(key)
            else:
                raise  # non-rate-limit error — propagate immediately
    if last_exc:
        raise last_exc
    raise RuntimeError("no_groq_key")


def _groq_invoke_structured(messages: list, schema: Type[BaseModel], temperature: float = 0.2) -> Any:
    """Structured output Groq call with key rotation."""
    from langchain_groq import ChatGroq
    keys = get_groq_keys()
    if not keys:
        raise RuntimeError("no_groq_key")
    last_exc: Exception | None = None
    for key in keys:
        if _groq_key_blocked(key):
            logger.debug("Groq key ...%s still rate-limited, skipping.", key[-6:])
            continue
        try:
            llm = ChatGroq(model=_get_groq_model(), groq_api_key=key, temperature=temperature)
            return llm.with_structured_output(schema).invoke(messages)
        except Exception as exc:
            last_exc = exc
            if _is_quota_error(exc):
                _block_groq_key(key)
            else:
                raise
    if last_exc:
        raise last_exc
    raise RuntimeError("no_groq_key")


# ── Gemini helpers ────────────────────────────────────────────────────────────

def _gemini_invoke(messages: list, model: str, temperature: float = 0.2):
    """Try all Gemini keys; raises on exhaustion."""
    from langchain_google_genai import ChatGoogleGenerativeAI

    if _gemini_all_exhausted():
        raise RuntimeError("gemini_cache_exhausted")

    keys = get_google_keys()
    if not keys:
        raise RuntimeError("no_gemini_key")

    last_exc: Exception | None = None
    all_quota = True
    for i, key in enumerate(keys):
        try:
            llm = ChatGoogleGenerativeAI(
                model=model,
                google_api_key=key,
                temperature=temperature,
                convert_system_message_to_human=True,
                request_timeout=25,
            )
            result = llm.invoke(messages)
            if i > 0:
                logger.info("Gemini key #%d succeeded.", i + 1)
            return result
        except Exception as exc:
            last_exc = exc
            if not _is_quota_error(exc):
                all_quota = False
            logger.warning("Gemini key #%d failed: %s", i + 1, type(exc).__name__)

    if all_quota and keys:
        _mark_gemini_exhausted()
    raise last_exc or RuntimeError("All Gemini keys failed.")


def _gemini_invoke_structured(messages: list, schema: Type[BaseModel], model: str, temperature: float = 0.2) -> Any:
    """Structured output Gemini call with key rotation."""
    from langchain_google_genai import ChatGoogleGenerativeAI

    if _gemini_all_exhausted():
        raise RuntimeError("gemini_cache_exhausted")

    keys = get_google_keys()
    if not keys:
        raise RuntimeError("no_gemini_key")

    last_exc: Exception | None = None
    all_quota = True
    for i, key in enumerate(keys):
        try:
            llm = ChatGoogleGenerativeAI(
                model=model,
                google_api_key=key,
                temperature=temperature,
                convert_system_message_to_human=True,
                request_timeout=25,
            ).with_structured_output(schema)
            result = llm.invoke(messages)
            if i > 0:
                logger.info("Gemini key #%d succeeded (structured).", i + 1)
            return result
        except Exception as exc:
            last_exc = exc
            if not _is_quota_error(exc):
                all_quota = False
            logger.warning("Gemini key #%d failed (structured): %s", i + 1, type(exc).__name__)

    if all_quota and keys:
        _mark_gemini_exhausted()
    raise last_exc or RuntimeError("All Gemini keys failed (structured).")


# ── Public API ────────────────────────────────────────────────────────────────

def invoke_with_key_rotation(messages: list, model: str, temperature: float = 0.2):
    """
    Try all Groq keys first (no daily quota, per-key per-minute limit).
    Falls back to Gemini if all Groq keys are rate-limited.
    """
    last_exc: Exception | None = None

    # ── Step 1: Groq rotation ─────────────────────────────────────────────
    if get_groq_keys():
        try:
            logger.debug("Using Groq (preferred).")
            return _groq_invoke(messages, temperature)
        except RuntimeError as e:
            if "no_groq_key" not in str(e):
                last_exc = e
                logger.warning("All Groq keys exhausted/failed, trying Gemini: %s", type(e).__name__)
        except Exception as exc:
            last_exc = exc
            logger.warning("Groq failed (%s), trying Gemini.", type(exc).__name__)

    # ── Step 2: Gemini fallback ────────────────────────────────────────────
    gemini_keys = get_google_keys()
    if gemini_keys:
        try:
            return _gemini_invoke(messages, model, temperature)
        except RuntimeError as e:
            if "no_gemini_key" not in str(e) and "gemini_cache_exhausted" not in str(e):
                last_exc = e
        except Exception as exc:
            last_exc = exc

    # ── Both failed ────────────────────────────────────────────────────────
    if last_exc:
        raise RuntimeError(f"Both Groq and Gemini failed. Last error: {last_exc}") from last_exc
    raise RuntimeError(
        "No LLM provider available. Add GROQ_API_KEY (free at console.groq.com) "
        "or GOOGLE_API_KEY (free at aistudio.google.com) to your .env file."
    )


def invoke_structured_with_rotation(
    messages: list,
    schema: Type[BaseModel],
    model: str,
    temperature: float = 0.2,
) -> Any:
    """
    Structured output — all Groq keys first, Gemini fallback.
    """
    last_exc: Exception | None = None

    # ── Step 1: Groq rotation ─────────────────────────────────────────────
    if get_groq_keys():
        try:
            logger.debug("Using Groq structured (preferred).")
            return _groq_invoke_structured(messages, schema, temperature)
        except RuntimeError as e:
            if "no_groq_key" not in str(e):
                last_exc = e
                logger.warning("All Groq keys exhausted/failed, trying Gemini: %s", type(e).__name__)
        except Exception as exc:
            last_exc = exc
            logger.warning("Groq structured failed (%s), trying Gemini.", type(exc).__name__)

    # ── Step 2: Gemini fallback ────────────────────────────────────────────
    gemini_keys = get_google_keys()
    if gemini_keys:
        try:
            return _gemini_invoke_structured(messages, schema, model, temperature)
        except RuntimeError as e:
            if "no_gemini_key" not in str(e) and "gemini_cache_exhausted" not in str(e):
                last_exc = e
        except Exception as exc:
            last_exc = exc

    # ── Both failed ────────────────────────────────────────────────────────
    if last_exc:
        raise RuntimeError(f"Both Groq and Gemini failed. Last error: {last_exc}") from last_exc
    raise RuntimeError(
        "No LLM provider available. Add GROQ_API_KEY (free at console.groq.com) "
        "or GOOGLE_API_KEY (free at aistudio.google.com) to your .env file."
    )


def build_google_llm_with_rotation(model: str, temperature: float = 0.2):
    """Build a Gemini LLM for direct use (uses first available key)."""
    from langchain_google_genai import ChatGoogleGenerativeAI
    keys = get_google_keys()
    if not keys:
        raise RuntimeError(
            "No Google API key found. Add GOOGLE_API_KEY to .env or enter it in the sidebar."
        )
    return ChatGoogleGenerativeAI(
        model=model,
        google_api_key=keys[0],
        temperature=temperature,
        convert_system_message_to_human=True,
    )
