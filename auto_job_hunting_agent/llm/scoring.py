from __future__ import annotations

import os

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from auto_job_hunting_agent.config import SETTINGS
from auto_job_hunting_agent.models import FitScore, JobPosting


_SYSTEM = """You are an expert technical recruiter and career coach.
You receive a job description and relevant excerpts from the candidate's resume.

Your tasks:
1. Score the fit from 0 to 100 based on skills, seniority, domain, and accomplishments vs the JD.
2. List up to 4 key strengths (short phrases).
3. List up to 3 gaps (short phrases). Be honest — do not invent facts not in the resume.
4. Write a concise, tailored cover letter (3 short paragraphs) that maps resume evidence to JD needs.
Return structured output matching the schema exactly."""


def _build_llm() -> BaseChatModel:
    if SETTINGS.llm_provider == "google":
        gkey = (SETTINGS.google_api_key or os.getenv("GOOGLE_API_KEY") or "").strip()
        if not gkey:
            raise RuntimeError(
                "GOOGLE_API_KEY is not set. "
                "Get a free key at https://aistudio.google.com/app/apikey"
            )
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=SETTINGS.google_chat_model,
            google_api_key=gkey,
            temperature=0.2,
            convert_system_message_to_human=True,
        )
    # fallback: OpenAI
    okey = (SETTINGS.openai_api_key or os.getenv("OPENAI_API_KEY") or "").strip()
    if not okey:
        raise RuntimeError("OPENAI_API_KEY is not set.")
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model=SETTINGS.openai_chat_model,
        temperature=0.2,
        api_key=okey,
    )


def score_job_against_resume(job: JobPosting, structured_resume_context: str) -> FitScore:
    llm = _build_llm().with_structured_output(FitScore)

    jd = (
        f"Title: {job.title}\n"
        f"Company: {job.company or 'Unknown'}\n"
        f"Location: {job.location or 'Unknown'}\n"
        f"Salary: {job.salary_text or 'Unknown'}\n\n"
        f"--- JOB DESCRIPTION ---\n"
        f"{job.description or '(No description — score conservatively.)'}"
    )
    msg = HumanMessage(
        content=f"{jd}\n\n--- RESUME EXCERPTS ---\n{structured_resume_context}"
    )
    result: FitScore = llm.invoke([SystemMessage(content=_SYSTEM), msg])  # type: ignore[assignment]
    return result
