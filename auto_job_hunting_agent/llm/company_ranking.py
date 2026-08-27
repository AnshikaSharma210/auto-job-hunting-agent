from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

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

# Keep inputs short to stay within Groq's 6,000 token-per-minute free-tier limit
_MAX_JD_CHARS = 1200
_MAX_RESUME_CHARS = 1000


def score_job_ranked(
    job: JobPosting,
    structured_resume_context: str,
    target_roles: list[str],
    work_mode: str,
    location_pref: str,
    years_experience: float,
) -> JobMatchResult:
    from auto_job_hunting_agent.config import SETTINGS

    roles_line = ", ".join(target_roles) if target_roles else job.title
    jd_text = (job.description or "(No description — score conservatively.)")[:_MAX_JD_CHARS]
    jd = (
        f"Title: {job.title}\n"
        f"Company: {job.company or 'Unknown'}\n"
        f"Location: {job.location or 'Unknown'}\n"
        f"Listed salary: {job.salary_text or 'Not disclosed'}\n\n"
        f"--- JOB DESCRIPTION (excerpt) ---\n"
        f"{jd_text}"
    )
    prefs = (
        f"Candidate target roles: {roles_line}\n"
        f"Preferred work mode: {work_mode}\n"
        f"Location preference: {location_pref}\n"
        f"Years of experience: {years_experience}\n"
    )
    resume_excerpt = structured_resume_context[:_MAX_RESUME_CHARS]
    messages = [
        SystemMessage(content=_RANK_SYSTEM),
        HumanMessage(content=f"{prefs}\n{jd}\n\n--- RESUME EXCERPTS ---\n{resume_excerpt}"),
    ]

    if SETTINGS.llm_provider == "groq":
        from langchain_groq import ChatGroq
        import os
        key = (SETTINGS.groq_api_key or os.getenv("GROQ_API_KEY") or "").strip()
        llm = ChatGroq(model=SETTINGS.groq_model, groq_api_key=key, temperature=0.2)
        return llm.with_structured_output(JobMatchResult).invoke(messages)  # type: ignore[return-value]

    if SETTINGS.llm_provider == "google":
        from auto_job_hunting_agent.llm.key_manager import invoke_structured_with_rotation
        return invoke_structured_with_rotation(messages, JobMatchResult, SETTINGS.google_chat_model)

    # OpenAI path
    import os
    from langchain_openai import ChatOpenAI
    okey = (SETTINGS.openai_api_key or os.getenv("OPENAI_API_KEY") or "").strip()
    if not okey:
        raise RuntimeError("OPENAI_API_KEY is not set.")
    llm = ChatOpenAI(model=SETTINGS.openai_chat_model, temperature=0.2, api_key=okey)
    return llm.with_structured_output(JobMatchResult).invoke(messages)  # type: ignore[return-value]
