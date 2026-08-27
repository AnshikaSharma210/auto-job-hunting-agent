"""
LLM-powered resume tailoring for a specific job posting.

For each shortlisted job, this module:
  1. Identifies keywords from the JD that are absent from the resume (inject into skills/summary)
  2. Surfaces existing resume bullet points worth emphasising for this role
  3. Generates a 3-sentence tailored professional summary tuned to the exact JD

Designed to run on-demand (user clicks "Tailor for this job") — not on every search.
Uses the same BYOK + rate-limit pattern as the rest of the LLM layer.
"""
from __future__ import annotations

import os

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from auto_job_hunting_agent.config import SETTINGS


class ResumeTailoringResult(BaseModel):
    """Output schema for per-job resume tailoring."""

    keywords_to_add: list[str] = Field(
        default_factory=list,
        description=(
            "Specific terms, technologies, or skills present in the JD but absent from the resume. "
            "These should be added to the resume's skills section or summary if the candidate actually has them."
        ),
    )
    bullets_to_emphasise: list[str] = Field(
        default_factory=list,
        description=(
            "Short phrases describing existing resume achievements or experiences that directly "
            "address what the JD asks for. Use these as talking points in interviews or to "
            "reorder the resume's experience section."
        ),
    )
    tailored_summary: str = Field(
        default="",
        description=(
            "A 3-sentence professional summary paragraph specifically written for this role and company. "
            "Draws only on facts mentioned in the resume — no fabrication."
        ),
    )
    match_verdict: str = Field(
        default="",
        description=(
            "One sentence honest verdict: how strong a match the resume is for this specific role, "
            "and the single most important thing to fix before applying."
        ),
    )


_SYSTEM = """You are a professional resume coach and technical recruiter.
You receive a job description and key sections from the candidate's resume.

Your tasks:
1. keywords_to_add: Extract up to 10 specific terms/skills/technologies from the JD that are missing from the resume.
   Only include ones the candidate could plausibly add if they genuinely have the skill.
2. bullets_to_emphasise: List up to 5 existing resume experiences/achievements that are most relevant to this JD.
   Quote or closely paraphrase the actual resume text.
3. tailored_summary: Write a 3-sentence professional summary tuned to THIS specific role and company.
   Draw only from the resume — do not invent skills or experiences.
4. match_verdict: One honest sentence on fit quality and the top gap to address.

Return structured JSON matching the schema exactly."""




def tailor_resume_for_job(
    resume_sections: str,
    job_title: str,
    company: str,
    job_description: str,
) -> ResumeTailoringResult:
    """
    Generate tailored keyword suggestions and a professional summary for the given job.
    Uses key rotation automatically on quota errors.
    """
    from auto_job_hunting_agent.config import SETTINGS

    jd_block = (
        f"Role: {job_title}\n"
        f"Company: {company or 'Unknown'}\n\n"
        f"--- JOB DESCRIPTION ---\n"
        f"{job_description[:2500] or '(No description provided.)'}"
    )
    resume_block = f"--- RESUME KEY SECTIONS ---\n{resume_sections[:2000]}"
    messages = [
        SystemMessage(content=_SYSTEM),
        HumanMessage(content=f"{jd_block}\n\n{resume_block}"),
    ]

    if SETTINGS.llm_provider == "google":
        from auto_job_hunting_agent.llm.key_manager import invoke_structured_with_rotation
        return invoke_structured_with_rotation(
            messages, ResumeTailoringResult, SETTINGS.google_chat_model, temperature=0.25
        )

    # OpenAI path
    import os
    from langchain_openai import ChatOpenAI
    okey = (SETTINGS.openai_api_key or os.getenv("OPENAI_API_KEY") or "").strip()
    if not okey:
        raise RuntimeError("OPENAI_API_KEY is not set.")
    llm = ChatOpenAI(model=SETTINGS.openai_chat_model, temperature=0.25, api_key=okey)
    return llm.with_structured_output(ResumeTailoringResult).invoke(messages)  # type: ignore[return-value]
