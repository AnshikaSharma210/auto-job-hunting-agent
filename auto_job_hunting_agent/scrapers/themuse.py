"""
The Muse public API — free, no authentication required.
https://www.themuse.com/api/public/jobs

Returns quality tech jobs from hundreds of global companies.
Useful for discovering openings at top-tier companies not listed elsewhere.
"""
from __future__ import annotations

import hashlib
import logging
import re

import requests

from auto_job_hunting_agent.models import JobPosting

logger = logging.getLogger(__name__)

_MUSE_URL = "https://www.themuse.com/api/public/jobs"
_TIMEOUT = 15

# Map role keywords to Muse category names
_ROLE_TO_CATEGORY: dict[str, str] = {
    "software": "Software Engineer",
    "developer": "Software Engineer",
    "engineer": "Software Engineer",
    "backend": "Software Engineer",
    "frontend": "Software Engineer",
    "fullstack": "Software Engineer",
    "qa": "QA",
    "quality": "QA",
    "test": "QA",
    "automation": "QA",
    "sdet": "QA",
    "data": "Data Science",
    "machine learning": "Data Science",
    "ml": "Data Science",
    "ai": "Data Science",
    "devops": "IT",
    "cloud": "IT",
    "sre": "IT",
    "product": "Product",
    "design": "Design & UX",
    "ux": "Design & UX",
    "android": "Mobile",
    "ios": "Mobile",
    "mobile": "Mobile",
}

_STRIP_HTML_RE = re.compile(r"<[^>]+>")


def _strip_html(html: str) -> str:
    text = _STRIP_HTML_RE.sub(" ", html)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def _pick_categories(roles: list[str]) -> list[str]:
    """Map role keywords to the best Muse category names (deduplicated)."""
    cats: list[str] = []
    seen: set[str] = set()
    for role in roles:
        role_l = role.lower()
        for kw, cat in _ROLE_TO_CATEGORY.items():
            if kw in role_l and cat not in seen:
                cats.append(cat)
                seen.add(cat)
    return cats or ["Software Engineer"]


def search_themuse_jobs(
    roles: list[str],
    location: str = "",
    max_results: int = 20,
) -> list[JobPosting]:
    """
    Fetch jobs from The Muse API matching the given roles.
    No API key required. 500 req/hr rate limit on the public API.
    """
    categories = _pick_categories(roles)
    jobs: list[JobPosting] = []
    seen_ids: set[str] = set()

    for category in categories[:2]:  # max 2 categories per search to stay fast
        try:
            params: dict = {
                "category": category,
                "page": 0,
                "descending": "true",
            }
            resp = requests.get(_MUSE_URL, params=params, timeout=_TIMEOUT)
            if resp.status_code != 200:
                logger.debug("The Muse: HTTP %s for category '%s'", resp.status_code, category)
                continue
            data = resp.json()
        except Exception as exc:
            logger.debug("The Muse error for category '%s': %s", category, exc)
            continue

        for item in (data.get("results") or [])[:max_results]:
            title = (item.get("name") or "").strip()
            if not title:
                continue

            company_obj = item.get("company") or {}
            company = (company_obj.get("name") or "").strip() or None

            locs = item.get("locations") or []
            loc_text = ", ".join(l.get("name", "") for l in locs if l.get("name")) or "See listing"

            apply_url = (item.get("refs") or {}).get("landing_page") or ""

            contents_raw = item.get("contents") or ""
            description = _strip_html(contents_raw)[:2000]

            jid = hashlib.sha256(
                f"muse:{item.get('id', title)}:{company or ''}".encode()
            ).hexdigest()[:20]

            if jid in seen_ids:
                continue
            seen_ids.add(jid)

            jobs.append(
                JobPosting(
                    id=jid,
                    platform="themuse",
                    title=title,
                    company=company,
                    location=loc_text,
                    salary_text=None,
                    url=apply_url,
                    description=description,
                )
            )

        if len(jobs) >= max_results:
            break

    return jobs[:max_results]
