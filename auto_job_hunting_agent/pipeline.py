from __future__ import annotations

import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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


# ── helpers ───────────────────────────────────────────────────────────────────

def _build_location_query(work_mode: str, location: str) -> str:
    """Build a clean location query string for API calls."""
    mode = work_mode.strip().lower()
    loc = location.strip() or "India"
    if mode == "remote":
        return "remote"
    # For hybrid/on-site just return the city — work mode is passed separately to JSearch
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
    start = section_starts[0][0]
    return resume_text[start : start + max_chars]


def _parse_extra_companies(raw: str) -> dict[str, dict[str, str]]:
    """Parse COMPANY_LIST_EXTRA="Name:ats:slug,Name2:ats2:slug2" into dict."""
    out: dict[str, dict[str, str]] = {}
    for entry in raw.split(","):
        parts = [p.strip() for p in entry.split(":")]
        if len(parts) == 3 and all(parts):
            out[parts[0]] = {"ats": parts[1], "slug": parts[2]}
    return out


def _dedup(jobs: list[JobPosting]) -> list[JobPosting]:
    """Remove cross-source duplicates by normalised title+company key."""
    seen: set[str] = set()
    unique: list[JobPosting] = []
    for job in jobs:
        key = f"{job.title.lower().strip()}|{(job.company or '').lower().strip()}"
        if key not in seen:
            seen.add(key)
            unique.append(job)
    return unique


# ── Role abbreviation expansion ───────────────────────────────────────────────
# Maps short/abbreviated role names to the actual words that appear in job titles.
# This lets "SDE" match "Software Engineer", "QA" match "Quality Assurance", etc.

_ROLE_EXPAND: dict[str, list[str]] = {
    "sde":          ["software", "developer", "engineer", "backend", "fullstack"],
    "swe":          ["software", "developer", "engineer"],
    "qa":           ["quality", "assurance", "test", "testing", "automation", "sdet"],
    "qe":           ["quality", "engineer", "testing"],
    "sdet":         ["automation", "test", "quality", "engineer", "sdet"],
    "ml":           ["machine", "learning", "data", "scientist", "mlops"],
    "ai":           ["artificial", "intelligence", "machine", "learning", "genai", "llm"],
    "llm":          ["llm", "language", "model", "ai", "engineer", "nlp"],
    "pm":           ["product", "manager", "management"],
    "po":           ["product", "owner", "manager"],
    "ux":           ["design", "user", "experience", "ux", "product"],
    "ui":           ["design", "frontend", "interface"],
    "ba":           ["business", "analyst", "analysis"],
    "hr":           ["human", "resources", "recruiter", "talent", "acquisition"],
    "ops":          ["operations", "devops", "platform", "infrastructure"],
    "sre":          ["reliability", "engineer", "devops", "platform"],
    "data":         ["data", "analyst", "scientist", "engineer", "analytics"],
    "fullstack":    ["fullstack", "full", "stack", "frontend", "backend"],
    "full-stack":   ["fullstack", "full", "stack", "frontend", "backend"],
    "devops":       ["devops", "cloud", "infrastructure", "reliability", "platform"],
    "android":      ["android", "mobile", "kotlin", "developer"],
    "ios":          ["ios", "swift", "mobile", "developer"],
    "mobile":       ["mobile", "android", "ios", "react native", "flutter"],
    # extra common full-word lookups
    "software":     ["software", "developer", "engineer"],
    "developer":    ["developer", "engineer", "software"],
    "engineer":     ["engineer", "developer", "software"],
    "automation":   ["automation", "test", "sdet", "engineer", "quality"],
    "backend":      ["backend", "server", "engineer", "developer"],
    "frontend":     ["frontend", "ui", "react", "angular", "vue", "engineer"],
    "cloud":        ["cloud", "aws", "azure", "gcp", "devops", "infrastructure"],
    "security":     ["security", "infosec", "appsec", "cybersecurity"],
    "embedded":     ["embedded", "firmware", "iot", "hardware"],
    "architect":    ["architect", "architecture", "principal", "lead"],
    "principal":    ["principal", "staff", "architect", "lead", "senior"],
    "senior":       ["senior", "sr", "lead", "staff", "principal"],
    "lead":         ["lead", "senior", "principal", "staff"],
}

_FILTER_STOP = {"and", "the", "for", "with", "or", "of", "in", "at", "to", "a", "is", "an"}

# Maps abbreviated role to a human-readable search string used for API queries
_SEARCH_EXPAND: dict[str, str] = {
    "sde":    "Software Engineer",
    "swe":    "Software Engineer",
    "qa":     "QA Engineer",
    "qe":     "Quality Engineer",
    "sdet":   "SDET Automation Engineer",
    "ml":     "Machine Learning Engineer",
    "ai":     "AI Engineer",
    "pm":     "Product Manager",
    "po":     "Product Owner",
    "ux":     "UX Designer",
    "ui":     "UI Designer",
    "ba":     "Business Analyst",
    "sre":    "Site Reliability Engineer",
    "devops": "DevOps Engineer",
    "data":   "Data Engineer",
}


def _expand_role_for_search(role: str) -> str:
    """Expand abbreviated roles into full search terms for external APIs."""
    return _SEARCH_EXPAND.get(role.lower().strip(), role)


def _expand_role_keywords(roles: list[str]) -> set[str]:
    """
    Build the full set of title-match keywords from the user's roles.
    Expands abbreviations and splits multi-word roles into individual words.
    """
    keywords: set[str] = set()
    for role in roles:
        role_lower = role.lower().strip()
        # Check if the whole role phrase is an abbreviation we know
        if role_lower in _ROLE_EXPAND:
            keywords.update(_ROLE_EXPAND[role_lower])
        # Also split into individual words and expand each
        for word in re.findall(r"[a-z]+", role_lower):
            if len(word) >= 2 and word not in _FILTER_STOP:
                keywords.add(word)
                if word in _ROLE_EXPAND:
                    keywords.update(_ROLE_EXPAND[word])
    return keywords


def _filter_relevant(jobs: list[JobPosting], roles: list[str]) -> list[JobPosting]:
    """
    Keep only jobs whose TITLE contains at least one keyword from the target roles.
    Also hard-blocks clearly non-tech titles (sales, BDE, content, designer, support)
    unless the user explicitly searched for them.
    """
    if not roles:
        return jobs
    keywords = _expand_role_keywords(roles)
    if not keywords:
        return jobs

    # Build full normalised phrases for phrase-level matching (e.g. "qa engineer")
    role_phrases = [re.sub(r"\s+", " ", r.lower().strip()) for r in roles if r.strip()]

    # Titles that are NEVER tech-developer roles — excluded unless user asked for them
    _HARD_BLOCK = {
        "sales", "business development", "bde", "bdm", "marketing",
        "content writer", "content creator", "copywriter",
        "graphic designer", "visual designer", "ui designer",
        "customer support", "customer success", "customer service",
        "account manager", "account executive",
        "social media", "seo specialist",
        "recruiter", "talent acquisition", "hr executive",
        "operations executive", "operations associate",
        "supply chain", "logistics", "procurement",
    }
    # Only apply hard-block if user didn't explicitly search for those terms
    user_terms = " ".join(roles).lower()
    active_blocks = {b for b in _HARD_BLOCK if b not in user_terms}

    def _is_blocked(title: str) -> bool:
        t = title.lower()
        return any(block in t for block in active_blocks)

    def _is_relevant(job: JobPosting) -> bool:
        title_lower = job.title.lower()
        if _is_blocked(title_lower):
            return False
        # Exact phrase match (e.g. "qa engineer" in title)
        if any(phrase in title_lower for phrase in role_phrases):
            return True
        # Keyword match
        return any(w in title_lower for w in keywords)

    relevant = [j for j in jobs if _is_relevant(j)]

    # Safety: if filter is too aggressive (< 5 survived), relax to keyword-only (no hard-block)
    if len(relevant) < 5:
        relevant = [j for j in jobs if any(w in j.title.lower() for w in keywords)]

    return relevant if relevant else jobs


# ── pipeline ──────────────────────────────────────────────────────────────────

@dataclass
class JobHuntPipeline:
    resume_store: ResumeVectorStore = field(default_factory=ResumeVectorStore)

    def score_resume_for_role(
        self, target_role: str, years_experience: float
    ) -> ATSResumeScore:
        if not self.resume_store.is_ready:
            raise RuntimeError("Upload a resume before ATS scoring.")
        resume_text = _extract_key_sections(self.resume_store.raw_resume)
        return score_resume_ats(resume_text, target_role, years_experience)

    def get_resume_key_sections(self) -> str:
        """Return extracted key sections for resume tailoring."""
        if not self.resume_store.is_ready:
            return ""
        return _extract_key_sections(self.resume_store.raw_resume)

    # ── source runners ────────────────────────────────────────────────────────

    def _run_jsearch(self, role: str, loc_query: str) -> list[JobPosting]:
        if not SETTINGS.jsearch_api_key:
            return []
        try:
            from auto_job_hunting_agent.scrapers.jsearch import search_jsearch_jobs
            # Expand abbreviations for better search results (e.g. "SDE" → "Software Engineer")
            search_role = _expand_role_for_search(role)
            return search_jsearch_jobs(search_role, loc_query, None, SETTINGS.max_results // 2)
        except Exception as exc:
            logger.warning("JSearch error: %s", exc)
            return []

    def _run_adzuna(self, role: str, loc_query: str) -> list[JobPosting]:
        if not SETTINGS.adzuna_app_id or not SETTINGS.adzuna_app_key:
            return []
        try:
            from auto_job_hunting_agent.scrapers.adzuna import search_adzuna_jobs
            return search_adzuna_jobs(role, loc_query, None, SETTINGS.max_results // 2)
        except Exception as exc:
            logger.warning("Adzuna error: %s", exc)
            return []

    def _run_remotive(self, role: str) -> list[JobPosting]:
        if not SETTINGS.enable_remotive:
            return []
        try:
            from auto_job_hunting_agent.scrapers.remotive import search_remotive_jobs
            return search_remotive_jobs(role, max_results=15)
        except Exception as exc:
            logger.warning("Remotive error: %s", exc)
            return []

    def _run_arbeitnow(self, roles: list[str]) -> list[JobPosting]:
        try:
            from auto_job_hunting_agent.scrapers.arbeitnow import search_arbeitnow_jobs
            return search_arbeitnow_jobs(roles, max_results=15)
        except Exception as exc:
            logger.warning("Arbeitnow error: %s", exc)
            return []

    def _run_jobicy(self, roles: list[str]) -> list[JobPosting]:
        try:
            from auto_job_hunting_agent.scrapers.jobicy import search_jobicy_jobs
            return search_jobicy_jobs(roles, max_results=15)
        except Exception as exc:
            logger.warning("Jobicy error: %s", exc)
            return []

    def _run_themuse(self, roles: list[str], location: str) -> list[JobPosting]:
        try:
            from auto_job_hunting_agent.scrapers.themuse import search_themuse_jobs
            return search_themuse_jobs(roles, location, max_results=20)
        except Exception as exc:
            logger.warning("The Muse error: %s", exc)
            return []

    def _run_company_careers(
        self,
        roles: list[str],
        progress: Callable[[str], None] | None = None,
    ) -> list[JobPosting]:
        if not SETTINGS.enable_company_careers:
            return []
        try:
            from auto_job_hunting_agent.scrapers.company_careers import search_company_careers
            extra = _parse_extra_companies(SETTINGS.company_list_extra)
            return search_company_careers(
                role_keywords=roles,
                max_per_company=3,
                extra_companies=extra or None,
                progress=progress,
            )
        except Exception as exc:
            logger.warning("Company careers error: %s", exc)
            return []

    # ── search ────────────────────────────────────────────────────────────────

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
        source = SETTINGS.job_source.lower().strip()

        # ── single explicit source (legacy / debug) ───────────────────────────
        if source == "mock":
            jobs: list[JobPosting] = []
            for role in roles:
                jobs.extend(mock_job_postings(role, loc_query, None))
            return _dedup(jobs)[: SETTINGS.max_results]

        if source == "jsearch":
            jobs = []
            for role in roles:
                p(f"Searching '{role}' on JSearch…")
                jobs.extend(self._run_jsearch(role, loc_query))
            if not jobs:
                p("JSearch returned no results — using demo listings.")
                for role in roles:
                    jobs.extend(mock_job_postings(role, loc_query, None))
            return _dedup(jobs)[: SETTINGS.max_results]

        if source == "adzuna":
            jobs = []
            for role in roles:
                p(f"Searching '{role}' on Adzuna…")
                jobs.extend(self._run_adzuna(role, loc_query))
            if not jobs:
                for role in roles:
                    jobs.extend(mock_job_postings(role, loc_query, None))
            return _dedup(jobs)[: SETTINGS.max_results]

        # ── multi: all sources in parallel ────────────────────────────────────
        p("Fetching from multiple sources in parallel…")
        all_jobs: list[JobPosting] = []
        is_remote = work_mode.strip().lower() == "remote"

        # Expanded keywords for company career page matching
        expanded_roles = list(_expand_role_keywords(roles))

        def _api_searches() -> list[JobPosting]:
            batch: list[JobPosting] = []
            with ThreadPoolExecutor(max_workers=8) as ex:
                futures = {}
                for role in roles:
                    futures[ex.submit(self._run_jsearch, role, loc_query)] = f"JSearch/{role}"
                    futures[ex.submit(self._run_adzuna, role, loc_query)] = f"Adzuna/{role}"
                    # Remotive and Jobicy are remote-only — skip for Hybrid/On-site
                    if is_remote:
                        futures[ex.submit(self._run_remotive, _expand_role_for_search(role))] = f"Remotive/{role}"
                # The Muse: quality tech jobs, global companies, free no-auth
                futures[ex.submit(self._run_themuse, roles, location)] = "TheMuse"
                # Arbeitnow/Jobicy are European/remote boards — only useful for remote searches
                if is_remote:
                    futures[ex.submit(self._run_arbeitnow, [_expand_role_for_search(r) for r in roles])] = "Arbeitnow"
                # Jobicy: remote-only
                if is_remote:
                    futures[ex.submit(self._run_jobicy, [_expand_role_for_search(r) for r in roles])] = "Jobicy"
                for fut in as_completed(futures):
                    name = futures[fut]
                    try:
                        result = fut.result()
                        if result:
                            batch.extend(result)
                            p(f"{name}: {len(result)} opening(s)")
                    except Exception as exc:
                        logger.debug("%s error: %s", name, exc)
            return batch

        # API searches + company career pages run concurrently at the top level
        with ThreadPoolExecutor(max_workers=2) as outer:
            f_api = outer.submit(_api_searches)
            # Pass expanded keywords so "SDE" matches "Software Engineer" on career pages
            f_careers = outer.submit(
                self._run_company_careers, expanded_roles,
                lambda msg: p(f"Career pages: {msg}")
            )
            all_jobs.extend(f_api.result())
            career_jobs = f_careers.result()
            if career_jobs:
                p(f"Company career pages: {len(career_jobs)} matching opening(s) found")
                all_jobs.extend(career_jobs)

        deduped = _dedup(all_jobs)
        if not deduped:
            p("No live results — showing demo listings.")
            for role in roles:
                deduped.extend(mock_job_postings(role, loc_query, None))
            deduped = _dedup(deduped)

        return deduped[: SETTINGS.max_results]

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
            job, ctx, target_roles, work_mode, location_pref, years_experience,
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
        # Filter to only jobs relevant to the target roles
        jobs = _filter_relevant(jobs, roles)
        if not jobs:
            return []

        p("Local ranking for all listings…", 0.35)
        prelim: list[tuple[JobPosting, JobMatchResult]] = []
        for job in jobs:
            prelim.append(
                (job, heuristic_job_match(job, resume, roles, years_experience))
            )
        prelim.sort(key=lambda x: x[1].hiring_chance, reverse=True)

        results: list[ScoredJob] = []
        loc_label = f"{work_mode} · {location}"
        for i, (job, quick) in enumerate(prelim):
            if i < llm_cap:
                p(
                    f"Deep AI rank {i + 1}/{llm_cap}: {job.company or 'Company'} — {job.title}…",
                    0.4 + 0.58 * (i / max(llm_cap, 1)),
                )
                if i > 0:
                    time.sleep(3)  # respect Groq's 6k TPM free-tier limit
                try:
                    match = self.analyze_job(job, roles, work_mode, loc_label, years_experience)
                except Exception as exc:
                    logger.warning("LLM ranking failed for '%s', using heuristic: %s", job.title, exc)
                    match = quick
            else:
                match = quick
            results.append(ScoredJob(job=job, match=match))

        results.sort(key=lambda x: x.match.hiring_chance, reverse=True)
        return results
