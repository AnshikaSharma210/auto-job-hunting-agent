"""
Supabase database and auth wrapper for Job Hunt Pro.

When SUPABASE_URL / SUPABASE_ANON_KEY are not configured the app runs in
"local mode" — all functions are safe no-ops that return empty data, and the
app falls back to session state + local file storage (original behaviour for
local development and plain Streamlit runs without a database).
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_client: Any = None


# ── Availability check ────────────────────────────────────────────────────────

def is_supabase_configured() -> bool:
    """True when both SUPABASE_URL and SUPABASE_ANON_KEY are present."""
    try:
        from auto_job_hunting_agent.config import SETTINGS
        return bool(
            getattr(SETTINGS, "supabase_url", None)
            and getattr(SETTINGS, "supabase_anon_key", None)
        )
    except Exception:
        return False


def get_client() -> Any:
    """Return a singleton Supabase client (lazily initialised)."""
    global _client
    if _client is not None:
        return _client
    from supabase import create_client
    from auto_job_hunting_agent.config import SETTINGS
    _client = create_client(SETTINGS.supabase_url, SETTINGS.supabase_anon_key)
    return _client


# ── Auth ──────────────────────────────────────────────────────────────────────

def sign_up(email: str, password: str) -> dict:
    """Register a new user. Returns {"user": ..., "session": ..., "error": ...}"""
    try:
        resp = get_client().auth.sign_up({"email": email, "password": password})
        return {"user": resp.user, "session": resp.session, "error": None}
    except Exception as exc:
        return {"user": None, "session": None, "error": _clean_error(exc)}


def sign_in(email: str, password: str) -> dict:
    """Sign in an existing user. Returns {"user": ..., "session": ..., "error": ...}"""
    try:
        resp = get_client().auth.sign_in_with_password({"email": email, "password": password})
        return {"user": resp.user, "session": resp.session, "error": None}
    except Exception as exc:
        return {"user": None, "session": None, "error": _clean_error(exc)}


def sign_out() -> None:
    try:
        get_client().auth.sign_out()
    except Exception:
        pass


def get_user(access_token: str) -> Any | None:
    """Validate an existing JWT and return the user object (or None if expired)."""
    try:
        resp = get_client().auth.get_user(access_token)
        return resp.user
    except Exception:
        return None


# ── Resume metadata ───────────────────────────────────────────────────────────

def save_resume_meta(
    user_id: str,
    raw_text: str,
    roles: str,
    years_experience: float,
    ats_results: dict | None = None,
) -> None:
    """Upsert (one row per user) resume text + ATS scores."""
    try:
        get_client().table("resume_meta").upsert(
            {
                "user_id": user_id,
                "raw_text": raw_text,
                "roles": roles,
                "years_experience": years_experience,
                "ats_results": ats_results or {},
            },
            on_conflict="user_id",
        ).execute()
    except Exception as exc:
        logger.warning("save_resume_meta failed: %s", exc)


def load_resume_meta(user_id: str) -> dict | None:
    """Return the stored resume row for this user, or None."""
    try:
        resp = (
            get_client()
            .table("resume_meta")
            .select("*")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None
    except Exception as exc:
        logger.warning("load_resume_meta failed: %s", exc)
        return None


def upload_resume_file(user_id: str, file_bytes: bytes, filename: str = "resume.pdf") -> str | None:
    """Upload resume PDF to Supabase Storage. Returns the storage path on success."""
    try:
        path = f"{user_id}/{filename}"
        get_client().storage.from_("resumes").upload(
            path,
            file_bytes,
            file_options={"upsert": "true", "content-type": "application/pdf"},
        )
        return path
    except Exception as exc:
        logger.warning("upload_resume_file failed: %s", exc)
        return None


def download_resume_file(storage_path: str) -> bytes | None:
    """Download a resume PDF from Supabase Storage."""
    try:
        return get_client().storage.from_("resumes").download(storage_path)
    except Exception as exc:
        logger.warning("download_resume_file failed: %s", exc)
        return None


# ── Shortlist ─────────────────────────────────────────────────────────────────

def load_shortlist(user_id: str) -> list[dict]:
    """Return all shortlisted jobs for this user."""
    try:
        resp = (
            get_client()
            .table("shortlist")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=False)
            .execute()
        )
        return resp.data or []
    except Exception as exc:
        logger.warning("load_shortlist failed: %s", exc)
        return []


def upsert_shortlist(user_id: str, job_id: str, job_data: dict, match_data: dict) -> None:
    """Insert or update a shortlisted job (identified by job_data->>'id')."""
    try:
        existing = (
            get_client()
            .table("shortlist")
            .select("id")
            .eq("user_id", user_id)
            .eq("job_data->>id", job_id)
            .execute()
        )
        if existing.data:
            get_client().table("shortlist").update(
                {"job_data": job_data, "match_data": match_data}
            ).eq("id", existing.data[0]["id"]).execute()
        else:
            get_client().table("shortlist").insert(
                {"user_id": user_id, "job_data": job_data, "match_data": match_data}
            ).execute()
    except Exception as exc:
        logger.warning("upsert_shortlist failed: %s", exc)


def delete_shortlist_item(user_id: str, job_id: str) -> None:
    """Remove a job from the user's shortlist."""
    try:
        get_client().table("shortlist").delete().eq("user_id", user_id).eq(
            "job_data->>id", job_id
        ).execute()
    except Exception as exc:
        logger.warning("delete_shortlist_item failed: %s", exc)


# ── Applications ──────────────────────────────────────────────────────────────

def load_applications_db(user_id: str) -> list[dict]:
    """Return all application records for this user, newest first."""
    try:
        resp = (
            get_client()
            .table("applications")
            .select("*")
            .eq("user_id", user_id)
            .order("applied_at", desc=True)
            .execute()
        )
        return resp.data or []
    except Exception as exc:
        logger.warning("load_applications_db failed: %s", exc)
        return []


def add_application_db(user_id: str, record: dict) -> None:
    """Insert or update an application record."""
    try:
        payload = {**record, "user_id": user_id}
        get_client().table("applications").upsert(payload, on_conflict="id").execute()
    except Exception as exc:
        logger.warning("add_application_db failed: %s", exc)


def update_application_status_db(user_id: str, app_id: str, status: str) -> None:
    """Update the status field of one application."""
    try:
        get_client().table("applications").update({"status": status}).eq(
            "id", app_id
        ).eq("user_id", user_id).execute()
    except Exception as exc:
        logger.warning("update_application_status_db failed: %s", exc)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _clean_error(exc: Exception) -> str:
    """Return a user-friendly error string from a Supabase exception."""
    msg = str(exc)
    if "Invalid login credentials" in msg:
        return "Incorrect email or password."
    if "User already registered" in msg or "already exists" in msg.lower():
        return "An account with this email already exists. Please log in."
    if "Email not confirmed" in msg:
        return "Please check your email and click the confirmation link first."
    if "Password should be" in msg:
        return "Password must be at least 6 characters."
    return msg.split("(")[0].strip()
