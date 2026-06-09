from __future__ import annotations

import re

from auto_job_hunting_agent.models import JobMatchResult, JobPosting

_STOP = {
    "a", "an", "the", "and", "or", "for", "with", "in", "on", "at", "to", "of", "is", "are",
    "as", "by", "from", "be", "this", "that", "will", "you", "your", "our", "we", "job",
}

_TOP_BRANDS = {
    "google", "microsoft", "amazon", "meta", "apple", "netflix", "adobe", "salesforce",
    "uber", "airbnb", "nvidia", "stripe", "atlassian", "oracle", "ibm", "sap",
}
_STRONG_INDIAN_BRANDS = {
    "flipkart", "swiggy", "zomato", "razorpay", "paytm", "freshworks", "zoho",
    "infosys", "tcs", "wipro", "hcl", "meesho", "phonepe",
}


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9+#.]{2,}", text.lower())
    return {w for w in words if w not in _STOP and len(w) > 2}


def _score_company_brand(company: str, platform: str) -> int:
    c = company.lower().strip()
    score = 52
    if any(x in c for x in _TOP_BRANDS):
        score = 88
    elif any(x in c for x in _STRONG_INDIAN_BRANDS):
        score = 78
    elif len(c) >= 4:
        score = 64
    if platform.lower() in {"linkedin", "indeed"}:
        score += 3
    return max(35, min(95, score))


def _score_growth(description: str, title: str) -> int:
    text = f"{title} {description}".lower()
    score = 50
    if re.search(r"\b(lead|senior|principal|staff|architect)\b", text):
        score += 12
    if re.search(r"\b(ownership|roadmap|mentor|leadership|cross-functional)\b", text):
        score += 10
    if re.search(r"\b(startup|scale|hypergrowth|0 to 1|greenfield)\b", text):
        score += 8
    if re.search(r"\b(contract|intern|temporary)\b", text):
        score -= 10
    return max(30, min(90, score))


def _score_flexibility(location: str, description: str) -> int:
    text = f"{location} {description}".lower()
    if "remote" in text:
        return 88
    if "hybrid" in text:
        return 72
    if re.search(r"\bon[-\s]?site\b|office", text):
        return 48
    return 58


def _score_work_env(description: str) -> int:
    text = description.lower()
    score = 52
    if re.search(r"\b(inclusive|collaborative|learning|mentorship|wellbeing)\b", text):
        score += 12
    if re.search(r"\b(agile|engineering culture|developer experience)\b", text):
        score += 8
    if re.search(r"\b(night shift|weekend|pressure|fast-paced)\b", text):
        score -= 8
    return max(35, min(88, score))


def _score_compensation(salary_text: str | None, title: str, years_experience: float) -> int:
    score = 52
    text = (salary_text or "").lower()
    if text and "not listed" not in text:
        score += 10
        nums = [int(x.replace(",", "")) for x in re.findall(r"\d[\d,]{2,}", text)]
        if nums:
            approx = max(nums)
            if approx >= 3_000_000:
                score += 12
            elif approx >= 1_500_000:
                score += 8
            elif approx >= 800_000:
                score += 4
    if re.search(r"\b(senior|lead|principal|staff)\b", title.lower()) and years_experience >= 5:
        score += 8
    return max(35, min(92, score))


def heuristic_job_match(
    job: JobPosting,
    resume_text: str,
    target_roles: list[str],
    years_experience: float,
) -> JobMatchResult:
    """Fast local ranking — no API calls. Used for most listings on free tier."""
    role_blob = " ".join(target_roles)
    resume_toks = _tokens(resume_text)
    job_toks = _tokens(f"{job.title} {job.description} {job.company or ''}")
    role_toks = _tokens(role_blob)

    if not job_toks:
        overlap = 0.0
    else:
        overlap = len(resume_toks & job_toks) / max(len(job_toks), 1)
    role_overlap = len(resume_toks & role_toks) / max(len(role_toks), 1) if role_toks else 0.0

    resume_fit = int(min(100, 35 + overlap * 120 + role_overlap * 25))
    brand = _score_company_brand(job.company or "", job.platform)
    growth = _score_growth(job.description, job.title)
    flex = _score_flexibility(job.location or "", job.description)
    work_env = _score_work_env(job.description)
    compensation = _score_compensation(job.salary_text, job.title, years_experience)
    hiring = int(
        min(
            100,
            resume_fit * 0.5
            + brand * 0.15
            + growth * 0.12
            + flex * 0.08
            + work_env * 0.08
            + compensation * 0.07
            + (5 if job.url else 0),
        )
    )

    strengths: list[str] = []
    for tok in sorted(resume_toks & job_toks, key=len, reverse=True)[:4]:
        strengths.append(tok.replace(".", " ").title())

    gaps: list[str] = []
    missing = list((job_toks - resume_toks) & role_toks)[:3]
    for m in missing:
        gaps.append(f"Add experience with {m}")

    company = job.company or "the company"
    letter = (
        f"Dear Hiring Manager,\n\n"
        f"I am writing to apply for the {job.title} role at {company}. "
        f"With {years_experience:g} years of experience aligned to {role_blob}, "
        f"I believe my background is a strong match for your team.\n\n"
        f"My resume highlights skills relevant to this posting. I would welcome "
        f"the opportunity to discuss how I can contribute.\n\n"
        f"Sincerely,\n[Your Name]"
    )

    return JobMatchResult(
        hiring_chance=hiring,
        resume_fit=resume_fit,
        company_reputation=brand,
        work_environment=work_env,
        compensation_fit=compensation,
        growth_potential=growth,
        flexibility=flex,
        summary=(
            f"Quick match (no AI call): {resume_fit}% resume overlap with this posting. "
            f"Use “Deep rank” on top picks for full company analysis."
        ),
        strengths=strengths or ["Profile overlap with role keywords"],
        gaps=gaps or ["Run deep AI rank for detailed gap analysis"],
        company_highlights=[
            f"Brand score {brand}/100",
            f"Growth score {growth}/100",
            f"Flex score {flex}/100",
        ],
        tailored_cover_letter=letter,
    )
