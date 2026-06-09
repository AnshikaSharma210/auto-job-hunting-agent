from __future__ import annotations

import hashlib

from auto_job_hunting_agent.models import JobPosting


def mock_job_postings(
    role: str,
    location: str,
    salary_min_lpa: float | None,
    count: int = 6,
) -> list[JobPosting]:
    """Deterministic synthetic listings for demos and tests without any network calls."""
    smin = salary_min_lpa or 0.0
    templates = [
        {
            "title": f"Staff {role} Engineer",
            "company": "RiverStack Labs",
            "location": location or "Remote — India",
            "salary": "₹45–65 LPA",
            "desc": (
                f"We are hiring a Staff {role} Engineer to design and own core backend services. "
                "You will lead API design, code reviews, and partner with product and data teams. "
                "Strong Python, distributed systems, and cloud (AWS/GCP) required. "
                "Experience with LangChain, LLMs, or agentic systems is a plus. "
                "We are a fast-growing startup with a strong engineering culture."
            ),
        },
        {
            "title": f"Senior ML Platform Engineer ({role})",
            "company": "Northwind Analytics",
            "location": location or "Hybrid — Bengaluru",
            "salary": "₹38–52 LPA",
            "desc": (
                f"Build ML platforms, feature stores, and batch/stream pipelines. "
                "Deep Python, Kubernetes, and observability required. "
                "Prior RAG or retrieval systems experience preferred. "
                "The role sits at the intersection of applied ML and strong software engineering."
            ),
        },
        {
            "title": f"Product Engineer — Full Stack ({role})",
            "company": "Contour Payments",
            "location": location or "Remote",
            "salary": "₹32–44 LPA",
            "desc": (
                f"End-to-end product engineering: React/TypeScript frontends, FastAPI/Python services, "
                "and data integrations. Looking for pragmatic engineers who can ship quickly. "
                "Experience with Streamlit or internal tooling is a plus."
            ),
        },
        {
            "title": f"Principal {role} Architect",
            "company": "Meridian Systems",
            "location": location or "Pune / Remote",
            "salary": "₹70–90 LPA",
            "desc": (
                f"Lead architecture for enterprise-scale {role} platforms. "
                "Define technical strategy, mentor teams, and interface with C-suite stakeholders. "
                "15+ years expected. Domain-driven design and microservices expertise required."
            ),
        },
        {
            "title": f"AI/ML {role} Specialist",
            "company": "Helios AI",
            "location": location or "Bengaluru",
            "salary": "₹28–40 LPA",
            "desc": (
                f"Join our AI team building LLM-powered products. You will work on {role} integrations, "
                "prompt engineering, RAG pipelines, and deployment. "
                "3-5 years with Python and ML frameworks expected. OpenAI, LangChain, and vector DBs a plus."
            ),
        },
        {
            "title": f"Backend {role} Lead",
            "company": "Cascade Finance",
            "location": location or "Mumbai / Hybrid",
            "salary": "₹50–70 LPA",
            "desc": (
                f"Lead a team of 6 backend engineers building high-throughput {role} infrastructure. "
                "Own reliability, latency, and security objectives. "
                "Python, Go, and Kafka required. Prior fintech experience preferred."
            ),
        },
    ]
    out: list[JobPosting] = []
    for i, t in enumerate(templates[:count]):
        blob = f"{t['title']}:{t['company']}:{i}".encode()
        jid = hashlib.sha256(blob).hexdigest()[:20]
        out.append(
            JobPosting(
                id=jid,
                platform="mock",
                title=t["title"],
                company=t["company"],
                location=t["location"],
                salary_text=t["salary"],
                url=f"https://example.com/jobs/{jid}",
                description=t["desc"],
            )
        )
    return out
