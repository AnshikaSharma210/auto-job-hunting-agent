"""ATS resume scoring — LLM-based analysis with local heuristic fallback."""
from __future__ import annotations

import json
import re

from auto_job_hunting_agent.models import ATSResumeScore

# ── LLM prompt ───────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a senior technical recruiter and ATS specialist with 15+ years of experience
screening candidates for top-tier tech companies.

Your task: perform a realistic ATS + human-reviewer analysis of this resume against
the given target role. Be honest and specific — avoid inflating scores.

Return ONLY a valid JSON object with these exact keys:
{
  "overall_pct": <int 0-100>,
  "keyword_match_pct": <int 0-100>,
  "formatting_score_pct": <int 0-100>,
  "experience_clarity_pct": <int 0-100>,
  "role_readiness": "<e.g. Strong Mid-level | Junior — needs cloud exp | Over-qualified>",
  "hiring_prospect": "<2-3 sentence plain-English hiring outlook: chances, what helps, what hurts>",
  "summary": "<1-2 sentence ATS pass-rate estimate with key reasons>",
  "present_strengths": ["<specific skill or experience from resume relevant to role>", ...],
  "matched_keywords": ["<keyword found in resume>", ...],
  "missing_keywords": ["<keyword expected for role but absent>", ...],
  "critical_missing": ["<must-have skill absent — deal-breaker gaps only>", ...],
  "gaps": ["<specific gap with context, e.g. No CI/CD pipeline experience mentioned>", ...],
  "improvements": ["<specific, actionable improvement tied to THIS resume>", ...]
}

Scoring guide:
- overall_pct: ATS filter pass likelihood. Be realistic (60-75 is typical for good candidates).
  Scores 85+ mean the resume is nearly role-perfect; don't give 90+ unless genuinely exceptional.
- keyword_match_pct: How many industry-standard keywords for this role appear in the resume.
- formatting_score_pct: Structure, clarity, use of bullet points, measurable outcomes.
- experience_clarity_pct: How clearly relevant experience is demonstrated with impact.
- present_strengths: 3-5 specific things in the resume that help for this role.
- missing_keywords: 5-10 typical skills/tools for this role that are absent.
- critical_missing: Only the 1-3 absolute must-haves that would cause immediate rejection.
- gaps: 3-4 substantive gaps specific to what's in the resume vs role expectations.
- improvements: 3-5 specific, actionable suggestions referencing actual resume content.
"""


def _llm_ats_score(resume_text: str, target_role: str, years_experience: float) -> ATSResumeScore:
    from auto_job_hunting_agent.llm.scoring import _build_llm
    from langchain_core.messages import HumanMessage, SystemMessage

    llm = _build_llm()

    user_msg = f"""\
TARGET ROLE: {target_role}
CANDIDATE EXPERIENCE: {years_experience} years

RESUME (key sections — skills, experience, projects):
{resume_text[:2800]}

Analyze the resume against the target role and return the JSON object as specified."""

    result = llm.invoke([SystemMessage(content=_SYSTEM_PROMPT), HumanMessage(content=user_msg)])
    raw = result.content.strip()

    # Strip markdown fences if present
    raw = re.sub(r"^```[a-z]*\n?", "", raw).rstrip("`").strip()

    data = json.loads(raw)

    return ATSResumeScore(
        overall_pct=int(data.get("overall_pct", 50)),
        keyword_match_pct=int(data.get("keyword_match_pct", 50)),
        formatting_score_pct=int(data.get("formatting_score_pct", 60)),
        experience_clarity_pct=int(data.get("experience_clarity_pct", 50)),
        summary=data.get("summary", ""),
        role_readiness=data.get("role_readiness", ""),
        hiring_prospect=data.get("hiring_prospect", ""),
        present_strengths=data.get("present_strengths", []),
        matched_keywords=data.get("matched_keywords", []),
        missing_keywords=data.get("missing_keywords", []),
        critical_missing=data.get("critical_missing", []),
        gaps=data.get("gaps", []),
        improvements=data.get("improvements", []),
    )


# ── Heuristic fallback (no API calls) ────────────────────────────────────────

_STOP = {
    "the", "and", "for", "with", "that", "this", "from", "you", "your", "our", "are",
    "role", "job", "years", "year", "experience",
}

# Typical skills expected per role family (used when LLM unavailable)
_ROLE_KEYWORDS: dict[str, list[str]] = {
    "python": ["python", "django", "fastapi", "flask", "pandas", "numpy", "sqlalchemy",
               "rest", "api", "docker", "git", "pytest", "celery", "redis"],
    "java": ["java", "spring", "springboot", "maven", "gradle", "junit", "microservices",
             "jvm", "hibernate", "rest", "api", "docker", "kubernetes"],
    "javascript": ["javascript", "typescript", "react", "nodejs", "express", "html", "css",
                   "webpack", "jest", "rest", "api", "git"],
    "frontend": ["react", "angular", "vue", "typescript", "html", "css", "webpack",
                 "responsive", "accessibility", "performance", "git"],
    "backend": ["api", "rest", "sql", "nosql", "microservices", "docker", "kubernetes",
                "caching", "messaging", "git", "ci/cd"],
    "data": ["python", "sql", "pandas", "numpy", "spark", "tableau", "powerbi",
             "etl", "warehouse", "pipeline", "machine learning"],
    "ml": ["python", "tensorflow", "pytorch", "sklearn", "pandas", "numpy",
           "model", "training", "deployment", "mlops", "docker"],
    "devops": ["docker", "kubernetes", "ci/cd", "jenkins", "terraform", "ansible",
               "aws", "azure", "gcp", "monitoring", "linux", "bash"],
    "sdet": ["selenium", "pytest", "junit", "testng", "automation", "api testing",
             "performance testing", "bdd", "cucumber", "ci/cd", "git"],
    "qa": ["testing", "automation", "selenium", "test cases", "bug", "jira",
           "regression", "integration", "api", "performance"],
    "fullstack": ["react", "nodejs", "python", "java", "sql", "rest", "api",
                  "docker", "git", "html", "css", "typescript"],
    "cloud": ["aws", "azure", "gcp", "terraform", "kubernetes", "docker",
              "serverless", "iam", "vpc", "ci/cd", "linux"],
    "ai": ["python", "langchain", "llm", "openai", "pytorch", "tensorflow",
           "embedding", "vector", "rag", "model", "deployment"],
}


def _get_role_keywords(target_role: str) -> list[str]:
    role_lower = target_role.lower()
    for key, kws in _ROLE_KEYWORDS.items():
        if key in role_lower:
            return kws
    # Fallback: tokenize the role title
    words = re.findall(r"[a-z0-9+#.]{2,}", role_lower)
    return [w for w in words if w not in _STOP]


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9+#./]{2,}", text.lower())
    return {w for w in words if w not in _STOP and len(w) > 2}


def _heuristic_ats_score(resume_text: str, target_role: str, years_experience: float) -> ATSResumeScore:
    role_keywords = _get_role_keywords(target_role)
    resume_terms = _tokens(resume_text)

    matched = [kw for kw in role_keywords if kw in resume_terms]
    missing = [kw for kw in role_keywords if kw not in resume_terms]

    keyword_pct = int(round(100 * len(matched) / max(len(role_keywords), 1)))
    keyword_pct = max(20, min(100, keyword_pct))

    # Formatting heuristics
    text = resume_text.lower()
    fmt = 60
    if len(resume_text) > 1500:
        fmt += 10
    if re.search(r"\b(experience|work history)\b", text):
        fmt += 8
    if re.search(r"\b(skills|technical skills|tools)\b", text):
        fmt += 8
    if re.search(r"\b(education|degree|university)\b", text):
        fmt += 6
    if re.search(r"\d+%|\$\d+|\d+\s*(k|m)\b", text):
        fmt += 8
    fmt = max(35, min(100, fmt))

    # Experience clarity
    exp = 55
    if re.search(r"\b\d+\+?\s+years?\b", text):
        exp += 20
    if re.search(r"\b(led|owned|architected|built|delivered|launched|designed)\b", text):
        exp += 10
    if years_experience >= 2:
        exp += 5
    if years_experience >= 5:
        exp += 5
    exp = max(35, min(100, exp))

    overall = int(round(keyword_pct * 0.5 + fmt * 0.25 + exp * 0.25))
    overall = max(20, min(100, overall))

    gaps: list[str] = []
    if missing:
        gaps.append(f"Missing expected skills: {', '.join(missing[:6])}")
    if fmt < 70:
        gaps.append("Resume could use clearer section headings and measurable impact bullets.")
    if exp < 70:
        gaps.append("Experience section should show ownership and quantified outcomes.")

    improvements = [
        f"Add these missing skills to your resume if applicable: {', '.join(missing[:5])}",
        "Quantify achievements — add numbers (%, latency, scale, revenue impact).",
        "Ensure section titles are explicit: Summary, Technical Skills, Experience, Projects, Education.",
    ]

    summary = (
        f"Heuristic ATS estimate: {overall}% pass likelihood for '{target_role}'. "
        f"Keyword match {keyword_pct}%, formatting {fmt}%, experience clarity {exp}%. "
        f"Enable AI analysis for deeper insights."
    )

    return ATSResumeScore(
        overall_pct=overall,
        keyword_match_pct=keyword_pct,
        formatting_score_pct=fmt,
        experience_clarity_pct=exp,
        summary=summary,
        role_readiness="",
        hiring_prospect="",
        present_strengths=[],
        matched_keywords=matched[:15],
        missing_keywords=missing[:15],
        critical_missing=missing[:3],
        gaps=gaps,
        improvements=improvements,
    )


# ── Public entry point ────────────────────────────────────────────────────────

def score_resume_ats(resume_text: str, target_role: str, years_experience: float) -> ATSResumeScore:
    """
    Score a resume against a target role.
    Tries LLM first; on quota/rate-limit falls back to heuristics with a note in the summary.
    Other unexpected errors still propagate so the UI can surface them.
    """
    try:
        return _llm_ats_score(resume_text, target_role, years_experience)
    except Exception as exc:
        err_str = str(exc).lower()
        # Quota / rate-limit / transient API errors → heuristic fallback
        if any(k in err_str for k in ("quota", "exhausted", "rate", "429", "503", "resource")):
            result = _heuristic_ats_score(resume_text, target_role, years_experience)
            result.summary = (
                f"[Quick estimate — AI analysis paused due to service limits] {result.summary}"
            )
            return result
        # All other errors propagate (bad key, network, etc.)
        raise
