from __future__ import annotations

from openai import APIConnectionError, AuthenticationError, RateLimitError


_QUOTA_MSG = (
    "Your OpenAI account has no credits remaining. "
    "Add credits at [platform.openai.com/billing](https://platform.openai.com/billing) "
    "and try again (minimum $5 top-up is enough for many searches)."
)
_AUTH_MSG = (
    "OpenAI API key is invalid or expired. "
    "Check the key at [platform.openai.com/api-keys](https://platform.openai.com/api-keys) "
    "and update your `.env` file."
)
_CONN_MSG = (
    "Could not reach OpenAI — check your internet connection. "
    "If you are on a corporate network, ensure `truststore` is installed (`pip install truststore`)."
)


def friendly(exc: Exception) -> str:
    """Return a human-readable message for common provider errors."""
    if isinstance(exc, RateLimitError):
        body = getattr(exc, "body", {}) or {}
        code = (body.get("error") or {}).get("code", "")
        if code == "insufficient_quota":
            return _QUOTA_MSG
        return f"OpenAI rate limit hit — wait a moment and try again. ({exc})"
    if isinstance(exc, AuthenticationError):
        return _AUTH_MSG
    if isinstance(exc, APIConnectionError):
        return _CONN_MSG
    try:
        from google.api_core.exceptions import ResourceExhausted

        if isinstance(exc, ResourceExhausted):
            return (
                "The analysis service is currently busy. Please wait a little and try again."
            )
    except ImportError:
        pass
    try:
        from langchain_google_genai._common import GoogleGenerativeAIError

        if isinstance(exc, GoogleGenerativeAIError):
            return "The analysis service is temporarily unavailable. Please try again shortly."
    except ImportError:
        pass
    return str(exc)
