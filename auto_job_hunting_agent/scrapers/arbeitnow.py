"""
Arbeitnow — free public job board API, no API key required.
https://www.arbeitnow.com/api/job-board-api

Tech-focused, Europe + global, includes remote listings.
"""
from __future__ import annotations

import hashlib
import logging
import re

import requests

from auto_job_hunting_agent.models import JobPosting

logger = logging.getLogger(__name__)

_URL = "https://www.arbeitnow.com/api/job-board-api"


def search_arbeitnow_jobs(roles: list[str], max_results: int = 20) -> list[JobPosting]:
    """
    Fetch from Arbeitnow and filter client-side by role keywords.
    No API key required. Returns tech/startup jobs worldwide.
    """
    role_words: set[str] = set()
    _stop = {"and", "the", "for", "with", "senior", "junior", "lead", "staff", "or", "of"}
    for role in roles:
        for w in re.findall(r"[a-z]+", role.lower()):
            if len(w) >= 3 and w not in _stop:
                role_words.add(w)

    try:
        resp = requests.get(_URL, params={"page": 1}, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning("Arbeitnow fetch error: %s", exc)
        return []

    jobs: list[JobPosting] = []
    for item in (data.get("data") or []):
        title = (item.get("title") or "").strip()
        if not title:
            continue
        # filter by role keywords in title or tags
        tags_text = " ".join(item.get("tags") or []).lower()
        combined = f"{title} {tags_text}".lower()
        if role_words and not any(w in combined for w in role_words):
            continue

        company = (item.get("company_name") or "").strip() or None
        location = (item.get("location") or "").strip() or "See listing"
        if item.get("remote"):
            location = f"Remote — {location}" if location != "See listing" else "Remote"
        url = item.get("url") or ""

        # Strip HTML from description
        description = re.sub(r"<[^>]+>", " ", item.get("description") or "")
        description = re.sub(r"\s{2,}", " ", description).strip()[:3000]

        salary_text: str | None = None
        salary_raw = (item.get("salary") or "").strip()
        if salary_raw:
            salary_text = salary_raw or None

        jid = hashlib.sha256(f"arbeitnow:{title}:{company or ''}:{url}".encode()).hexdigest()[:20]
        jobs.append(
            JobPosting(
                id=jid,
                platform="arbeitnow",
                title=title,
                company=company,
                location=location,
                salary_text=salary_text,
                url=url,
                description=description,
            )
        )
        if len(jobs) >= max_results:
            break

    return jobs
