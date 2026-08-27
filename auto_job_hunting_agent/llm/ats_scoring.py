"""ATS resume scoring — LLM-based analysis with intelligent local heuristic fallback."""
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
    from auto_job_hunting_agent.llm.key_manager import invoke_with_key_rotation
    from auto_job_hunting_agent.config import SETTINGS
    from langchain_core.messages import HumanMessage, SystemMessage

    user_msg = f"""\
TARGET ROLE: {target_role}
CANDIDATE EXPERIENCE: {years_experience} years

RESUME (key sections — skills, experience, projects):
{resume_text[:2000]}

Analyze the resume against the target role and return the JSON object as specified."""

    result = invoke_with_key_rotation(
        [SystemMessage(content=_SYSTEM_PROMPT), HumanMessage(content=user_msg)],
        model=SETTINGS.google_chat_model,
    )
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
    "role", "job", "years", "year", "experience", "also", "will", "must", "have",
}

# Comprehensive role → expected skills/keywords map
_ROLE_KEYWORDS: dict[str, list[str]] = {
    "automation": [
        "selenium", "pytest", "junit", "testng", "appium", "playwright", "cypress",
        "api testing", "rest assured", "postman", "bdd", "cucumber", "gherkin",
        "ci/cd", "jenkins", "github actions", "docker", "git", "python", "java",
        "performance testing", "jmeter", "regression", "test framework", "page object",
    ],
    "qa": [
        "selenium", "testing", "test cases", "bug reporting", "jira", "regression",
        "integration testing", "api testing", "postman", "test plan", "test strategy",
        "functional testing", "smoke testing", "automation", "defect", "agile",
    ],
    "sdet": [
        "selenium", "pytest", "junit", "api testing", "automation framework", "ci/cd",
        "performance testing", "rest assured", "bdd", "cucumber", "docker", "git",
        "javascript", "python", "java", "testng", "playwright", "appium",
    ],
    "python": [
        "python", "django", "fastapi", "flask", "pandas", "numpy", "sqlalchemy",
        "rest", "api", "docker", "git", "pytest", "celery", "redis", "pydantic",
        "asyncio", "microservices", "postgresql", "mongodb",
    ],
    "java": [
        "java", "spring", "spring boot", "maven", "gradle", "junit", "microservices",
        "jvm", "hibernate", "rest", "api", "docker", "kubernetes", "kafka",
        "jpa", "multithreading", "design patterns",
    ],
    "javascript": [
        "javascript", "typescript", "react", "nodejs", "express", "html", "css",
        "webpack", "jest", "rest", "api", "git", "npm", "graphql", "nextjs",
    ],
    "frontend": [
        "react", "angular", "vue", "typescript", "html", "css", "webpack",
        "responsive design", "accessibility", "performance", "git", "jest",
        "figma", "css-in-js", "state management",
    ],
    "backend": [
        "api", "rest", "sql", "nosql", "microservices", "docker", "kubernetes",
        "caching", "messaging", "git", "ci/cd", "database design", "kafka",
        "redis", "postgresql", "system design",
    ],
    "fullstack": [
        "react", "nodejs", "python", "java", "sql", "rest", "api",
        "docker", "git", "html", "css", "typescript", "postgresql", "mongodb",
        "ci/cd", "system design",
    ],
    "data": [
        "python", "sql", "pandas", "numpy", "spark", "tableau", "power bi",
        "etl", "data warehouse", "pipeline", "machine learning", "excel",
        "data modeling", "airflow", "bigquery", "snowflake", "dbt",
    ],
    "data engineer": [
        "python", "sql", "spark", "airflow", "kafka", "etl", "data pipeline",
        "aws", "gcp", "azure", "dbt", "snowflake", "bigquery", "redshift",
        "docker", "git", "data modeling", "data warehouse",
    ],
    "ml": [
        "python", "tensorflow", "pytorch", "scikit-learn", "pandas", "numpy",
        "model training", "deployment", "mlops", "docker", "hugging face",
        "feature engineering", "a/b testing", "model evaluation",
    ],
    "ai": [
        "python", "langchain", "llm", "openai", "pytorch", "tensorflow",
        "embedding", "vector database", "rag", "model deployment", "prompt engineering",
        "faiss", "transformers", "fine-tuning", "api", "generative ai",
    ],
    "devops": [
        "docker", "kubernetes", "ci/cd", "jenkins", "terraform", "ansible",
        "aws", "azure", "gcp", "monitoring", "linux", "bash", "helm",
        "prometheus", "grafana", "git", "infrastructure as code",
    ],
    "cloud": [
        "aws", "azure", "gcp", "terraform", "kubernetes", "docker",
        "serverless", "iam", "vpc", "ci/cd", "linux", "cloudformation",
        "lambda", "ec2", "s3", "networking",
    ],
    "product": [
        "product roadmap", "user stories", "agile", "scrum", "stakeholder",
        "kpi", "metrics", "a/b testing", "jira", "wireframe", "market research",
        "go-to-market", "data-driven", "customer", "prioritization",
    ],
    "analyst": [
        "sql", "python", "excel", "tableau", "power bi", "data analysis",
        "reporting", "kpi", "dashboard", "statistics", "business intelligence",
        "stakeholder", "requirements", "documentation",
    ],
    "engineer": [
        "software development", "system design", "api", "git", "docker",
        "ci/cd", "agile", "code review", "testing", "debugging",
        "microservices", "cloud", "database",
    ],
}


def _get_role_keywords(target_role: str) -> list[str]:
    role_lower = target_role.lower()
    # Try longest match first (e.g. "data engineer" before "data")
    sorted_keys = sorted(_ROLE_KEYWORDS.keys(), key=len, reverse=True)
    for key in sorted_keys:
        if key in role_lower:
            return _ROLE_KEYWORDS[key]
    # Fallback: tokenize role title and return non-stop words
    words = re.findall(r"[a-z0-9+#.]{2,}", role_lower)
    return [w for w in words if w not in _STOP]


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9+#./]{2,}", text.lower())
    return {w for w in words if w not in _STOP and len(w) > 2}


def _extract_present_strengths(resume_text: str, role_keywords: list[str]) -> list[str]:
    """Pull actual resume lines/phrases that relate to the role."""
    strengths: list[str] = []
    text_lower = resume_text.lower()
    resume_terms = _tokens(resume_text)

    # Matched technical skills
    matched_skills = [kw for kw in role_keywords if kw.lower() in text_lower]
    if matched_skills:
        strengths.append(f"Technical skills found: {', '.join(matched_skills[:6])}")

    # Check for quantified impact
    if re.search(r"\d+\s*%|\d+x\b|\$\s*\d+|\d+\s*(k|m|million|lakh)", text_lower):
        strengths.append("Resume includes quantified achievements (numbers/percentages)")

    # Leadership signals
    if re.search(r"\b(led|owned|architected|built|designed|launched|managed\s+team|mentored)\b", text_lower):
        strengths.append("Shows ownership and leadership with action verbs")

    # Project work
    if re.search(r"\b(projects?|portfolio|github|open.?source)\b", text_lower):
        strengths.append("Personal projects or portfolio work mentioned")

    # Relevant certifications
    if re.search(r"\b(certified|certification|aws|azure|gcp|pmp|scrum|itil)\b", text_lower):
        strengths.append("Certifications or credentials present")

    return strengths[:5]


def _generate_role_improvements(
    role: str,
    missing: list[str],
    resume_text: str,
    fmt: int,
    exp: int,
) -> list[str]:
    """Generate specific, role-aware improvement suggestions."""
    improvements: list[str] = []
    text_lower = resume_text.lower()

    if missing:
        top_missing = missing[:4]
        improvements.append(
            f"Add {role}-specific keywords to your Skills section: "
            f"{', '.join(top_missing)}"
        )

    # No metrics/numbers
    if not re.search(r"\d+\s*%|\d+x\b|\$\s*\d+|\d+\s*(k|m|million|lakh)", text_lower):
        improvements.append(
            "Add measurable impact to your experience bullets "
            "(e.g. 'reduced test execution time by 40%', 'automated 200+ test cases')"
        )

    # No leadership/ownership language
    if not re.search(r"\b(led|owned|architected|designed|launched|managed)\b", text_lower):
        improvements.append(
            "Use stronger action verbs to show ownership: "
            "'Led', 'Designed', 'Architected', 'Owned' rather than 'Worked on' or 'Helped with'"
        )

    # Missing summary section
    if not re.search(r"\b(summary|objective|profile|about)\b", text_lower):
        improvements.append(
            f"Add a 2-3 line Professional Summary at the top tailored to {role} — "
            "recruiters scan this in the first 6 seconds"
        )

    # Generic — mention the role
    improvements.append(
        f"Mirror language from {role} job descriptions in your resume — "
        "ATS systems reward exact keyword matches from the JD"
    )

    return improvements[:5]


def _heuristic_ats_score(resume_text: str, target_role: str, years_experience: float) -> ATSResumeScore:
    role_keywords = _get_role_keywords(target_role)
    resume_terms = _tokens(resume_text)
    text_lower = resume_text.lower()

    matched = [kw for kw in role_keywords if kw.lower() in text_lower]
    missing = [kw for kw in role_keywords if kw.lower() not in text_lower]

    keyword_pct = int(round(100 * len(matched) / max(len(role_keywords), 1)))
    keyword_pct = max(20, min(100, keyword_pct))

    # Formatting score
    fmt = 55
    if len(resume_text) > 1500:
        fmt += 10
    if re.search(r"\b(experience|work history|employment)\b", text_lower):
        fmt += 8
    if re.search(r"\b(skills|technical skills|tools|technologies)\b", text_lower):
        fmt += 8
    if re.search(r"\b(education|degree|university|college)\b", text_lower):
        fmt += 6
    if re.search(r"\d+\s*%|\d+x\b|\$\s*\d+|\d+\s*(k|m|million|lakh)", text_lower):
        fmt += 10
    if re.search(r"\b(projects?|portfolio|github)\b", text_lower):
        fmt += 3
    if re.search(r"\b(summary|objective|profile|about|career|professional|introduction|bio|overview)\b", text_lower[:1500]):
        fmt += 5
    fmt = max(35, min(100, fmt))

    # Experience clarity
    exp = 50
    if re.search(r"\b\d+\+?\s+years?\b", text_lower):
        exp += 15
    if re.search(r"\b(led|owned|architected|built|delivered|launched|designed|managed)\b", text_lower):
        exp += 12
    if re.search(r"\d+\s*%|\d+x\b|\$\s*\d+", text_lower):
        exp += 10
    if years_experience >= 2:
        exp += 5
    if years_experience >= 5:
        exp += 8
    exp = max(35, min(100, exp))

    overall = int(round(keyword_pct * 0.5 + fmt * 0.25 + exp * 0.25))
    overall = max(20, min(100, overall))

    # Role readiness
    if overall >= 80:
        role_readiness = f"Strong match for {target_role}"
    elif overall >= 65:
        role_readiness = f"Good fit with minor gaps for {target_role}"
    elif overall >= 50:
        role_readiness = f"Partial match — key skills missing for {target_role}"
    else:
        role_readiness = f"Significant gaps for {target_role} — resume needs strengthening"

    # Hiring prospect
    if overall >= 75:
        hiring_prospect = (
            f"Your resume has a strong chance of passing the ATS screen for {target_role}. "
            f"The main differentiator will be your cover letter and interview performance. "
            f"Ensure your top matching skills ({', '.join(matched[:3])}) are front and centre."
        )
    elif overall >= 55:
        hiring_prospect = (
            f"Moderate ATS pass likelihood for {target_role}. "
            f"Adding {', '.join(missing[:3])} to your skills section could push you past the filter. "
            f"Quantifying your impact with numbers will strengthen the human review stage."
        )
    else:
        hiring_prospect = (
            f"The resume currently misses several key signals for {target_role}. "
            f"Priority additions: {', '.join(missing[:4])}. "
            f"Consider adding a targeted skills section and a role-specific summary to improve ATS pass rate."
        )

    # Summary — no mention of "enable AI"
    summary = (
        f"Resume scores {overall}% for {target_role}. "
        f"Keyword match: {keyword_pct}% "
        f"({len(matched)} of {len(role_keywords)} expected skills found). "
        f"Formatting: {fmt}%, Experience clarity: {exp}%."
    )

    # Specific gaps
    gaps: list[str] = []
    if missing:
        top = missing[:5]
        gaps.append(f"Missing {target_role} keywords: {', '.join(top)}")
    if fmt < 70:
        if not re.search(r"\d+\s*%|\d+x\b", text_lower):
            gaps.append("No quantified achievements found — add numbers (%, ms, scale, revenue)")
    if exp < 65:
        if not re.search(r"\b(led|owned|architected|built|launched)\b", text_lower):
            gaps.append("Weak ownership language — replace 'worked on' with 'led', 'built', 'owned'")
    if not re.search(r"\b(summary|objective|profile|about|career|professional|introduction|bio|overview)\b", text_lower[:1500]):
        gaps.append("No professional summary section detected — add a 2-3 line summary at the top")

    present_strengths = _extract_present_strengths(resume_text, role_keywords)
    improvements = _generate_role_improvements(target_role, missing, resume_text, fmt, exp)

    return ATSResumeScore(
        overall_pct=overall,
        keyword_match_pct=keyword_pct,
        formatting_score_pct=fmt,
        experience_clarity_pct=exp,
        summary=summary,
        role_readiness=role_readiness,
        hiring_prospect=hiring_prospect,
        present_strengths=present_strengths,
        matched_keywords=matched[:15],
        missing_keywords=missing[:15],
        critical_missing=missing[:3],
        gaps=gaps,
        improvements=improvements,
        analysis_type="heuristic",
    )


# ── Public entry point ────────────────────────────────────────────────────────

def score_resume_ats(resume_text: str, target_role: str, years_experience: float) -> ATSResumeScore:
    """
    Score a resume against a target role.
    Tries LLM first; on quota/rate-limit falls back to intelligent heuristics instantly.
    """
    try:
        return _llm_ats_score(resume_text, target_role, years_experience)
    except Exception as exc:
        err_str = str(exc).lower()
        if any(k in err_str for k in (
            "quota", "exhausted", "rate", "429", "resource",
            "api key", "invalid", "401", "403", "permission",
        )):
            return _heuristic_ats_score(resume_text, target_role, years_experience)
        raise
