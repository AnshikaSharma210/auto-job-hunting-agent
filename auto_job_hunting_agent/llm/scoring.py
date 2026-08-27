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


def _build_llm(temperature: float = 0.2) -> BaseChatModel:
    """Build an LLM using the configured provider. Uses key rotation for Google."""
    if SETTINGS.llm_provider == "groq":
        from langchain_groq import ChatGroq
        key = (SETTINGS.groq_api_key or os.getenv("GROQ_API_KEY") or "").strip()
        if not key:
            raise RuntimeError(
                "GROQ_API_KEY is not set. Get a free key at https://console.groq.com"
            )
        return ChatGroq(model=SETTINGS.groq_model, groq_api_key=key, temperature=temperature)

    if SETTINGS.llm_provider == "google":
        from auto_job_hunting_agent.llm.key_manager import build_google_llm_with_rotation
        return build_google_llm_with_rotation(SETTINGS.google_chat_model, temperature)

    # OpenAI fallback
    okey = (SETTINGS.openai_api_key or os.getenv("OPENAI_API_KEY") or "").strip()
    if not okey:
        raise RuntimeError("OPENAI_API_KEY is not set.")
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(model=SETTINGS.openai_chat_model, temperature=temperature, api_key=okey)


def _invoke_llm(messages: list, temperature: float = 0.2):
    """
    Invoke the LLM with automatic key rotation on quota errors (Google only).
    For OpenAI, delegates directly to _build_llm.
    """
    if SETTINGS.llm_provider == "google":
        from auto_job_hunting_agent.llm.key_manager import invoke_with_key_rotation
        return invoke_with_key_rotation(messages, SETTINGS.google_chat_model, temperature)
    return _build_llm(temperature).invoke(messages)


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
