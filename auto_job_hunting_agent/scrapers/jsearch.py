from __future__ import annotations

import hashlib
import logging

import requests

from auto_job_hunting_agent.config import SETTINGS
from auto_job_hunting_agent.models import JobPosting

logger = logging.getLogger(__name__)

_JSEARCH_URL = "https://jsearch.p.rapidapi.com/search"


def search_jsearch_jobs(
    role: str,
    location: str,
    salary_min_lpa: float | None = None,
    max_results: int | None = None,
) -> list[JobPosting]:
    """
    JSearch via RapidAPI — aggregates LinkedIn, Indeed, Glassdoor, ZipRecruiter.
    Free tier: 200 requests / month.  Sign up at https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch
    """
    if not SETTINGS.jsearch_api_key:
        raise ValueError(
            "JSEARCH_API_KEY is required. "
            "Get a free key at https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch"
        )

    n = max_results or SETTINGS.max_results
    # Clean query: "SDE Pune" not "SDE in remote" — location is already a city/region
    location_clean = location.strip()
    query = f"{role.strip()} {location_clean}" if location_clean else role.strip()

    headers = {
        "X-RapidAPI-Key": SETTINGS.jsearch_api_key,
        "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
    }
    params: dict = {
        "query": query,
        "num_pages": "1",
        "page": "1",
        "date_posted": "month",
    }

    resp = requests.get(_JSEARCH_URL, headers=headers, params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()

    jobs: list[JobPosting] = []
    for item in (data.get("data") or [])[:n]:
        title = (item.get("job_title") or "").strip()
        company = (item.get("employer_name") or "").strip() or None
        city = item.get("job_city") or ""
        state = item.get("job_state") or ""
        country = item.get("job_country") or ""
        loc_parts = [p for p in (city, state, country) if p]
        loc_text = ", ".join(loc_parts) if loc_parts else location

        salary_text: str | None = None
        s_min = item.get("job_min_salary")
        s_max = item.get("job_max_salary")
        s_period = item.get("job_salary_period") or ""
        if s_min or s_max:
            lo = f"{int(s_min):,}" if s_min else ""
            hi = f"{int(s_max):,}" if s_max else ""
            salary_text = " – ".join(x for x in (lo, hi) if x)
            if s_period:
                salary_text += f" / {s_period}"

        url = item.get("job_apply_link") or item.get("job_url") or ""
        description = item.get("job_description") or ""
        platform_raw = (item.get("job_publisher") or "jsearch").lower()
        # Normalise publisher names to recognisable platform labels
        platform = _normalise_platform(platform_raw)

        jid = hashlib.sha256(
            f"jsearch:{title}:{company or ''}:{url}".encode()
        ).hexdigest()[:20]

        jobs.append(
            JobPosting(
                id=jid,
                platform=platform,
                title=title,
                company=company,
                location=loc_text,
                salary_text=salary_text,
                url=url,
                description=description,
            )
        )
    return jobs


def _normalise_platform(raw: str) -> str:
    for name in ("linkedin", "indeed", "glassdoor", "ziprecruiter", "naukri", "monster"):
        if name in raw:
            return name
    return "jsearch"
