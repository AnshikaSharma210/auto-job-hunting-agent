# Job Hunt Pro — AI-Powered Job Hunting Copilot

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.x-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![LangChain](https://img.shields.io/badge/LangChain-0.3-green?logo=chainlink&logoColor=white)](https://python.langchain.com/)
[![Google Gemini](https://img.shields.io/badge/LLM-Google%20Gemini-4285F4?logo=google&logoColor=white)](https://aistudio.google.com/)
[![FAISS](https://img.shields.io/badge/Vector%20Store-FAISS-orange)](https://faiss.ai/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Live App](https://img.shields.io/badge/🚀%20Live%20App-autojobhuntingagent.streamlit.app-6366f1)](https://autojobhuntingagent.streamlit.app/)

> An intelligent job-hunting copilot that scores your resume like an **ATS**, discovers and **ranks openings by hiring chance**, and guides a fully human-in-the-loop application workflow — complete with AI-drafted cover letters and a built-in application tracker.

**[▶ Try it live → autojobhuntingagent.streamlit.app](https://autojobhuntingagent.streamlit.app/)**

---

## Why this project?

Applying to jobs is time-consuming and opaque. Most people either mass-apply (low quality) or spend hours manually evaluating job postings. **Job Hunt Pro** automates the research and scoring so you can focus your energy only on roles where you have a genuine shot — with your resume, your experience, and your priorities in mind.

Key design choices:
- **No blind mass-apply.** You review, shortlist, and confirm every application.
- **Free to run.** Default stack uses Google Gemini's free tier + local sentence-transformer embeddings.
- **Multi-user cloud deployment.** Login with email, data persists per account via Supabase — no setup needed for end users.

---

## Features

| # | Tab | What it does |
|---|-----|-------------|
| 1 | **Resume & ATS** | Upload PDF/TXT (≤ 2 MB). Receive an ATS-style score per target role — keyword gaps, formatting signals, hiring prospect, and actionable improvement tips. |
| 2 | **Discover Roles** | Search up to 3 job titles simultaneously across **5 sources** (LinkedIn/Indeed/Naukri via JSearch, Adzuna, Remotive, and 70+ company career pages). Filter by Remote / Hybrid / On-site, city, and years of experience. |
| 3 | **Ranked Listings** | Every result gets a **hiring chance %** and sub-scores: resume fit, company brand, growth, flexibility, compensation fit, and work environment. Paginated results (5 per page) with a **source badge** showing where each role came from. |
| 4 | **Shortlist** | Bookmark roles you're interested in. Click **"Tailor resume for this role"** to get: keywords to add, existing bullet points to emphasise, and a ready-to-paste tailored summary paragraph. |
| 5 | **Apply** | AI generates a tailored cover letter for each role. Open the listing, review, confirm to log the application. |
| 6 | **My Applications** | Track every application: company, role, date applied, and current status (Applied → Interview → Offer → Rejected). |

---

## Demo

> Run locally with `streamlit run streamlit_app.py` — see [Quick start](#quick-start) below.

The app opens at `https://autojobhuntingagent.streamlit.app/` with a dark, professional UI.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **UI** | Streamlit (custom dark theme, compact CSS) |
| **Orchestration** | LangChain tool-calling agent |
| **LLM** | Google Gemini `gemini-2.0-flash` (default, free) · OpenAI GPT-4o (optional) |
| **Embeddings** | `all-MiniLM-L6-v2` via `sentence-transformers` (local, free) · Google / OpenAI (optional) |
| **Vector store** | FAISS (in-memory, no native build on Windows) |
| **Resume parsing** | `PyMuPDF` for PDF extraction |
| **Job data** | JSearch (LinkedIn/Indeed/Glassdoor via RapidAPI) · Adzuna · Remotive · 70+ company career pages (Greenhouse / Lever / Ashby) · mock demo data |
| **Persistence** | Local JSON under `.data/` (gitignored) |
| **SSL handling** | `truststore` for corporate proxy compatibility |

---

## Architecture

```
streamlit_app.py
├── Tab 1: Resume & ATS    → rag/resume_store.py (FAISS)
│                             llm/ats_scoring.py (ATSResumeScore)
├── Tab 2: Discover roles  → pipeline.search_and_score()
│   ├── scrapers/          →   jsearch.py | adzuna.py | mock_data.py
│   ├── llm/               →   company_ranking.py (JobMatchResult)
│   └── llm/               →   heuristic_ranking.py (local fallback)
├── Tab 3-4: Shortlist     → session_state + applications_store.py
├── Tab 5: Apply           → llm/scoring.py (cover letters)
└── Tab 6: My Applications → applications_store.py (.data/applications.json)

auto_job_hunting_agent/
├── config.py              # centralised settings from .env
├── models.py              # Pydantic: JobPosting, FitScore, ATSResumeScore, ApplicationRecord
├── pipeline.py            # orchestrates search → score → rank
├── rag/
│   ├── resume_store.py    # chunk, embed, FAISS index
│   └── context_builder.py # section-grouped context per JD
├── llm/
│   ├── ats_scoring.py     # ATS % + actionable insights (LLM + heuristic fallback)
│   ├── company_ranking.py # hiring_chance + 6 company dimension scores
│   ├── heuristic_ranking.py  # local keyword-based ranking (no API)
│   └── scoring.py         # fit scoring + cover letter generation
├── scrapers/
│   ├── jsearch.py         # RapidAPI JSearch
│   ├── adzuna.py          # Adzuna REST API
│   └── mock_data.py       # offline demo data
├── applications_store.py  # CRUD for application log
└── error_handling.py      # user-friendly API error messages
```

---

## Quick Start

```bash
git clone https://github.com/AnshikaSharma210/auto-job-hunting-agent.git
cd auto-job-hunting-agent

python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

pip install -r requirements.txt

cp .env.example .env
# Edit .env — add your GOOGLE_API_KEY (free, 60 seconds to get)
# https://aistudio.google.com/app/apikey

streamlit run streamlit_app.py
```

Open **https://autojobhuntingagent.streamlit.app/**.

---

## Environment Variables

Copy `.env.example` to `.env` and fill in the values you need.

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `google` | `google` or `openai` |
| `EMBEDDING_PROVIDER` | `local` | `local` (free) · `google` · `openai` |
| `GOOGLE_API_KEY` | — | Free key from [Google AI Studio](https://aistudio.google.com/app/apikey) |
| `GOOGLE_CHAT_MODEL` | `gemini-2.0-flash` | Gemini model for scoring & letters |
| `OPENAI_API_KEY` | — | Only required when `LLM_PROVIDER=openai` |
| `JOB_SOURCE` | `multi` | `multi` (all sources) · `jsearch` · `adzuna` · `mock` |
| `JSEARCH_API_KEY` | — | [RapidAPI JSearch](https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch) key |
| `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` | — | [Adzuna developer](https://developer.adzuna.com/) credentials |
| `ENABLE_REMOTIVE` | `true` | Include remote-only roles from Remotive (free, no key) |
| `ENABLE_COMPANY_CAREERS` | `true` | Query 70+ company career pages via Greenhouse / Lever / Ashby (free, no key) |
| `COMPANY_LIST_EXTRA` | — | Add custom companies: `"MyCompany:greenhouse:mycompany-slug,..."` |
| `MAX_RESULTS` | `20` | Max jobs returned per search |
| `MAX_LLM_RANKINGS` | `3` | Max Gemini ranking calls per search (rest use local scoring) |
| `MAX_UPLOAD_MB` | `2` | Resume upload size cap |
| `LOCAL_EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | `sentence-transformers` model name |

**Minimum setup (100% free):**

```env
LLM_PROVIDER=google
EMBEDDING_PROVIDER=local
GOOGLE_API_KEY=your_key_here
GOOGLE_CHAT_MODEL=gemini-2.0-flash
JOB_SOURCE=jsearch
JSEARCH_API_KEY=your_rapidapi_key
```

---

## Deploying to Streamlit Community Cloud

The app is **already live** at [autojobhuntingagent.streamlit.app](https://autojobhuntingagent.streamlit.app/).

To deploy your own instance:
1. Fork this repo to your GitHub account.
2. Create a free [Supabase](https://supabase.com) project — run `supabase_schema.sql` in the SQL editor.
3. Go to [share.streamlit.io](https://share.streamlit.io) → **New app** → select `streamlit_app.py`.
4. Under **Advanced settings → Secrets**, add your keys (see `.streamlit/secrets.toml.example`).
5. Click **Deploy** — no Selenium, no Chrome, no server setup required.

### Multi-user login & persistent storage

The hosted app uses **Supabase** for authentication and storage:

- Users sign up with email — no API keys or setup required on their end.
- Each user's resume, shortlist, and applications are stored privately in Supabase (isolated per account).
- Data persists across sessions and devices — upload your resume once and it's there next time you log in.
- The host's Groq and Google API keys are shared silently — users get full AI features out of the box.

---

## API Quota Tips

The default configuration is already optimised for free-tier usage:

| Setting | Why it saves quota |
|---------|--------------------|
| `EMBEDDING_PROVIDER=local` | Resume indexing runs fully on your machine (no API calls) |
| `MAX_LLM_RANKINGS=3` | Only the top 3 listings get full Gemini analysis; the rest use free keyword scoring |
| ATS is optional in the UI | Triggered on demand, not on every upload |
| Sleep between calls | 5-second pauses between consecutive LLM calls to avoid rate-limit errors |

Set the **Deep AI ranking** slider to `0` to search entirely without using Gemini.

---

## Project Highlights (for recruiters)

- **Context Engineering / RAG pipeline:** Resume is chunked, embedded into FAISS, and the most relevant sections are retrieved per job description at query time — keeping LLM context windows lean and accurate.
- **LangChain agents:** Tool-calling agent orchestrates multi-step workflows (search → score → rank → generate) with graceful fallbacks.
- **Heuristic + LLM hybrid ranking:** Local rule-based scoring handles the bulk of listings; LLM deep analysis is reserved for the top candidates — reducing API costs by 80%+.
- **Pydantic data models:** Strict typed schemas (`JobPosting`, `FitScore`, `ATSResumeScore`, `ApplicationRecord`) throughout the pipeline.
- **Production-grade error handling:** API quota exhaustion, SSL proxy issues, file stream errors, and rate limits are all caught and surfaced as friendly, non-technical messages.
- **Custom Streamlit dark UI:** Extensive CSS overrides for compact, professional styling — no default Streamlit look.

---

## Compliance & Limitations

- ATS scores simulate common screening heuristics; they are directional guidance, not a guarantee of any employer's internal system.
- The Apply flow opens the employer URL — you fill and submit the form yourself.
- Use official APIs (JSearch, Adzuna) and respect each job board's Terms of Service.
- Resume files are capped at 2 MB for performance and cost reasons.

---

## License

MIT — use freely for personal job search. Do not commit `.env` or `.data/` to version control.
