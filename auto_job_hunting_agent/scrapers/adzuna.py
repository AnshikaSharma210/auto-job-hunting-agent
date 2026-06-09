from __future__ import annotations

import hashlib
import logging
from urllib.parse import urlencode

import requests

from auto_job_hunting_agent.config import SETTINGS
from auto_job_hunting_agent.models import JobPosting

logger = logging.getLogger(__name__)

_BASE = "https://api.adzuna.com/v1/api/jobs/{country}/search/1"


def search_adzuna_jobs(
    role: str,
    location: str,
    salary_min_lpa: float | None = None,
    max_results: int | None = None,
) -> list[JobPosting]:
    if not SETTINGS.adzuna_app_id or not SETTINGS.adzuna_app_key:
        raise ValueError(
            "ADZUNA_APP_ID and ADZUNA_APP_KEY are required. "
            "Sign up free at https://developer.adzuna.com/"
        )

    n = max_results or SETTINGS.max_results
    params: dict = {
        "app_id": SETTINGS.adzuna_app_id,
        "app_key": SETTINGS.adzuna_app_key,
        "what": role.strip(),
        "where": location.strip(),
        "results_per_page": min(n, 50),
        "content-type": "application/json",
    }
    if salary_min_lpa and salary_min_lpa > 0:
        # Adzuna uses annual salary in local currency; convert LPA (lakhs) to units
        # 1 LPA = 100,000 INR
        params["salary_min"] = int(salary_min_lpa * 100_000)

    url = _BASE.format(country=SETTINGS.adzuna_country)
    resp = requests.get(url, params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()

    jobs: list[JobPosting] = []
    for item in data.get("results", []):
        title = item.get("title", "").strip()
        company = (item.get("company") or {}).get("display_name") or None
        loc_data = item.get("location") or {}
        loc_parts = loc_data.get("area") or []
        loc_text = ", ".join(loc_parts) if loc_parts else location
        salary_min = item.get("salary_min")
        salary_max = item.get("salary_max")
        salary_text: str | None = None
        if salary_min or salary_max:
            s_min = f"₹{int(salary_min):,}" if salary_min else ""
            s_max = f"₹{int(salary_max):,}" if salary_max else ""
            salary_text = " – ".join(x for x in (s_min, s_max) if x) or None

        redirect_url = item.get("redirect_url") or item.get("adref") or ""
        description = item.get("description") or ""

        jid = hashlib.sha256(
            f"adzuna:{title}:{company or ''}:{redirect_url}".encode()
        ).hexdigest()[:20]

        jobs.append(
            JobPosting(
                id=jid,
                platform="adzuna",
                title=title,
                company=company,
                location=loc_text,
                salary_text=salary_text,
                url=redirect_url,
                description=description,
            )
        )
    return jobs
