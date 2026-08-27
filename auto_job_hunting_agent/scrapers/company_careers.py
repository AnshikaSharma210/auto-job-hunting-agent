"""
Direct company career-page scraper using free, public, no-auth ATS APIs.

Supported platforms:
  Greenhouse  — boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true
  Lever       — api.lever.co/v0/postings/{slug}?mode=json
  Ashby       — api.ashbyhq.com/posting-api/job-board/{slug}

All three APIs are public, read-only, require no authentication, and are the
same endpoints each company uses to power their embedded careers widget.
"""
from __future__ import annotations

import hashlib
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

import requests

from auto_job_hunting_agent.models import JobPosting
from auto_job_hunting_agent.scrapers.company_list import COMPANY_ATS_MAP

logger = logging.getLogger(__name__)

_TIMEOUT = 12
_MAX_WORKERS = 16

# ── per-platform fetchers ─────────────────────────────────────────────────────


def _fetch_greenhouse(company: str, slug: str) -> list[JobPosting]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    try:
        resp = requests.get(url, params={"content": "true"}, timeout=_TIMEOUT)
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.debug("Greenhouse %s/%s error: %s", company, slug, exc)
        return []

    jobs: list[JobPosting] = []
    for item in data.get("jobs") or []:
        title = (item.get("title") or "").strip()
        location = (item.get("location") or {}).get("name") or "See listing"
        apply_url = item.get("absolute_url") or ""
        description = _strip_html(item.get("content") or "")
        jid = hashlib.sha256(f"gh:{slug}:{item.get('id', title)}".encode()).hexdigest()[:20]
        jobs.append(
            JobPosting(
                id=jid,
                platform="greenhouse",
                title=title,
                company=company,
                location=location,
                salary_text=None,
                url=apply_url,
                description=description[:3000],
            )
        )
    return jobs


def _fetch_lever(company: str, slug: str) -> list[JobPosting]:
    url = f"https://api.lever.co/v0/postings/{slug}"
    try:
        resp = requests.get(url, params={"mode": "json"}, timeout=_TIMEOUT)
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.debug("Lever %s/%s error: %s", company, slug, exc)
        return []

    jobs: list[JobPosting] = []
    for item in data or []:
        title = (item.get("text") or "").strip()
        cats = item.get("categories") or {}
        location = cats.get("location") or cats.get("allLocations") or "See listing"
        if isinstance(location, list):
            location = ", ".join(location)
        apply_url = item.get("hostedUrl") or item.get("applyUrl") or ""

        # Build description from lists sections
        desc_parts: list[str] = []
        for lst in item.get("lists") or []:
            heading = lst.get("text") or ""
            content = _strip_html(lst.get("content") or "")
            if heading:
                desc_parts.append(f"{heading}: {content}")
            else:
                desc_parts.append(content)
        description = " | ".join(desc_parts)[:3000]

        salary_text: str | None = None
        salary_range = item.get("salaryRange") or {}
        if salary_range.get("min") or salary_range.get("max"):
            lo = salary_range.get("min") or ""
            hi = salary_range.get("max") or ""
            currency = salary_range.get("currency") or ""
            interval = salary_range.get("interval") or ""
            salary_text = f"{currency}{lo}–{hi} / {interval}".strip(" /") or None

        jid = hashlib.sha256(f"lever:{slug}:{item.get('id', title)}".encode()).hexdigest()[:20]
        jobs.append(
            JobPosting(
                id=jid,
                platform="lever",
                title=title,
                company=company,
                location=location,
                salary_text=salary_text,
                url=apply_url,
                description=description,
            )
        )
    return jobs


def _fetch_ashby(company: str, slug: str) -> list[JobPosting]:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
    try:
        resp = requests.get(url, params={"includeCompensation": "true"}, timeout=_TIMEOUT)
        if resp.status_code in (404, 422):
            return []
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.debug("Ashby %s/%s error: %s", company, slug, exc)
        return []

    jobs: list[JobPosting] = []
    for item in (data.get("jobPostings") or []):
        title = (item.get("title") or "").strip()
        location = (item.get("location") or "Remote").strip()
        apply_url = item.get("jobUrl") or item.get("applyUrl") or ""
        description = _strip_html(item.get("descriptionHtml") or item.get("description") or "")[:3000]

        salary_text: str | None = None
        comp = item.get("compensation") or {}
        if comp.get("summaryComponents"):
            parts = [c.get("label") or "" for c in comp["summaryComponents"] if c.get("label")]
            salary_text = " | ".join(parts) or None

        jid = hashlib.sha256(f"ashby:{slug}:{item.get('id', title)}".encode()).hexdigest()[:20]
        jobs.append(
            JobPosting(
                id=jid,
                platform="ashby",
                title=title,
                company=company,
                location=location,
                salary_text=salary_text,
                url=apply_url,
                description=description,
            )
        )
    return jobs


# ── public entry point ────────────────────────────────────────────────────────

def search_company_careers(
    role_keywords: list[str],
    max_per_company: int = 5,
    extra_companies: dict[str, dict[str, str]] | None = None,
    progress: Callable[[str], None] | None = None,
) -> list[JobPosting]:
    """
    Query all companies in COMPANY_ATS_MAP (plus any extra_companies) in parallel
    and return postings whose title matches at least one role keyword.

    role_keywords: list of strings to match against job title (case-insensitive OR).
    """
    all_companies = {**COMPANY_ATS_MAP, **(extra_companies or {})}
    # Build individual word tokens from role keywords for flexible matching
    _stop = {"and", "the", "for", "with", "or", "of", "in", "a"}
    kw_words: set[str] = set()
    for kw in role_keywords:
        for word in re.findall(r"[a-z]+", kw.lower()):
            if len(word) >= 2 and word not in _stop:  # len>=2 so "qa" is included
                kw_words.add(word)
    # Also keep full phrases for exact matches
    keywords_lower = [k.lower() for k in role_keywords if k.strip()]

    def _fetch_one(name: str, cfg: dict[str, str]) -> list[JobPosting]:
        ats = cfg.get("ats", "")
        slug = cfg.get("slug", "")
        if not slug:
            return []
        if ats == "greenhouse":
            all_jobs = _fetch_greenhouse(name, slug)
        elif ats == "lever":
            all_jobs = _fetch_lever(name, slug)
        elif ats == "ashby":
            all_jobs = _fetch_ashby(name, slug)
        else:
            return []
        # Filter by word-level keyword match in title (more flexible than phrase match)
        if not kw_words:
            return all_jobs[:max_per_company]
        matched = [
            j for j in all_jobs
            if any(w in j.title.lower() for w in kw_words)
        ]
        return matched[:max_per_company]

    results: list[JobPosting] = []
    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
        futures = {
            executor.submit(_fetch_one, name, cfg): name
            for name, cfg in all_companies.items()
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                batch = future.result()
                if batch:
                    results.extend(batch)
                    if progress:
                        progress(f"Found {len(batch)} opening(s) at {name}")
            except Exception as exc:
                logger.debug("Career page error for %s: %s", name, exc)

    return results


# ── utilities ─────────────────────────────────────────────────────────────────

def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()
