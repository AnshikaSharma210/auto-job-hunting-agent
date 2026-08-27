"""
Jobicy — free remote jobs API, no API key required.
https://jobicy.com/api/v2/remote-jobs

Covers software, data, devops, QA and other tech disciplines.
"""
from __future__ import annotations

import hashlib
import logging
import re

import requests

from auto_job_hunting_agent.models import JobPosting

logger = logging.getLogger(__name__)

_URL = "https://jobicy.com/api/v2/remote-jobs"


def search_jobicy_jobs(roles: list[str], max_results: int = 20) -> list[JobPosting]:
    """
    Fetch from Jobicy remote jobs API and return matching postings.
    No API key required. Focused on remote-only roles.
    """
    try:
        resp = requests.get(
            _URL,
            params={"count": min(max_results * 3, 50)},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning("Jobicy fetch error: %s", exc)
        return []

    # Collect individual role words for title filtering (min length 2 to catch "ai", "qa")
    role_words: set[str] = set()
    _stop = {"and", "the", "for", "with", "senior", "junior", "lead", "staff", "or", "of"}
    for role in roles:
        for w in re.findall(r"[a-z]+", role.lower()):
            if len(w) >= 2 and w not in _stop:
                role_words.add(w)

    jobs: list[JobPosting] = []
    for item in (data.get("jobs") or []):
        title = (item.get("jobTitle") or "").strip()
        if not title:
            continue
        # loose filter: allow if any role word in title
        if role_words and not any(w in title.lower() for w in role_words):
            continue

        company = (item.get("companyName") or "").strip() or None
        location = (item.get("jobGeo") or "Remote").strip()
        url = item.get("url") or ""
        description = (item.get("jobExcerpt") or "") + " " + (item.get("jobDescription") or "")
        description = re.sub(r"<[^>]+>", " ", description)
        description = re.sub(r"\s{2,}", " ", description).strip()[:3000]

        salary_text: str | None = None
        salary_raw = (item.get("jobSalary") or "").strip()
        if salary_raw and salary_raw.lower() not in ("not listed", "n/a", "—"):
            salary_text = salary_raw

        jid = hashlib.sha256(f"jobicy:{title}:{company or ''}:{url}".encode()).hexdigest()[:20]
        jobs.append(
            JobPosting(
                id=jid,
                platform="jobicy",
                title=title,
                company=company,
                location=location,
                salary_text=salary_text,
                url=url,
                description=description,
            )
        )

    return jobs[:max_results]
