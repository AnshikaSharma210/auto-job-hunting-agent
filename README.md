# Job Hunt Pro

[![Live App](https://img.shields.io/badge/Live%20App-autojobhuntingagent.streamlit.app-6366f1?style=for-the-badge)](https://autojobhuntingagent.streamlit.app/)

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.x-FF4B4B?logo=streamlit)](https://streamlit.io/)
[![LangChain](https://img.shields.io/badge/LangChain-0.3-green)](https://python.langchain.com/)
[![Supabase](https://img.shields.io/badge/Supabase-Auth%20%26%20DB-3ECF8E?logo=supabase&logoColor=white)](https://supabase.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

An AI-powered job hunting copilot for busy professionals. Upload your resume once — the agent scores it against your target roles using ATS logic, searches across 8+ job sources in real time, ranks every opening by actual hiring probability, and generates a tailored cover letter for each application. All data persists per user account.

---

## What it does

**Resume & ATS Screening**
Runs an ATS-style analysis per target role using an LLM. Returns an overall pass-rate percentage, keyword match, formatting score, experience clarity, readiness level, hiring outlook, critical gaps, and a prioritised list of improvements — not a generic score, but role-specific actionable insights.

**Multi-source Job Discovery**
Searches concurrently across JSearch (aggregates LinkedIn, Indeed, Glassdoor, Naukri), Adzuna, Remotive, Arbeitnow, Jobicy, The Muse, and 110+ company career pages via Greenhouse / Lever / Ashby APIs. Results are deduplicated, relevance-filtered (hard-blocks sales/support/non-tech titles), and ranked by hiring chance.

**AI Job Ranking**
Each job gets a composite score across 7 dimensions: hiring chance, resume fit, company brand, growth potential, flexibility, compensation fit, and work environment. The top N results are deep-ranked by the LLM; the rest use a fast local heuristic scorer — keeping costs near zero while maintaining quality.

**Shortlist & Resume Tailoring**
Users shortlist roles and get per-job tailoring suggestions: keywords to add, existing bullets to emphasise, and a ready-to-paste summary paragraph optimised for that specific JD.

**Apply with Cover Letter**
AI drafts a personalised cover letter per role. Users review, edit inline, open the employer's application page, and confirm to log it.

**Application Tracker**
Every confirmed application is stored with company, role, platform, date, and status. Filterable by company name, status, and date. Status updates persist to the database.

---

## Tech Stack

| Layer | Technology |
|---|---|
| UI | Streamlit · custom dark theme CSS |
| LLM | Groq `llama-3.3-70b` (primary, free, no daily cap) · Google Gemini `gemini-3.6-flash` (fallback) |
| RAG / Embeddings | FAISS vector store · `all-MiniLM-L6-v2` sentence-transformers (local, zero-cost) |
| Orchestration | LangChain · Pydantic structured outputs |
| Auth & Storage | Supabase (PostgreSQL + Storage) · Row-Level Security per user |
| Job Sources | JSearch (RapidAPI) · Adzuna · Remotive · Arbeitnow · Jobicy · The Muse · Greenhouse / Lever / Ashby ATS APIs |
| Resume Parsing | PyPDF |
| Reliability | API key rotation (multiple Groq + Gemini keys) · heuristic fallback when LLM is unavailable · `truststore` for SSL proxy compatibility |

---

## Architecture

```
streamlit_app.py                  # UI + session management + Supabase sync
│
├── auto_job_hunting_agent/
│   ├── pipeline.py               # search → filter → rank → score orchestrator
│   ├── config.py                 # settings from .env / st.secrets
│   ├── models.py                 # Pydantic: JobPosting, JobMatchResult, ATSResumeScore, ApplicationRecord
│   ├── db.py                     # Supabase wrapper: auth, resume, shortlist, applications
│   │
│   ├── rag/
│   │   └── resume_store.py       # PDF ingestion · chunking · FAISS index · similarity search
│   │
│   ├── llm/
│   │   ├── key_manager.py        # Groq-first key rotation · per-minute rate-limit blocking · Gemini fallback
│   │   ├── ats_scoring.py        # role-specific ATS analysis · LLM + heuristic fallback
│   │   ├── company_ranking.py    # 7-dimension job scoring via structured LLM output
│   │   ├── heuristic_ranking.py  # local keyword-based ranking (no API, instant)
│   │   ├── scoring.py            # resume fit scoring · cover letter generation
│   │   └── resume_tailor.py      # per-job keyword suggestions + tailored summary
│   │
│   └── scrapers/
│       ├── jsearch.py            # JSearch (LinkedIn / Indeed / Glassdoor / Naukri)
│       ├── remotive.py           # Remotive (remote tech roles)
│       ├── arbeitnow.py          # Arbeitnow (global tech)
│       ├── jobicy.py             # Jobicy (remote)
│       ├── themuse.py            # The Muse
│       ├── company_careers.py    # Greenhouse · Lever · Ashby parallel scraper
│       └── company_list.py       # 110+ curated companies with ATS platform slugs
```

---

## Key Design Decisions

**Groq-first LLM strategy** — Groq's free tier has no daily cap (only a per-minute rate limit). The key manager tries each configured Groq key in round-robin; a rate-limited key is blocked for 62 seconds then re-queued. Gemini is the fallback. This gives effectively unlimited daily LLM usage with zero cost.

**Hybrid ranking** — Only the top N candidates (configurable) get a full LLM deep-rank. The rest receive an instant local heuristic score. This reduces LLM calls by ~80% while keeping the ranked list accurate where it matters.

**Title-only relevance filter** — Job descriptions frequently mention unrelated roles (e.g. a sales JD mentioning "engineer" in benefits). Filtering on job title only, with role abbreviation expansion and a hard-block list for non-tech titles, produces significantly higher signal-to-noise.

**Per-user isolation** — Supabase Row-Level Security ensures every DB query is scoped to the authenticated user. Resume files are stored under `{user_id}/` in a private Storage bucket. No user can access another's data even if they know the job ID.

---

## Live App

**[autojobhuntingagent.streamlit.app](https://autojobhuntingagent.streamlit.app/)** — sign up with email, no API keys needed.

---

## License

MIT
