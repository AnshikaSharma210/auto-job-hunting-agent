from __future__ import annotations


def apply_result_for_job(url: str | None, dry_run: bool = False) -> dict:
    """
    HITL apply: no automation.  Returns metadata the UI uses to surface
    a link-button and mark the application as dispatched.
    """
    if not url or url.startswith("https://example.com"):
        return {"ok": False, "reason": "No real URL available (mock listing)."}
    return {"ok": True, "url": url, "dry_run": dry_run}
