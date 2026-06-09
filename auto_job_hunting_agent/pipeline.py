from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Callable

from auto_job_hunting_agent.config import SETTINGS
from auto_job_hunting_agent.llm.ats_scoring import score_resume_ats
from auto_job_hunting_agent.llm.company_ranking import score_job_ranked
from auto_job_hunting_agent.llm.heuristic_ranking import heuristic_job_match
from auto_job_hunting_agent.models import ATSResumeScore, JobMatchResult, JobPosting
from auto_job_hunting_agent.rag.context_builder import build_structured_resume_context
from auto_job_hunting_agent.rag.resume_store import ResumeVectorStore
from auto_job_hunting_agent.scrapers.mock_data import mock_job_postings

logger = logging.getLogger(__name__)


@dataclass
class ScoredJob:
    job: JobPosting
    match: JobMatchResult


def _build_location_query(work_mode: str, location: str) -> str:
    mode = work_mode.strip().lower()
    loc = location.strip() or "India"
    if mode == "remote":
        return f"remote {loc}"
    if mode == "hybrid":
        return f"hybrid {loc}"
    return loc


def _parse_roles(roles_csv: str) -> list[str]:
    parts = [p.strip() for p in roles_csv.split(",") if p.strip()]
    return parts[:3] if parts else ["Software Engineer"]


def _extract_key_sections(resume_text: str, max_chars: int = 2500) -> str:
    """Return the most signal-rich sections (skills + experience + projects) to save tokens."""
    import re
    lower = resume_text.lower()
    section_starts: list[tuple[int, str]] = []
    patterns = {
        "skills": r"\b(skills|technical skills|tools|technologies|stack)\b",
        "experience": r"\b(experience|work history|employment|professional)\b",
        "projects": r"\b(projects?|portfolio)\b",
        "education": r"\b(education|academic|degree|university)\b",
    }
    for sec, pat in patterns.items():
        m = re.search(pat, lower)
        if m:
            section_starts.append((m.start(), sec))
    section_starts.sort()
    if not section_starts:
        return resume_text[:max_chars]
    # Grab text from first key section onward
    start = section_starts[0][0]
    return resume_text[start:start + max_chars]


@dataclass
class JobHuntPipeline:
    resume_store: ResumeVectorStore = field(default_factory=ResumeVectorStore)

    def score_resume_for_role(
        self, target_role: str, years_experience: float
    ) -> ATSResumeScore:
        if not self.resume_store.is_ready:
            raise RuntimeError("Upload a resume before ATS scoring.")
        # Use only the most relevant sections to save tokens
        resume_text = _extract_key_sections(self.resume_store.raw_resume)
        return score_resume_ats(resume_text, target_role, years_experience)

    def search_jobs(
        self,
        roles: list[str],
        work_mode: str,
        location: str,
        progress: Callable[[str], None] | None = None,
    ) -> list[JobPosting]:
        def p(msg: str) -> None:
            if progress:
                progress(msg)

        loc_query = _build_location_query(work_mode, location)
        seen: set[str] = set()
        all_jobs: list[JobPosting] = []

        per_role = max(3, SETTINGS.max_results // max(len(roles), 1))
        for role in roles:
            role = role.strip() or "Software Engineer"
            p(f"Searching '{role}' · {work_mode} · {loc_query}…")
            batch = self._search_single_role(role, loc_query, progress=p)[:per_role]
            for job in batch:
                if job.id not in seen:
                    seen.add(job.id)
                    all_jobs.append(job)
            if len(all_jobs) >= SETTINGS.max_results:
                break

        return all_jobs[: SETTINGS.max_results]

    def _search_single_role(
        self,
        role: str,
        location: str,
        progress: Callable[[str], None] | None = None,
    ) -> list[JobPosting]:
        source = SETTINGS.job_source.lower().strip()

        if source == "jsearch":
            if not SETTINGS.jsearch_api_key:
                if progress:
                    progress("JSEARCH_API_KEY not set — using demo listings.")
                return mock_job_postings(role, location, None)
            from auto_job_hunting_agent.scrapers.jsearch import search_jsearch_jobs

            try:
                return search_jsearch_jobs(role, location, None)
            except Exception as exc:
                logger.warning("JSearch error: %s", exc)
                if progress:
                    progress(f"JSearch error — demo listings. ({exc})")
                return mock_job_postings(role, location, None)

        if source == "adzuna":
            if not SETTINGS.adzuna_app_id or not SETTINGS.adzuna_app_key:
                if progress:
                    progress("Adzuna keys not set — using demo listings.")
                return mock_job_postings(role, location, None)
            from auto_job_hunting_agent.scrapers.adzuna import search_adzuna_jobs

            try:
                return search_adzuna_jobs(role, location, None)
            except Exception as exc:
                logger.warning("Adzuna error: %s", exc)
                return mock_job_postings(role, location, None)

        return mock_job_postings(role, location, None)

    def analyze_job(
        self,
        job: JobPosting,
        target_roles: list[str],
        work_mode: str,
        location_pref: str,
        years_experience: float,
    ) -> JobMatchResult:
        if not self.resume_store.is_ready:
            raise RuntimeError("Upload and index a resume before analysis.")
        query = "\n".join(
            x for x in (job.title, job.company or "", job.location or "", job.description) if x
        )
        docs = self.resume_store.similarity_search(query, k=6)
        ctx = build_structured_resume_context(docs)
        return score_job_ranked(
            job,
            ctx,
            target_roles,
            work_mode,
            location_pref,
            years_experience,
        )

    def search_and_score(
        self,
        roles_csv: str,
        work_mode: str,
        location: str,
        years_experience: float,
        progress: Callable[[str, float], None] | None = None,
        max_llm_rankings: int | None = None,
    ) -> list[ScoredJob]:
        roles = _parse_roles(roles_csv)
        llm_cap = max(0, max_llm_rankings if max_llm_rankings is not None else SETTINGS.max_llm_rankings)
        resume = self.resume_store.raw_resume if self.resume_store.is_ready else ""

        def p(msg: str, pct: float = 0.0) -> None:
            if progress:
                progress(msg, pct)

        jobs = self.search_jobs(roles, work_mode, location, progress=lambda m: p(m, 0.05))
        if not jobs:
            return []

        p("Quick local ranking for all listings…", 0.12)
        prelim: list[tuple[JobPosting, JobMatchResult]] = []
        for job in jobs:
            prelim.append(
                (job, heuristic_job_match(job, resume, roles, years_experience))
            )
        prelim.sort(key=lambda x: x[1].hiring_chance, reverse=True)

        results: list[ScoredJob] = []
        loc_label = f"{work_mode} · {location}"
        n = len(prelim)
        for i, (job, quick) in enumerate(prelim):
            if i < llm_cap:
                p(
                    f"Deep AI rank {i + 1}/{llm_cap}: {job.company or 'Company'} — {job.title}…",
                    0.15 + 0.85 * (i / max(llm_cap, 1)),
                )
                if i > 0:
                    time.sleep(5)  # stay within RPM quota
                match = self.analyze_job(job, roles, work_mode, loc_label, years_experience)
            else:
                match = quick
            results.append(ScoredJob(job=job, match=match))

        results.sort(key=lambda x: x.match.hiring_chance, reverse=True)
        return results
