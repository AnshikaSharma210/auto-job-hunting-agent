from __future__ import annotations

import hashlib
import logging

import requests

from auto_job_hunting_agent.models import JobPosting

logger = logging.getLogger(__name__)

_REMOTIVE_URL = "https://remotive.com/api/remote-jobs"


def search_remotive_jobs(
    role: str,
    max_results: int = 20,
) -> list[JobPosting]:
    """
    Remotive public API — 100% remote tech roles, no API key required.
    https://remotive.com/api/remote-jobs
    """
    try:
        params = {"search": role.strip(), "limit": max_results}
        resp = requests.get(_REMOTIVE_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning("Remotive fetch error: %s", exc)
        return []

    jobs: list[JobPosting] = []
    for item in (data.get("jobs") or [])[:max_results]:
        title = (item.get("title") or "").strip()
        company = (item.get("company_name") or "").strip() or None
        location = item.get("candidate_required_location") or "Remote"
        url = item.get("url") or ""
        description = item.get("description") or ""
        # Strip HTML tags from description (Remotive returns HTML)
        import re
        description = re.sub(r"<[^>]+>", " ", description)
        description = re.sub(r"\s{2,}", " ", description).strip()[:3000]

        salary_text: str | None = None
        salary_raw = item.get("salary") or ""
        if salary_raw:
            salary_text = salary_raw.strip() or None

        jid = hashlib.sha256(
            f"remotive:{title}:{company or ''}:{url}".encode()
        ).hexdigest()[:20]

        jobs.append(
            JobPosting(
                id=jid,
                platform="remotive",
                title=title,
                company=company,
                location=location,
                salary_text=salary_text,
                url=url,
                description=description,
            )
        )
    return jobs
