from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class JobPosting(BaseModel):
    """Normalized job listing from any source."""

    id: str = Field(description="Stable id within a session (hash or source id).")
    platform: str = Field(description="linkedin | naukri | mock | jsearch | adzuna")
    title: str
    company: str | None = None
    location: str | None = None
    salary_text: str | None = None
    url: str | None = None
    description: str = Field(default="", description="Full or partial JD text for scoring.")


class FitScore(BaseModel):
    """Legacy fit payload; prefer JobMatchResult for new flows."""

    score: int = Field(ge=0, le=100)
    summary: str
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    tailored_cover_letter: str


class ATSResumeScore(BaseModel):
    """ATS-style resume screening score for a target role."""

    overall_pct: int = Field(ge=0, le=100, description="Overall ATS pass likelihood.")
    keyword_match_pct: int = Field(ge=0, le=100)
    formatting_score_pct: int = Field(ge=0, le=100)
    experience_clarity_pct: int = Field(ge=0, le=100)
    summary: str
    matched_keywords: list[str] = Field(default_factory=list)
    missing_keywords: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    # Enhanced fields from LLM analysis
    role_readiness: str = Field(default="", description="e.g. 'Strong Mid-level', 'Junior — needs 1 more year'")
    critical_missing: list[str] = Field(default_factory=list, description="Must-have skills absent from resume")
    present_strengths: list[str] = Field(default_factory=list, description="Resume highlights relevant to the role")
    hiring_prospect: str = Field(default="", description="Plain-English hiring outlook for this role")


class JobMatchResult(BaseModel):
    """Ranked job match: resume fit + company/hiring outlook."""

    hiring_chance: int = Field(
        ge=0,
        le=100,
        description="Likelihood of success if you apply now (primary rank key).",
    )
    resume_fit: int = Field(ge=0, le=100)
    company_reputation: int = Field(ge=0, le=100)
    work_environment: int = Field(ge=0, le=100)
    compensation_fit: int = Field(ge=0, le=100)
    growth_potential: int = Field(ge=0, le=100)
    flexibility: int = Field(ge=0, le=100)
    summary: str
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    company_highlights: list[str] = Field(default_factory=list)
    tailored_cover_letter: str

    @property
    def score(self) -> int:
        """Alias for UI components that expect .score."""
        return self.hiring_chance


ApplicationStatus = Literal[
    "Applied",
    "Under Review",
    "Interview",
    "Offer",
    "Rejected",
    "Withdrawn",
]


class ApplicationRecord(BaseModel):
    id: str
    job_id: str
    company: str
    role: str
    platform: str
    applied_at: str  # ISO date
    status: ApplicationStatus = "Applied"
    job_url: str | None = None
    cover_letter: str = ""
    notes: str = ""

    @classmethod
    def new(
        cls,
        job_id: str,
        company: str,
        role: str,
        platform: str,
        job_url: str | None,
        cover_letter: str,
    ) -> ApplicationRecord:
        return cls(
            id=f"app_{job_id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            job_id=job_id,
            company=company,
            role=role,
            platform=platform,
            applied_at=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            status="Applied",
            job_url=job_url,
            cover_letter=cover_letter,
        )
