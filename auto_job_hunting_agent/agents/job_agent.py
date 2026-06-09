from __future__ import annotations

import json
import os
from typing import Any

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool

from auto_job_hunting_agent.config import SETTINGS
from auto_job_hunting_agent.models import JobPosting
from auto_job_hunting_agent.pipeline import JobHuntPipeline


def _build_agent_llm():
    if SETTINGS.llm_provider == "google":
        gkey = (SETTINGS.google_api_key or os.getenv("GOOGLE_API_KEY") or "").strip()
        if not gkey:
            raise RuntimeError("GOOGLE_API_KEY is not set.")
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=SETTINGS.google_chat_model,
            google_api_key=gkey,
            temperature=0.1,
            convert_system_message_to_human=True,
        )
    okey = (SETTINGS.openai_api_key or os.getenv("OPENAI_API_KEY") or "").strip()
    if not okey:
        raise RuntimeError("OPENAI_API_KEY is not set.")
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model=SETTINGS.openai_chat_model,
        temperature=0.1,
        api_key=okey,
    )


def build_job_agent_executor(pipeline: JobHuntPipeline) -> AgentExecutor:

    @tool
    def search_and_score_jobs(
        roles_csv: str,
        work_mode: str,
        location: str,
        years_experience: float = 3,
    ) -> str:
        """Search jobs and rank by hiring chance. roles_csv: up to 3 titles comma-separated."""
        results = pipeline.search_and_score(roles_csv, work_mode, location, years_experience)
        out = [
            {
                "rank": i + 1,
                "hiring_chance": r.match.hiring_chance,
                "title": r.job.title,
                "company": r.job.company,
                "location": r.job.location,
                "summary": r.match.summary,
            }
            for i, r in enumerate(results)
        ]
        return json.dumps(out, ensure_ascii=False)

    @tool
    def get_cover_letter(job_json: str) -> str:
        """Given a JobPosting JSON, return a tailored cover letter."""
        job = JobPosting.model_validate(json.loads(job_json))
        meta = pipeline  # noqa: keep reference
        match = meta.analyze_job(
            job,
            target_roles=[job.title],
            work_mode="Remote",
            location_pref=job.location or "India",
            years_experience=3.0,
        )
        return match.tailored_cover_letter

    @tool
    def explain_resume_match(job_json: str) -> str:
        """Show resume sections retrieved for a job."""
        from auto_job_hunting_agent.rag.context_builder import build_structured_resume_context

        job = JobPosting.model_validate(json.loads(job_json))
        if not pipeline.resume_store.is_ready:
            return "Resume not indexed yet."
        query = "\n".join(
            x for x in (job.title, job.company or "", job.location or "", job.description) if x
        )
        docs = pipeline.resume_store.similarity_search(query, k=6)
        return build_structured_resume_context(docs)[:8000]

    tools = [search_and_score_jobs, get_cover_letter, explain_resume_match]

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a job-hunting copilot. Help users find roles, explain rankings, "
                "and refine cover letters. The human always reviews before applying.",
            ),
            MessagesPlaceholder("chat_history", optional=True),
            ("human", "{input}"),
            MessagesPlaceholder("agent_scratchpad"),
        ]
    )

    llm = _build_agent_llm()
    agent = create_tool_calling_agent(llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=False, max_iterations=8)


def run_agent_message(
    executor: AgentExecutor,
    text: str,
    chat_history: list[Any] | None = None,
) -> str:
    hist = chat_history or []
    out = executor.invoke({"input": text, "chat_history": hist})
    return str(out.get("output", ""))
