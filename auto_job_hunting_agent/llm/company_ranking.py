from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from auto_job_hunting_agent.llm.scoring import _build_llm
from auto_job_hunting_agent.models import JobMatchResult, JobPosting

_RANK_SYSTEM = """You are a senior career strategist and ex-FAANG recruiter.
Given a job posting, resume excerpts, and candidate preferences, produce a holistic match score.

Prioritize hiring_chance (0-100): realistic odds the candidate gets an interview/offer if they apply now.
Weigh: resume_fit vs JD, company brand/reputation in industry, typical compensation for role+YOE,
growth trajectory, work environment reputation, flexibility (remote/hybrid), and amenities/perks when known.

Use public knowledge about well-known employers; for unknown companies infer conservatively from JD tone.
Never invent resume facts. Be honest about gaps.
Write a tailored 3-paragraph cover letter for this specific role.
Return structured output only."""


def score_job_ranked(
    job: JobPosting,
    structured_resume_context: str,
    target_roles: list[str],
    work_mode: str,
    location_pref: str,
    years_experience: float,
) -> JobMatchResult:
    llm = _build_llm().with_structured_output(JobMatchResult)
    roles_line = ", ".join(target_roles) if target_roles else job.title
    jd = (
        f"Title: {job.title}\n"
        f"Company: {job.company or 'Unknown'}\n"
        f"Location: {job.location or 'Unknown'}\n"
        f"Listed salary: {job.salary_text or 'Not disclosed'}\n"
        f"Platform: {job.platform}\n\n"
        f"--- JOB DESCRIPTION ---\n"
        f"{job.description or '(No description — score conservatively.)'}"
    )
    prefs = (
        f"Candidate target roles: {roles_line}\n"
        f"Preferred work mode: {work_mode}\n"
        f"Location preference: {location_pref}\n"
        f"Years of experience: {years_experience}\n"
    )
    msg = HumanMessage(
        content=f"{prefs}\n{jd}\n\n--- RESUME EXCERPTS ---\n{structured_resume_context}"
    )
    result: JobMatchResult = llm.invoke([SystemMessage(content=_RANK_SYSTEM), msg])  # type: ignore[assignment]
    return result
