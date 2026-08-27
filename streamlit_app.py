from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from auto_job_hunting_agent.ssl_patch import patch as _ssl_patch

_ssl_patch()

import streamlit as st

from auto_job_hunting_agent.applications_store import (
    add_application,
    load_applications,
    update_status,
)
from auto_job_hunting_agent.config import SETTINGS
from auto_job_hunting_agent.db import (
    is_supabase_configured,
    sign_in,
    sign_up,
    sign_out,
    get_user,
    save_resume_meta,
    load_resume_meta,
    upload_resume_file,
    download_resume_file,
    load_shortlist,
    upsert_shortlist,
    delete_shortlist_item,
    load_applications_db,
    add_application_db,
    update_application_status_db,
)
from auto_job_hunting_agent.models import (
    ApplicationRecord,
    ApplicationStatus,
    ATSResumeScore,
    FitScore,
    JobMatchResult,
    JobPosting,
)
from auto_job_hunting_agent.pipeline import JobHuntPipeline, ScoredJob

# ── page ─────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Job Hunt Pro",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Auth gate (Supabase cloud mode only) ─────────────────────────────────────
# In local mode (no SUPABASE_URL) the gate is skipped entirely.

def _sb_user() -> dict | None:
    """Return the current Supabase user dict, or None if not logged in."""
    return st.session_state.get("sb_user")


def _sb_uid() -> str | None:
    u = _sb_user()
    return u.id if u else None


def _render_login_page() -> None:
    """Full-page login / register screen (shown instead of app when not authenticated)."""
    st.markdown(
        """
<style>
.auth-card{max-width:420px;margin:60px auto;background:#1e293b;border-radius:14px;
  padding:36px 32px;box-shadow:0 4px 32px rgba(0,0,0,.45)}
.auth-title{font-size:1.6rem;font-weight:700;color:#f1f5f9;margin-bottom:4px;text-align:center}
.auth-sub{font-size:.88rem;color:#94a3b8;text-align:center;margin-bottom:24px}
</style>
<div class="auth-card">
  <div class="auth-title">Job Hunt Pro</div>
  <div class="auth-sub">Sign in or create a free account to get started</div>
</div>
""",
        unsafe_allow_html=True,
    )
    col = st.columns([1, 2, 1])[1]
    with col:
        mode = st.radio("", ["Sign in", "Create account"], horizontal=True, label_visibility="collapsed")
        email = st.text_input("Email", placeholder="you@email.com")
        password = st.text_input("Password", type="password", placeholder="••••••••")
        if mode == "Sign in":
            if st.button("Sign in", type="primary", use_container_width=True):
                if not email or not password:
                    st.error("Please enter your email and password.")
                else:
                    with st.spinner("Signing in…"):
                        result = sign_in(email.strip(), password)
                    if result["error"]:
                        st.error(result["error"])
                    else:
                        st.session_state["sb_user"] = result["user"]
                        st.session_state["sb_token"] = result["session"].access_token
                        st.rerun()
        else:
            if st.button("Create account", type="primary", use_container_width=True):
                if not email or not password:
                    st.error("Please fill in all fields.")
                elif len(password) < 6:
                    st.error("Password must be at least 6 characters.")
                else:
                    with st.spinner("Creating account…"):
                        result = sign_up(email.strip(), password)
                    if result["error"]:
                        st.error(result["error"])
                    elif result["session"]:
                        st.session_state["sb_user"] = result["user"]
                        st.session_state["sb_token"] = result["session"].access_token
                        st.rerun()
                    else:
                        st.success("Account created! Check your email for a confirmation link, then sign in.")


if is_supabase_configured():
    # Re-validate existing session token on each rerun
    token = st.session_state.get("sb_token")
    if token and not st.session_state.get("sb_user"):
        st.session_state["sb_user"] = get_user(token)

    if not _sb_user():
        _render_login_page()
        st.stop()

PAGE_SIZE = 10
WORK_MODES = ["Remote", "Hybrid", "On-site"]
LOCATIONS = [
    "Bangalore",
    "Mumbai",
    "Delhi NCR",
    "Hyderabad",
    "Pune",
    "Chennai",
    "Kolkata",
    "India (any city)",
    "International / Global",
]
STATUS_OPTIONS: list[ApplicationStatus] = [
    "Applied",
    "Under Review",
    "Interview",
    "Offer",
    "Rejected",
    "Withdrawn",
]

st.markdown(
    """
<style>
html,body,[class*="css"]{font-family:'Segoe UI',Arial,sans-serif}
.block-container{padding-top:0.6rem!important;padding-bottom:1rem!important}
[data-testid="InputInstructions"]{display:none!important}
/* compact list spacing */
ul,ol{margin:0.15rem 0!important;padding-left:1.1rem!important}
li{margin-bottom:0.1rem!important;line-height:1.4!important}
/* ── compact text inputs ── */
div[data-baseweb="input"]{min-height:34px!important;height:34px!important;box-shadow:none!important}
div[data-baseweb="input"]>div{min-height:34px!important;height:34px!important;padding:0 10px!important;box-shadow:none!important}
div[data-baseweb="input"] input{font-size:.95rem!important;height:34px!important;padding:0!important;line-height:34px!important}
/* remove ALL focus glow */
div[data-baseweb="input"],
div[data-baseweb="input"]:hover,
div[data-baseweb="input"]:focus,
div[data-baseweb="input"]:focus-within,
div[data-baseweb="input"]>div,
div[data-baseweb="input"]>div:focus,
div[data-baseweb="input"]>div:focus-within,
input,input:focus,input:focus-visible,input:active{
  box-shadow:none!important;outline:none!important}
div[data-baseweb="input"]:focus-within{border-color:#6366f1!important}
/* labels */
div[data-testid="stTextInput"] label,
div[data-testid="stSelectbox"] label{font-size:.8rem!important;margin-bottom:2px!important;font-weight:500}
/* ── role field columns: fixed narrow width ── */
.role-fields-row div[data-baseweb="input"],
.role-fields-row div[data-baseweb="input"]>div{max-width:180px!important;width:180px!important}
/* ── experience field: narrow ── */
.exp-field-wrap div[data-baseweb="input"],
.exp-field-wrap div[data-baseweb="input"]>div{max-width:100px!important;width:100px!important}
/* selectbox compact */
div[data-baseweb="select"]>div{min-height:32px!important;padding:0 8px!important;font-size:.85rem!important}
/* ── file uploader compact ── */
div[data-testid="stFileUploader"] section,
div[data-testid="stFileUploader"] section>div{padding:10px 14px!important;min-height:52px!important;border-radius:8px!important;border:1.5px dashed #475569!important}
div[data-testid="stFileUploader"] section span,
div[data-testid="stFileUploader"] section p,
div[data-testid="stFileUploader"] section small,
div[data-testid="stFileUploader"] section *{font-size:.82rem!important}
button[data-testid="stFileUploaderDeleteBtn"]{display:none}
.hero{background:linear-gradient(135deg,#1e1b4b 0%,#312e81 45%,#4f46e5 100%);border-radius:10px;padding:12px 22px;margin-bottom:14px;border:1px solid rgba(129,140,248,.3)}
.hero h1{color:#f8fafc;font-size:1.25rem;font-weight:800;margin:0 0 2px}
.hero p{color:#c7d2fe;margin:0;font-size:.8rem}
.job-card{border:1px solid #334155;border-radius:12px;padding:14px 18px;margin-bottom:8px;background:linear-gradient(180deg,#1e293b 0%,#172033 100%);box-shadow:0 2px 12px rgba(0,0,0,.2)}
.job-card:hover{border-color:#6366f1}
.score-badge{display:inline-block;padding:2px 8px;border-radius:6px;font-weight:600;font-size:.75rem;line-height:1.4}
.score-green{background:#064e3b;color:#6ee7b7}
.score-yellow{background:#78350f;color:#fcd34d}
.score-red{background:#7f1d1d;color:#fca5a5}
.tag{display:inline-block;background:#0f172a;color:#94a3b8;border-radius:6px;padding:2px 7px;font-size:.7rem;margin:1px 2px 1px 0}
.src-badge{display:inline-block;padding:1px 7px;border-radius:5px;font-size:.68rem;font-weight:600;text-transform:uppercase;letter-spacing:.04em}
.src-greenhouse{background:#14532d;color:#86efac}
.src-lever{background:#1e3a5f;color:#93c5fd}
.src-ashby{background:#3b1f5e;color:#d8b4fe}
.src-remotive{background:#1c3337;color:#67e8f9}
.src-linkedin{background:#1e3a5f;color:#7dd3fc}
.src-indeed{background:#1f2937;color:#fbbf24}
.src-jsearch{background:#1f2937;color:#a3a3a3}
.src-adzuna{background:#2d1a00;color:#fb923c}
.src-naukri{background:#1a1a2e;color:#a78bfa}
.src-arbeitnow{background:#1a2e1a;color:#86efac}
.src-jobicy{background:#2e1a2e;color:#e879f9}
.src-themuse{background:#3d1a00;color:#fb923c}
.src-default{background:#1e293b;color:#94a3b8}
.tailor-kw{display:inline-block;background:#1e3a5f;color:#93c5fd;border-radius:5px;padding:2px 9px;font-size:.75rem;margin:2px 3px 2px 0}
.tailor-bullet{background:#1e293b;border-left:3px solid #6366f1;padding:5px 10px;border-radius:0 6px 6px 0;margin:3px 0;font-size:.82rem;color:#cbd5e1}
.page-title{font-size:1.2rem;font-weight:800;color:#f1f5f9;margin-bottom:2px}
.page-sub{font-size:.82rem;color:#64748b;margin-bottom:10px}
.metric-card{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:10px;text-align:center}
.metric-card .val{font-size:1.5rem;font-weight:800;color:#a5b4fc}
.metric-card .lbl{font-size:.68rem;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em}
.done-badge{background:#14532d;color:#86efac;border-radius:999px;padding:3px 10px;font-size:.75rem;font-weight:600}
#MainMenu,footer,header{display:none!important}
/* mobile: add bottom padding so content clears the browser nav bar */
.block-container{padding-bottom:80px!important}
@media(max-width:768px){.block-container{padding-bottom:100px!important}}
section[data-testid="stSidebar"]{background:#0c1222!important;border-right:1px solid #1e293b}
/* compact file uploader drop zone */
div[data-testid="stFileUploader"] section{padding:14px 16px!important;min-height:64px!important;border-radius:10px!important;border:1.5px dashed #475569!important;display:flex!important;align-items:center!important;justify-content:center!important}
div[data-testid="stFileUploader"] section *{font-size:.85rem!important}
div[data-testid="stFileUploaderDropzoneInstructions"]{padding:4px 0!important}
</style>
""",
    unsafe_allow_html=True,
)


# ── helpers ──────────────────────────────────────────────────────────────────

def _badge(score: int, label: str = "") -> str:
    cls = "score-green" if score >= 75 else ("score-yellow" if score >= 50 else "score-red")
    txt = f"{score}%" if not label else f"{label}: {score}%"
    return f'<span class="score-badge {cls}">{txt}</span>'


def _tag(text: str) -> str:
    return f'<span class="tag">{text}</span>'


def _source_badge(platform: str) -> str:
    platform = (platform or "").lower()
    css_map = {
        "greenhouse": "src-greenhouse",
        "lever": "src-lever",
        "ashby": "src-ashby",
        "remotive": "src-remotive",
        "linkedin": "src-linkedin",
        "indeed": "src-indeed",
        "jsearch": "src-jsearch",
        "adzuna": "src-adzuna",
        "naukri": "src-naukri",
        "arbeitnow": "src-arbeitnow",
        "jobicy": "src-jobicy",
        "themuse": "src-themuse",
        "mock": "src-default",
    }
    css = css_map.get(platform, "src-default")
    label_map = {
        "greenhouse": "Greenhouse",
        "lever": "Lever",
        "ashby": "Ashby",
        "remotive": "Remotive",
        "linkedin": "LinkedIn",
        "indeed": "Indeed",
        "jsearch": "Job boards",
        "adzuna": "Adzuna",
        "naukri": "Naukri",
        "arbeitnow": "Arbeitnow",
        "jobicy": "Jobicy",
        "themuse": "The Muse",
        "mock": "Demo",
    }
    label = label_map.get(platform, platform.capitalize())
    return f'<span class="src-badge {css}">{label}</span>'


def _get_pipeline() -> JobHuntPipeline:
    if "pipeline" not in st.session_state:
        st.session_state.pipeline = JobHuntPipeline()
    return st.session_state.pipeline  # type: ignore[return-value]


def _google_key_live() -> bool:
    k = (os.getenv("GOOGLE_API_KEY") or SETTINGS.google_api_key or "").strip()
    if k:
        return True
    if hasattr(st, "secrets"):
        try:
            return bool(str(st.secrets.get("GOOGLE_API_KEY", "")).strip())
        except Exception:
            pass
    return False


def _openai_key_live() -> bool:
    k = (os.getenv("OPENAI_API_KEY") or SETTINGS.openai_api_key or "").strip()
    return bool(k)


def _embeddings_ready() -> bool:
    if SETTINGS.embedding_provider == "google":
        return _google_key_live()
    return _openai_key_live()


def _ai_ready() -> bool:
    """True if ANY LLM key is available (Groq preferred, Google fallback)."""
    # Check Groq keys first — they're used as primary LLM
    groq_key = (os.getenv("GROQ_API_KEY") or SETTINGS.groq_api_key or "").strip()
    if groq_key:
        return True
    if SETTINGS.llm_provider == "google":
        return _google_key_live()
    return _openai_key_live()


def _keys_ready_for_resume() -> bool:
    if SETTINGS.embedding_provider == "local":
        return True
    return _embeddings_ready()


def _keys_ready_for_scoring() -> bool:
    return _ai_ready()


def _fit_to_match(fit: FitScore) -> JobMatchResult:
    return JobMatchResult(
        hiring_chance=fit.score,
        resume_fit=fit.score,
        company_reputation=fit.score,
        work_environment=fit.score,
        compensation_fit=fit.score,
        growth_potential=fit.score,
        flexibility=fit.score,
        summary=fit.summary,
        strengths=fit.strengths,
        gaps=fit.gaps,
        company_highlights=[],
        tailored_cover_letter=fit.tailored_cover_letter,
    )


def _scored_from_state() -> list[ScoredJob]:
    out: list[ScoredJob] = []
    for r in st.session_state.get("scored_jobs", []):
        job = JobPosting.model_validate(r["job"])
        if "match" in r:
            match = JobMatchResult.model_validate(r["match"])
        else:
            match = _fit_to_match(FitScore.model_validate(r["fit"]))
        out.append(ScoredJob(job=job, match=match))
    return out


def _parse_roles_csv(roles_csv: str) -> list[str]:
    return [p.strip() for p in roles_csv.split(",") if p.strip()]


def _roles_to_csv(roles: list[str]) -> str:
    return ", ".join([r.strip() for r in roles if r.strip()])


def _role_fields(prefix: str, defaults: list[str] | None = None) -> list[str]:
    d = defaults or ["", "", ""]
    while len(d) < 3:
        d.append("")
    # Seed session state from defaults only if keys not yet set
    for i, val in enumerate(d[:3], 1):
        key = f"{prefix}_role_{i}"
        if key not in st.session_state and val:
            st.session_state[key] = val
    st.markdown('<div class="role-fields-row">', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        r1 = st.text_input("Role 1", key=f"{prefix}_role_1")
    with c2:
        r2 = st.text_input("Role 2", key=f"{prefix}_role_2")
    with c3:
        r3 = st.text_input("Role 3", key=f"{prefix}_role_3")
    st.markdown('</div>', unsafe_allow_html=True)
    return [r.strip() for r in (r1, r2, r3) if r.strip()]


def _shortlist_store() -> dict[str, dict]:
    return st.session_state.setdefault("shortlisted_jobs", {})


def _shortlisted_from_store() -> list[ScoredJob]:
    out: list[ScoredJob] = []
    for data in _shortlist_store().values():
        job = JobPosting.model_validate(data["job"])
        match = JobMatchResult.model_validate(data["match"])
        out.append(ScoredJob(job=job, match=match))
    return out


def _queue_ids() -> set[str]:
    return st.session_state.setdefault("queue_ids", set())


def _letters() -> dict[str, str]:
    return st.session_state.setdefault("edited_letters", {})


# ── Cloud-aware data helpers ──────────────────────────────────────────────────

def _ensure_shortlist_loaded() -> None:
    """On first run after login, populate in-memory shortlist from Supabase."""
    if not is_supabase_configured():
        return
    uid = _sb_uid()
    if not uid or st.session_state.get("_shortlist_loaded"):
        return
    items = load_shortlist(uid)
    store = _shortlist_store()
    queue = _queue_ids()
    for item in items:
        jid = item["job_data"].get("id", "")
        if jid:
            store[jid] = {"job": item["job_data"], "match": item["match_data"]}
            queue.add(jid)
    st.session_state["_shortlist_loaded"] = True


def _shortlist_add(job: "JobPosting", match: "JobMatchResult") -> None:
    """Add to in-memory shortlist and persist to Supabase if available."""
    store = _shortlist_store()
    queue = _queue_ids()
    store[job.id] = {"job": job.model_dump(), "match": match.model_dump()}
    queue.add(job.id)
    if is_supabase_configured() and (uid := _sb_uid()):
        upsert_shortlist(uid, job.id, job.model_dump(), match.model_dump())


def _shortlist_remove(job_id: str) -> None:
    """Remove from in-memory shortlist and delete from Supabase if available."""
    _shortlist_store().pop(job_id, None)
    _queue_ids().discard(job_id)
    st.session_state.pop(f"sel_{job_id}", None)
    if is_supabase_configured() and (uid := _sb_uid()):
        delete_shortlist_item(uid, job_id)


def _load_applications_all() -> list[ApplicationRecord]:
    """Load applications from Supabase (cloud) or local file (dev)."""
    if is_supabase_configured() and (uid := _sb_uid()):
        rows = load_applications_db(uid)
        return [ApplicationRecord.model_validate(r) for r in rows]
    return load_applications()


def _add_application_cloud(rec: ApplicationRecord) -> list[ApplicationRecord]:
    """Persist a new application to Supabase (cloud) or local file (dev)."""
    if is_supabase_configured() and (uid := _sb_uid()):
        add_application_db(uid, rec.model_dump())
        return _load_applications_all()
    return add_application(rec)


def _update_status_cloud(app_id: str, status: "ApplicationStatus") -> list[ApplicationRecord]:
    if is_supabase_configured() and (uid := _sb_uid()):
        update_application_status_db(uid, app_id, status)
        return _load_applications_all()
    return update_status(app_id, status)


def _check_upload_size(uploaded) -> bool:
    if uploaded is None:
        return True
    # Prefer .size attribute (set by Streamlit, doesn't consume the stream)
    size = getattr(uploaded, "size", None)
    if size is None:
        data = uploaded.getvalue()
        size = len(data)
        # Reset stream position so subsequent .read() works correctly
        try:
            uploaded.seek(0)
        except Exception:
            pass
    if size > SETTINGS.max_upload_bytes:
        mb = SETTINGS.max_upload_bytes // (1024 * 1024)
        st.error(f"File is too large ({size / 1024 / 1024:.1f} MB). Maximum allowed is **{mb} MB**.")
        return False
    return True


def _paginate(items: list, page_key: str) -> list:
    total = len(items)
    if total == 0:
        return []
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = st.session_state.get(page_key, 0)
    page = max(0, min(page, pages - 1))
    st.session_state[page_key] = page
    start = page * PAGE_SIZE
    return items[start : start + PAGE_SIZE]


def _pagination_controls(items: list, page_key: str) -> None:
    """Render prev/next controls — call AFTER rendering the page items."""
    total = len(items)
    if total == 0:
        return
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = st.session_state.get(page_key, 0)
    st.markdown("<div style='margin-top:12px'></div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        if st.button("← Previous", key=f"prev_{page_key}", disabled=page == 0,
                     use_container_width=True):
            st.session_state[page_key] = page - 1
            st.session_state["_paginate_scroll"] = True
            st.rerun()
    with c2:
        st.markdown(
            f"<p style='text-align:center;color:#94a3b8;font-size:.82rem;margin:6px 0'>"
            f"Page <b>{page + 1}</b> of <b>{pages}</b> · {total} openings</p>",
            unsafe_allow_html=True,
        )
    with c3:
        if st.button("Next →", key=f"next_{page_key}", disabled=page >= pages - 1,
                     use_container_width=True):
            st.session_state[page_key] = page + 1
            st.session_state["_paginate_scroll"] = True
            st.rerun()


def _render_job_card(job: JobPosting, match: JobMatchResult, *, show_select: bool) -> None:
    strengths = "".join(_tag(s) for s in match.strengths[:4])
    gaps = "".join(_tag(g) for g in match.gaps[:3])
    highlights = "".join(_tag(h) for h in match.company_highlights[:3])
    # Heuristic jobs have no AI summary; detect by absence of multi-sentence prose
    is_heuristic = "%" in match.summary and len(match.summary) < 80
    rank_badge = (
        '<span style="background:rgba(30,58,95,.8);color:#7dd3fc;border-radius:20px;'
        'padding:2px 9px;font-size:0.67rem;font-weight:700;letter-spacing:.3px">⚡ Quick match</span>'
        if is_heuristic else
        '<span style="background:rgba(20,83,45,.8);color:#86efac;border-radius:20px;'
        'padding:2px 9px;font-size:0.67rem;font-weight:700;letter-spacing:.3px">✦ AI Ranked</span>'
    )
    summary_text = match.summary
    st.markdown(
        f"""
<div class="job-card">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:6px">
    <div style="flex:1;min-width:0">
      <div style="font-size:1.05rem;font-weight:700;color:#f1f5f9;line-height:1.3">{job.title}</div>
      <div style="color:#94a3b8;font-size:0.82rem;margin-top:1px">{job.company or "Company confidential"}</div>
    </div>
    <div style="display:flex;align-items:center;gap:5px;flex-wrap:wrap;justify-content:flex-end">
      {rank_badge}
      {_badge(match.hiring_chance, "Hiring chance")}
      {_badge(match.resume_fit, "Resume")}
    </div>
  </div>
  <div style="margin:7px 0 5px;font-size:0.77rem;color:#64748b;display:flex;flex-wrap:wrap;gap:8px">
    <span>📍 {job.location or "—"}</span>
    <span>{_source_badge(job.platform)}</span>
    <span>💰 {job.salary_text or "Not listed"}</span>
    <span>{_badge(match.company_reputation, "Brand")} {_badge(match.growth_potential, "Growth")} {_badge(match.flexibility, "Flex")}</span>
  </div>
  <div style="font-size:0.82rem;color:#94a3b8;margin-bottom:8px;font-style:italic">{summary_text}</div>
  <div style="display:flex;flex-wrap:wrap;gap:0;margin-bottom:3px">
    <span style="color:#86efac;font-size:0.68rem;font-weight:700;margin-right:5px;align-self:center">✓ STRENGTHS</span>{strengths}
  </div>
  <div style="display:flex;flex-wrap:wrap;gap:0;margin-bottom:3px">
    <span style="color:#fca5a5;font-size:0.68rem;font-weight:700;margin-right:5px;align-self:center">✗ GAPS</span>{gaps}
  </div>
  <div style="display:flex;flex-wrap:wrap;gap:0">
    <span style="color:#a5b4fc;font-size:0.68rem;font-weight:700;margin-right:5px;align-self:center">★ COMPANY</span>{highlights}
  </div>
</div>
""",
        unsafe_allow_html=True,
    )
    if show_select:
        queue = _queue_ids()
        checked = st.checkbox("Shortlist for apply", value=job.id in queue, key=f"sel_{job.id}")
        if checked:
            _shortlist_add(job, match)
        else:
            _shortlist_remove(job.id)
    if job.url and not str(job.url).startswith("https://example.com"):
        st.link_button("View opening ↗", url=job.url, use_container_width=False)


def _score_color(pct: int) -> str:
    if pct >= 75:
        return "#4ade80"   # green
    if pct >= 50:
        return "#facc15"   # yellow
    return "#f87171"       # red


def _render_tailor_result(payload: dict) -> None:
    """Render resume tailoring suggestions from cached dict."""
    from auto_job_hunting_agent.llm.resume_tailor import ResumeTailoringResult
    result = ResumeTailoringResult.model_validate(payload)

    if result.match_verdict:
        st.info(result.match_verdict, icon="🎯")

    col_l, col_r = st.columns(2)
    with col_l:
        if result.keywords_to_add:
            st.markdown("**Keywords to add to your resume**")
            st.caption("Add these to your skills section or summary if you genuinely have these skills:")
            kw_html = "".join(f'<span class="tailor-kw">{kw}</span>' for kw in result.keywords_to_add)
            st.markdown(kw_html, unsafe_allow_html=True)

    with col_r:
        if result.bullets_to_emphasise:
            st.markdown("**Existing strengths to highlight**")
            st.caption("Lead with these points — they match what this JD is looking for:")
            for bullet in result.bullets_to_emphasise:
                st.markdown(
                    f'<div class="tailor-bullet">{bullet}</div>',
                    unsafe_allow_html=True,
                )

    if result.tailored_summary:
        st.markdown("**Tailored professional summary**")
        st.caption("Copy this into the summary section of your resume for this application:")
        st.text_area(
            "Summary (copy-ready)",
            value=result.tailored_summary,
            height=110,
            key=f"tailor_summary_{hash(result.tailored_summary) % 99999}",
        )


def _render_ats(score: ATSResumeScore) -> None:
    is_ai = score.analysis_type != "heuristic"

    # ── Header bar ─────────────────────────────────────────────────────────
    badge_html = (
        '<span style="background:linear-gradient(90deg,#1e3a5f,#1e40af);color:#93c5fd;'
        'border-radius:20px;padding:3px 12px;font-size:.72rem;font-weight:700;'
        'letter-spacing:.4px">✦ AI Analysis</span>'
        if is_ai else
        '<span style="background:#1e293b;color:#94a3b8;'
        'border-radius:20px;padding:3px 12px;font-size:.72rem;font-weight:600">'
        '⚡ Quick estimate</span>'
    )
    st.markdown(badge_html, unsafe_allow_html=True)
    st.markdown("")

    # ── 4 score metric cards ────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    for col, val, lbl, icon in zip(
        (c1, c2, c3, c4),
        (score.overall_pct, score.keyword_match_pct, score.formatting_score_pct, score.experience_clarity_pct),
        ("ATS Pass Rate", "Keyword Match", "Resume Format", "Exp. Clarity"),
        ("🎯", "🔑", "📄", "💼"),
    ):
        color = _score_color(val)
        ring_color = color
        with col:
            st.markdown(
                f'<div class="metric-card" style="text-align:center;padding:14px 8px">'
                f'<div style="font-size:1.6rem;font-weight:800;color:{ring_color};line-height:1">{val}%</div>'
                f'<div style="font-size:.68rem;color:#94a3b8;margin-top:4px;font-weight:500">{icon} {lbl}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    st.markdown("")

    # ── Readiness + hiring outlook ──────────────────────────────────────────
    if score.role_readiness or score.hiring_prospect:
        _rc1, _rc2 = st.columns([1, 2])
        with _rc1:
            if score.role_readiness:
                _rl = score.role_readiness.strip()
                _rl_color = "#4ade80" if "strong" in _rl.lower() or "ready" in _rl.lower() else (
                    "#facc15" if "partial" in _rl.lower() or "moderate" in _rl.lower() else "#f87171"
                )
                st.markdown(
                    f'<div style="background:rgba(30,41,59,.7);border-left:3px solid {_rl_color};'
                    f'border-radius:8px;padding:10px 14px;font-size:.82rem;">'
                    f'<div style="color:#94a3b8;font-size:.68rem;font-weight:600;margin-bottom:3px">READINESS LEVEL</div>'
                    f'<div style="color:{_rl_color};font-weight:700">{_rl}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        with _rc2:
            if score.hiring_prospect:
                st.markdown(
                    f'<div style="background:rgba(30,41,59,.7);border-left:3px solid #6366f1;'
                    f'border-radius:8px;padding:10px 14px;font-size:.82rem;color:#cbd5e1;line-height:1.5">'
                    f'<div style="color:#a5b4fc;font-size:.68rem;font-weight:600;margin-bottom:3px">🎯 HIRING OUTLOOK</div>'
                    f'{score.hiring_prospect}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    elif score.summary:
        st.markdown(
            f'<div style="background:rgba(30,41,59,.7);border-radius:8px;padding:10px 14px;'
            f'font-size:.82rem;color:#94a3b8">{score.summary}</div>',
            unsafe_allow_html=True,
        )

    st.markdown("")

    # ── Two-column: strengths | gaps ────────────────────────────────────────
    left, right = st.columns(2)

    with left:
        if score.present_strengths:
            st.markdown(
                '<div style="font-size:.72rem;font-weight:700;color:#86efac;'
                'letter-spacing:.5px;margin-bottom:6px">✓ WHAT WORKS FOR YOU</div>',
                unsafe_allow_html=True,
            )
            for s in score.present_strengths:
                st.markdown(
                    f'<div style="background:rgba(20,83,45,.25);border-radius:6px;'
                    f'padding:6px 10px;margin-bottom:4px;font-size:.82rem;color:#d1fae5">'
                    f'<span style="color:#4ade80;margin-right:6px">✓</span>{s}</div>',
                    unsafe_allow_html=True,
                )

        if score.matched_keywords:
            st.markdown(
                '<div style="font-size:.72rem;font-weight:700;color:#86efac;'
                'letter-spacing:.5px;margin:10px 0 6px">🔑 KEYWORDS FOUND</div>',
                unsafe_allow_html=True,
            )
            kw_html = "".join(
                f'<span style="background:rgba(20,83,45,.3);color:#86efac;border-radius:12px;'
                f'padding:2px 9px;font-size:.72rem;margin:2px 3px 2px 0;display:inline-block">{kw}</span>'
                for kw in score.matched_keywords[:15]
            )
            st.markdown(kw_html, unsafe_allow_html=True)

    with right:
        if score.critical_missing:
            st.markdown(
                '<div style="font-size:.72rem;font-weight:700;color:#fca5a5;'
                'letter-spacing:.5px;margin-bottom:6px">⚠ CRITICAL GAPS</div>',
                unsafe_allow_html=True,
            )
            for s in score.critical_missing:
                st.markdown(
                    f'<div style="background:rgba(127,29,29,.25);border-radius:6px;'
                    f'padding:6px 10px;margin-bottom:4px;font-size:.82rem;color:#fecaca">'
                    f'<span style="color:#f87171;margin-right:6px">✗</span>{s}</div>',
                    unsafe_allow_html=True,
                )

        if score.missing_keywords:
            st.markdown(
                '<div style="font-size:.72rem;font-weight:700;color:#fca5a5;'
                'letter-spacing:.5px;margin:10px 0 6px">🔍 MISSING KEYWORDS</div>',
                unsafe_allow_html=True,
            )
            kw_html = "".join(
                f'<span style="background:rgba(127,29,29,.3);color:#fca5a5;border-radius:12px;'
                f'padding:2px 9px;font-size:.72rem;margin:2px 3px 2px 0;display:inline-block">{kw}</span>'
                for kw in score.missing_keywords[:15]
            )
            st.markdown(kw_html, unsafe_allow_html=True)

    # ── Weaknesses + action plan ────────────────────────────────────────────
    if score.gaps or score.improvements:
        st.markdown("")
        _gc1, _gc2 = st.columns(2)
        with _gc1:
            if score.gaps:
                st.markdown(
                    '<div style="font-size:.72rem;font-weight:700;color:#fbbf24;'
                    'letter-spacing:.5px;margin-bottom:6px">📋 SPECIFIC WEAKNESSES</div>',
                    unsafe_allow_html=True,
                )
                for i, g in enumerate(score.gaps, 1):
                    st.markdown(
                        f'<div style="padding:5px 0;font-size:.82rem;color:#e2e8f0;'
                        f'border-bottom:1px solid rgba(255,255,255,.06)">'
                        f'<span style="color:#fbbf24;font-weight:700;margin-right:7px">{i}.</span>{g}</div>',
                        unsafe_allow_html=True,
                    )
        with _gc2:
            if score.improvements:
                st.markdown(
                    '<div style="font-size:.72rem;font-weight:700;color:#a5b4fc;'
                    'letter-spacing:.5px;margin-bottom:6px">🚀 HOW TO IMPROVE</div>',
                    unsafe_allow_html=True,
                )
                for i, imp in enumerate(score.improvements, 1):
                    st.markdown(
                        f'<div style="padding:5px 0;font-size:.82rem;color:#e2e8f0;'
                        f'border-bottom:1px solid rgba(255,255,255,.06)">'
                        f'<span style="color:#818cf8;font-weight:700;margin-right:7px">→</span>{imp}</div>',
                        unsafe_allow_html=True,
                    )


# ── sidebar (minimal) ────────────────────────────────────────────────────────

# ── Load per-user data from Supabase on first render after login ──────────────
_ensure_shortlist_loaded()

# ── Auto-restore resume from Supabase if pipeline is empty after login ────────
_pipeline_obj = _get_pipeline()
if is_supabase_configured() and (uid := _sb_uid()):
    if not _pipeline_obj.resume_store.is_ready and not st.session_state.get("_resume_restore_tried"):
        st.session_state["_resume_restore_tried"] = True
        _meta = load_resume_meta(uid)
        if _meta and _meta.get("raw_text"):
            try:
                _pipeline_obj.resume_store.ingest_text(_meta["raw_text"])
            except Exception:
                pass

pipeline = _pipeline_obj
applications = _load_applications_all()

with st.sidebar:
    st.markdown("### Job Hunt Pro")
    st.caption("Smart applications · HITL")
    st.divider()
    if pipeline.resume_store.is_ready:
        st.markdown("📄 Resume on file")
    else:
        st.markdown("📄 No resume yet")
    n_apps = len(applications)
    if n_apps:
        st.markdown(f"📋 {n_apps} application(s) tracked")
    st.divider()

    if is_supabase_configured() and (user := _sb_user()):
        st.caption(f"Signed in as **{user.email}**")
        if st.button("Sign out", use_container_width=True):
            sign_out()
            for k in ["sb_user", "sb_token", "_shortlist_loaded", "_resume_restore_tried",
                      "shortlisted_jobs", "queue_ids", "scored_jobs", "resume_years"]:
                st.session_state.pop(k, None)
            st.rerun()
    else:
        st.caption("Local mode — data stays on this device")

# ── page-level scroll-to-top: inject button into parent DOM ──────────────────
import streamlit.components.v1 as _components  # noqa: E402
_components.html("""<script>
(function(){
  if(window.parent.document.getElementById('jhp-top-btn'))return;
  var b=window.parent.document.createElement('button');
  b.id='jhp-top-btn';
  b.innerHTML='&#9650;';
  b.title='Back to top';
  b.style.cssText='position:fixed;bottom:26px;right:26px;z-index:99999;'
    +'background:#4f46e5;color:#fff;border:none;border-radius:50%;'
    +'width:38px;height:38px;font-size:1.1rem;cursor:pointer;'
    +'box-shadow:0 2px 10px rgba(0,0,0,.55);line-height:38px;text-align:center;'
    +'font-family:sans-serif;';
  b.onmouseenter=function(){b.style.background='#6366f1'};
  b.onmouseleave=function(){b.style.background='#4f46e5'};
  b.onclick=function(){
    /* Streamlit scrolls inside a specific div, not window */
    var el=window.parent.document.querySelector('section.main')
      ||window.parent.document.querySelector('[data-testid="stMain"]')
      ||window.parent.document.querySelector('.main')
      ||window.parent.document.documentElement;
    el.scrollTo({top:0,behavior:'smooth'});
    window.parent.scrollTo({top:0,behavior:'smooth'});
  };
  window.parent.document.body.appendChild(b);
})();
</script>""", height=0)

# ── hero ─────────────────────────────────────────────────────────────────────

st.markdown(
    """
<div class="hero">
  <h1>Job Hunt Pro</h1>
  <p>ATS scoring · ranked openings · cover letters · application tracker</p>
</div>
""",
    unsafe_allow_html=True,
)

# ── User badge (top-right, injected as fixed overlay) ─────────────────────────
if is_supabase_configured() and (user := _sb_user()):
    _email_short = (user.email or "").split("@")[0][:16]
    _initial = _email_short[0].upper() if _email_short else "U"
    st.markdown(
        f"""
<style>
#jhp-user-badge{{
  position:fixed;top:14px;right:18px;z-index:99998;
  display:flex;align-items:center;gap:8px;
  background:rgba(30,41,59,.92);backdrop-filter:blur(8px);
  border:1px solid rgba(99,102,241,.35);border-radius:40px;
  padding:5px 14px 5px 6px;box-shadow:0 2px 16px rgba(0,0,0,.4);
}}
#jhp-user-avatar{{
  width:28px;height:28px;border-radius:50%;
  background:linear-gradient(135deg,#6366f1,#8b5cf6);
  display:flex;align-items:center;justify-content:center;
  font-size:.82rem;font-weight:700;color:#fff;flex-shrink:0;
}}
#jhp-user-name{{font-size:.78rem;color:#e2e8f0;font-weight:500;max-width:130px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
</style>
<div id="jhp-user-badge">
  <div id="jhp-user-avatar">{_initial}</div>
  <span id="jhp-user-name">{_email_short}</span>
</div>
""",
        unsafe_allow_html=True,
    )
    # Compact logout tucked into the top-right corner beneath the badge
    _lc = st.columns([8, 1])[1]
    with _lc:
        if st.button("⏏ Out", key="top_signout", help=f"Sign out ({user.email})"):
            sign_out()
            for k in ["sb_user", "sb_token", "_shortlist_loaded", "_resume_restore_tried",
                      "shortlisted_jobs", "queue_ids", "scored_jobs", "resume_years"]:
                st.session_state.pop(k, None)
            st.rerun()

tab_resume, tab_search, tab_review, tab_apply, tab_tracker = st.tabs([
    "Resume & ATS",
    "Discover roles",
    "Shortlist",
    "Apply",
    "My applications",
])

# Scroll to job list anchor when pagination button was clicked
if st.session_state.pop("_paginate_scroll", False):
    import time as _time_mod
    _components.html(f"""<script>
(function(){{
  // unique: {_time_mod.time_ns()} — prevents Streamlit caching this component
  function doScroll() {{
    var anchor = window.parent.document.getElementById('jhp-jobs-top');
    if(anchor){{
      anchor.scrollIntoView({{behavior:'smooth', block:'start'}});
    }} else {{
      var el = window.parent.document.querySelector('[data-testid="stMain"]')
        || window.parent.document.querySelector('section.main')
        || window.parent.document.documentElement;
      el.scrollTo({{top:0, behavior:'smooth'}});
    }}
  }}
  // Delay to let Streamlit finish rendering the new page before scrolling
  setTimeout(doScroll, 150);
}})();
</script>""", height=0)

# ══════════════════════════════════════════════════════
# TAB 1 — Resume & ATS
# ══════════════════════════════════════════════════════

with tab_resume:
    st.markdown('<div class="page-title">Resume & ATS screening</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="page-sub">Upload your resume (PDF or TXT, max 2 MB) and target roles. Optionally run ATS screening before searching.</div>',
        unsafe_allow_html=True,
    )

    roles_list_resume = _role_fields("resume")
    st.markdown('<div class="exp-field-wrap">', unsafe_allow_html=True)
    _exp_c1, _exp_c2 = st.columns([1, 3])
    with _exp_c1:
        _years_raw = st.text_input(
            "Years of experience",
            placeholder="e.g. 2",
            key="resume_years",
        )
    st.markdown('</div>', unsafe_allow_html=True)
    try:
        years_exp = float(_years_raw) if _years_raw.strip() else 0.0
    except ValueError:
        years_exp = 0.0

    run_ats = st.checkbox(
        "Run ATS screening now",
        value=False,
        help="You can continue without this and run screening later.",
    )

    upload = st.file_uploader(
        "Resume file",
        type=["pdf", "txt"],
        help=f"Maximum file size: {SETTINGS.max_upload_bytes // (1024 * 1024)} MB",
    )

    go = st.button(
        "Upload resume",
        type="primary",
        disabled=upload is None or not roles_list_resume,
    )

    if go and upload:
        if not _check_upload_size(upload):
            st.stop()
        if run_ats and not _ai_ready():
            st.error("ATS service is currently unavailable. Upload without ATS and continue.")
            st.stop()
        st.session_state["target_roles"] = _roles_to_csv(roles_list_resume)
        st.session_state["years_experience"] = years_exp
        for i, role in enumerate(roles_list_resume, 1):
            st.session_state[f"search_role_{i}"] = role
        for i in range(len(roles_list_resume) + 1, 4):
            st.session_state[f"search_role_{i}"] = ""

        # ── Scroll DOWN toward progress area ──────────────────────────────
        _components.html("""<script>
(function(){
  setTimeout(function(){
    var el=window.parent.document.querySelector('section.main')
      ||window.parent.document.querySelector('[data-testid="stMain"]')
      ||window.parent.document.documentElement;
    el.scrollBy({top:300,behavior:'smooth'});
  },150);
})();
</script>""", height=0)

        # ── Animated step-by-step progress ────────────────────────────────
        _prog_box = st.empty()

        def _show_step(steps: list[tuple[str, str]]) -> None:
            """steps: list of (icon, label) where status is 'done'|'active'|'pending'"""
            rows = ""
            for icon, label, status in steps:
                if status == "done":
                    color, bg = "#86efac", "#14532d"
                elif status == "active":
                    color, bg = "#fde68a", "#1c1a00"
                else:
                    color, bg = "#94a3b8", "#1e293b"
                rows += (
                    f'<div style="display:flex;align-items:center;gap:10px;padding:8px 14px;'
                    f'background:{bg};border-radius:8px;margin:4px 0">'
                    f'<span style="font-size:1.1rem">{icon}</span>'
                    f'<span style="color:{color};font-size:.88rem;font-weight:500">{label}</span>'
                    f'</div>'
                )
            _prog_box.markdown(
                f'<div style="background:#0f172a;border:1px solid #334155;border-radius:12px;'
                f'padding:14px 16px;margin:10px 0">'
                f'<div style="color:#94a3b8;font-size:.75rem;font-weight:600;'
                f'text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px">'
                f'Processing</div>{rows}</div>',
                unsafe_allow_html=True,
            )

        import time as _time

        n_ats = len(roles_list_resume[:3]) if run_ats else 0
        base_steps = [("📄", "Reading & indexing resume", "active")]
        if run_ats:
            for r in roles_list_resume[:3]:
                base_steps.append(("🔍", f"ATS analysis: {r}", "pending"))
        _show_step([(i, l, s) for i, l, s in base_steps])

        try:
            upload.seek(0)
            file_bytes = upload.read()
            upload.seek(0)
            pipeline.resume_store.ingest_upload(upload, upload.name)
            done = [("📄", "Resume indexed", "done")]
            if run_ats:
                for r in roles_list_resume[:3]:
                    done.append(("🔍", f"ATS analysis: {r}", "pending"))
            _show_step(done)

            if run_ats:
                ats_map: dict[str, dict] = {}
                for idx, role in enumerate(roles_list_resume[:3]):
                    if idx > 0:
                        _time.sleep(5)  # give Groq's per-minute window time to recover
                    steps_now = [("📄", "Resume indexed", "done")]
                    for j, r in enumerate(roles_list_resume[:3]):
                        if j < idx:
                            steps_now.append(("🔍", f"ATS analysis: {r}", "done"))
                        elif j == idx:
                            steps_now.append(("🔍", f"ATS analysis: {r}", "active"))
                        else:
                            steps_now.append(("🔍", f"ATS analysis: {r}", "pending"))
                    _show_step(steps_now)
                    ats = pipeline.score_resume_for_role(role, years_exp)
                    ats_map[role] = ats.model_dump()

                # All done
                all_done = [("📄", "Resume indexed", "done")]
                for r in roles_list_resume[:3]:
                    all_done.append(("✅", f"ATS complete: {r}", "done"))
                _show_step(all_done)
                st.session_state["ats_scores"] = ats_map
            else:
                st.session_state.pop("ats_scores", None)

            # ── Persist resume to Supabase (cloud mode) ───────────────────
            if is_supabase_configured() and (uid := _sb_uid()):
                roles_csv = ",".join(roles_list_resume)
                save_resume_meta(
                    uid,
                    pipeline.resume_store.raw_resume,
                    roles_csv,
                    years_exp,
                    ats_results=st.session_state.get("ats_scores"),
                )
                upload_resume_file(uid, file_bytes, upload.name)

            _time.sleep(0.6)
            _prog_box.empty()
            if run_ats:
                st.success(f"**{upload.name}** ready — ATS report generated for {len(ats_map)} role(s).")
            else:
                st.success(f"**{upload.name}** uploaded. Use **Run ATS screening** to score your resume.")
            st.rerun()
        except Exception as exc:
            _prog_box.empty()
            from auto_job_hunting_agent.error_handling import friendly
            st.error(friendly(exc))

    if pipeline.resume_store.is_ready:
        if "ats_scores" in st.session_state:
            ats_roles = list(st.session_state["ats_scores"].keys())
            current_roles = roles_list_resume
            # Show re-run button if roles have changed since last ATS run
            if set(current_roles) != set(ats_roles) and current_roles:
                st.info(
                    f"You changed the target roles. Click **Re-run ATS** to update scores "
                    f"for: {', '.join(current_roles)}",
                    icon="🔄",
                )
                if st.button("Re-run ATS", type="secondary") and _ai_ready():
                    with st.spinner("Running ATS analysis for all roles…"):
                        try:
                            ats_map: dict[str, dict] = {}
                            for role in current_roles:
                                ats = pipeline.score_resume_for_role(role, years_exp)
                                ats_map[role] = ats.model_dump()
                            st.session_state["ats_scores"] = ats_map
                            st.session_state["target_roles"] = _roles_to_csv(current_roles)
                            st.rerun()
                        except Exception as exc:
                            from auto_job_hunting_agent.error_handling import friendly
                            st.error(friendly(exc))

            st.divider()
            n_roles = len(st.session_state["ats_scores"])
            st.markdown(f"### ATS screening by role  ·  {n_roles} role(s) analysed")
            for role, payload in st.session_state["ats_scores"].items():
                with st.expander(f"**{role}**", expanded=True):
                    _render_ats(ATSResumeScore.model_validate(payload))

    if pipeline.resume_store.is_ready:
        st.divider()
        if st.button("Continue to Discover roles →", type="primary", key="continue_to_discover"):
            st.session_state["_goto_discover"] = True
            st.rerun()

# Inject tab-switch JS when user clicks "Continue"
_goto = st.session_state.pop("_goto_discover", False)
if _goto:
    _components.html(
        f"""<script>
(function(){{
  // Works on both desktop (iframe) and mobile (direct window)
  function getDoc() {{
    try {{ return window.parent.document; }} catch(e) {{ return window.document; }}
  }}
  function switchTab() {{
    var doc = getDoc();
    var tabs = doc.querySelectorAll('button[role=tab]');
    if (tabs && tabs.length > 1) {{ tabs[1].click(); return true; }}
    return false;
  }}
  // Retry up to 5 times with increasing delays to handle slow mobile renders
  var attempts = 0;
  function trySwitch() {{
    if (switchTab() || attempts++ >= 5) return;
    setTimeout(trySwitch, 150 * attempts);
  }}
  setTimeout(trySwitch, 100);
}})();
</script>""",
        height=0,
    )


# ══════════════════════════════════════════════════════
# TAB 2 — Discover
# ══════════════════════════════════════════════════════

with tab_search:
    st.markdown('<div class="page-title">Discover & rank openings</div>', unsafe_allow_html=True)

    # ── Mirror roles and experience directly from resume tab widget keys ──────
    # This is the most reliable source — Streamlit keeps widget keys in sync live.
    for _i in range(1, 4):
        _src = st.session_state.get(f"resume_role_{_i}", "")
        if _src:
            st.session_state[f"search_role_{_i}"] = _src
    _yrs_src = st.session_state.get("resume_years", "")
    if _yrs_src:
        st.session_state["discover_years"] = _yrs_src

    _saved_roles = [
        st.session_state.get("search_role_1", ""),
        st.session_state.get("search_role_2", ""),
        st.session_state.get("search_role_3", ""),
    ]
    _saved_roles = [r for r in _saved_roles if r.strip()]

    # ── Compact role summary + collapsible edit ───────────────────────────────
    _r1 = st.session_state.get("search_role_1", "")
    _r2 = st.session_state.get("search_role_2", "")
    _r3 = st.session_state.get("search_role_3", "")
    _dy = st.session_state.get("discover_years", "")
    _role_tags = " · ".join(r for r in [_r1, _r2, _r3] if r)
    _yrs_tag   = f"{_dy} yrs" if _dy else ""
    _summary   = " | ".join(x for x in [_role_tags, _yrs_tag] if x) or "No roles set — enter below"

    st.markdown(
        f'<div style="font-size:.82rem;color:#94a3b8;margin-bottom:6px">🔍 {_summary}</div>',
        unsafe_allow_html=True,
    )

    with st.expander("Edit search criteria", expanded=True):
        role_list = _role_fields("search", defaults=_saved_roles)

        rc1, rc2, rc3, rc4 = st.columns([2, 2, 2, 1])
        with rc1:
            work_mode = st.selectbox("Work arrangement", WORK_MODES, index=0)
        with rc2:
            location = st.selectbox("Location", LOCATIONS, index=0)
        with rc3:
            _yrs_raw2 = st.text_input("Years of experience", placeholder="e.g. 2", key="discover_years")
            try:
                years_exp = float(_yrs_raw2) if _yrs_raw2.strip() else 0.0
            except ValueError:
                years_exp = 0.0
        with rc4:
            deep_rank = st.select_slider(
                "Analysis depth",
                options=[0, 1, 2, 3, 5, 8],
                value=min(3, SETTINGS.max_llm_rankings),
                help="0 = instant. Higher = richer AI insights for top roles.",
            )

        use_careers = True
        use_remotive = True

    # always read role_list from session state (force-synced from tab 1 above)
    role_list = [r for r in [
        st.session_state.get("search_role_1", ""),
        st.session_state.get("search_role_2", ""),
        st.session_state.get("search_role_3", ""),
    ] if r.strip()]

    no_roles = len(role_list) == 0
    search_btn = st.button(
        "Search & rank companies",
        type="primary",
        disabled=no_roles,
        key="search_btn",
    )

    if search_btn:
        if not pipeline.resume_store.is_ready:
            st.error("Upload your resume on the **Resume & ATS** tab first.")
            st.stop()
        if deep_rank > 0 and not _ai_ready():
            st.error(
                "Detailed analysis service is unavailable. Set analysis depth to 0 and try again."
            )
            st.stop()

        # Temporarily apply UI toggles to env so pipeline picks them up
        os.environ["ENABLE_COMPANY_CAREERS"] = "true" if use_careers else "false"
        os.environ["ENABLE_REMOTIVE"] = "true" if use_remotive else "false"
        # Rebuild settings so pipeline sees updated values this run
        from auto_job_hunting_agent import config as _cfg
        _cfg.SETTINGS = _cfg._build_settings()  # type: ignore[attr-defined]

        roles_csv = _roles_to_csv(role_list)
        st.session_state["target_roles"] = roles_csv
        st.session_state["years_experience"] = years_exp
        st.session_state["search_page"] = 0

        pbar = st.progress(0.0)
        status = st.empty()

        def _prog(msg: str, pct: float) -> None:
            pbar.progress(min(pct, 1.0))
            status.caption(msg)

        with st.spinner("Searching and ranking…"):
            try:
                results = pipeline.search_and_score(
                    roles_csv,
                    work_mode,
                    location,
                    years_exp,
                    progress=_prog,
                    max_llm_rankings=deep_rank,
                )
            except Exception as exc:
                from auto_job_hunting_agent.error_handling import friendly

                pbar.empty()
                status.empty()
                st.error(friendly(exc))
                st.stop()

        pbar.progress(1.0)
        status.empty()
        st.session_state["scored_jobs"] = [
            {"job": r.job.model_dump(), "match": r.match.model_dump()} for r in results
        ]
        st.session_state["search_meta"] = {
            "roles": roles_csv,
            "work_mode": work_mode,
            "location": location,
            "years": years_exp,
        }
        st.success(f"Ranked **{len(results)}** openings — best hiring chance first.")

    scored = _scored_from_state()
    if scored:
        # ── source breakdown ───────────────────────────────────────────────
        from collections import Counter
        src_counts = Counter(r.job.platform for r in scored)
        src_parts = []
        src_label_map = {
            "greenhouse": "Greenhouse", "lever": "Lever", "ashby": "Ashby",
            "remotive": "Remotive", "linkedin": "LinkedIn", "indeed": "Indeed",
            "jsearch": "Job boards", "adzuna": "Adzuna", "naukri": "Naukri",
            "arbeitnow": "Arbeitnow", "jobicy": "Jobicy", "themuse": "The Muse", "mock": "Demo",
        }
        for src, count in sorted(src_counts.items(), key=lambda x: -x[1]):
            label = src_label_map.get(src, src.capitalize())
            src_parts.append(f"{label} ({count})")
        if src_parts:
            st.caption("Sources: " + " · ".join(src_parts))

    scored = _scored_from_state()
    if scored:
        meta = st.session_state.get("search_meta", {})
        st.caption(
            f"Search: **{meta.get('roles', '—')}** · {meta.get('work_mode', '')} · "
            f"{meta.get('location', '')} · {meta.get('years', '')} yrs exp"
        )
        st.divider()
        page_items = _paginate(scored, "search_page")
        st.markdown('<div id="jhp-jobs-top"></div>', unsafe_allow_html=True)
        for r in page_items:
            _render_job_card(r.job, r.match, show_select=True)
            with st.expander("Full description"):
                st.write(r.job.description[:1500] or "No description available.")
            st.markdown("---")
        _pagination_controls(scored, "search_page")


# ══════════════════════════════════════════════════════
# TAB 3 — Shortlist
# ══════════════════════════════════════════════════════

with tab_review:
    st.markdown('<div class="page-title">Your shortlist</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="page-sub">Roles you marked for apply — sorted by hiring chance.</div>',
        unsafe_allow_html=True,
    )

    shortlisted = _shortlisted_from_store()

    if not shortlisted:
        st.info("No roles shortlisted yet. Use **Discover roles** and check *Shortlist for apply*.", icon="⭐")
    else:
        shortlisted.sort(key=lambda x: x.match.hiring_chance, reverse=True)
        st.caption(f"**{len(shortlisted)}** selected")
        page_items = _paginate(shortlisted, "shortlist_page")
        st.markdown('<div id="jhp-jobs-top"></div>', unsafe_allow_html=True)
        for r in page_items:
            _render_job_card(r.job, r.match, show_select=False)
            b1, b2 = st.columns([1, 4])
            with b1:
                if st.button("Remove", key=f"remove_short_{r.job.id}"):
                    _shortlist_remove(r.job.id)
                    st.rerun()

            # ── Tailor for this job ────────────────────────────────────────
            with st.expander("Tailor resume for this role", expanded=False):
                tailor_key = f"tailor_{r.job.id}"
                tailor_cache = st.session_state.get(tailor_key)
                if tailor_cache:
                    _render_tailor_result(tailor_cache)
                else:
                    if not pipeline.resume_store.is_ready:
                        st.caption("Upload your resume to use this feature.")
                    elif not _ai_ready():
                        st.caption("Add your API key in the sidebar to enable AI tailoring.")
                    else:
                        if st.button("Generate tailoring suggestions", key=f"tailorbtn_{r.job.id}", type="secondary"):
                            with st.spinner("Analysing role and resume…"):
                                try:
                                    from auto_job_hunting_agent.llm.resume_tailor import tailor_resume_for_job
                                    result = tailor_resume_for_job(
                                        resume_sections=pipeline.get_resume_key_sections(),
                                        job_title=r.job.title,
                                        company=r.job.company or "",
                                        job_description=r.job.description,
                                    )
                                    st.session_state[tailor_key] = result.model_dump()
                                    st.rerun()
                                except Exception as exc:
                                    from auto_job_hunting_agent.error_handling import friendly
                                    st.error(friendly(exc))

            st.markdown("---")
        _pagination_controls(shortlisted, "shortlist_page")


# ══════════════════════════════════════════════════════
# TAB 4 — Apply
# ══════════════════════════════════════════════════════

with tab_apply:
    st.markdown('<div class="page-title">Apply with cover letter</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="page-sub">Review personalised letters, open the job page, then confirm to track the application.</div>',
        unsafe_allow_html=True,
    )

    shortlisted = _shortlisted_from_store()
    letters = _letters()
    queue_items = sorted(shortlisted, key=lambda x: x.match.hiring_chance, reverse=True)
    applied_ids = {a.job_id for a in applications}

    if not queue_items:
        st.info("Shortlist roles first, then return here to apply.", icon="✅")
    else:
        pending = [r for r in queue_items if r.job.id not in applied_ids]
        st.caption(f"**{len(pending)}** pending · **{len(queue_items) - len(pending)}** already tracked")

        # ── Search filter ──────────────────────────────────────────────────
        _apply_search = st.text_input(
            "Search by company or role",
            placeholder="e.g. Google, Software Engineer…",
            key="_apply_search",
            label_visibility="collapsed",
        )
        if _apply_search.strip():
            _q = _apply_search.strip().lower()
            pending = [r for r in pending if _q in (r.job.company or "").lower() or _q in r.job.title.lower()]

        for r in pending:
            job, match = r.job, r.match
            lkey = f"letter_{job.id}"
            if lkey not in letters:
                letters[lkey] = match.tailored_cover_letter

            with st.expander(
                f"{job.title} @ {job.company or 'Unknown'} — {match.hiring_chance}% hiring chance",
                expanded=True,
            ):
                edited = st.text_area(
                    "Cover letter",
                    value=letters[lkey],
                    height=240,
                    key=f"ta_{job.id}",
                )
                letters[lkey] = edited
                b1, b2, b3 = st.columns(3)
                with b1:
                    if job.url and not str(job.url).startswith("https://example.com"):
                        st.link_button("Open job & apply ↗", url=job.url, type="primary")
                with b2:
                    safe = (job.title or "role").replace(" ", "_")[:40]
                    st.download_button(
                        "Download letter",
                        data=edited.encode(),
                        file_name=f"cover_{safe}.txt",
                        mime="text/plain",
                        key=f"dl_{job.id}",
                    )
                with b3:
                    if st.button("Confirm application", key=f"apply_{job.id}", type="primary"):
                        rec = ApplicationRecord.new(
                            job_id=job.id,
                            company=job.company or "Unknown",
                            role=job.title,
                            platform=job.platform,
                            job_url=job.url,
                            cover_letter=edited,
                        )
                        _add_application_cloud(rec)
                        st.success("Application recorded — see **My applications** tab.")
                        st.rerun()


# ══════════════════════════════════════════════════════
# TAB 5 — Tracker
# ══════════════════════════════════════════════════════

with tab_tracker:
    st.markdown('<div class="page-title">Application tracker</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="page-sub">Every role you confirmed — update status as you hear back.</div>',
        unsafe_allow_html=True,
    )

    apps = _load_applications_all()
    if not apps:
        st.info("No applications yet. Confirm applies on the **Apply** tab.", icon="📋")
    else:
        # ── Filters ───────────────────────────────────────────────────────
        _fc1, _fc2, _fc3 = st.columns([3, 2, 2])
        with _fc1:
            _trk_search = st.text_input(
                "Search company / role",
                placeholder="e.g. Microsoft, QA…",
                key="_trk_search",
                label_visibility="collapsed",
            )
        with _fc2:
            _trk_status = st.selectbox(
                "Filter by status",
                ["All statuses"] + list(STATUS_OPTIONS),
                key="_trk_status",
                label_visibility="collapsed",
            )
        with _fc3:
            _trk_sort = st.selectbox(
                "Sort by",
                ["Newest first", "Oldest first"],
                key="_trk_sort",
                label_visibility="collapsed",
            )

        filtered_apps = list(apps)
        if _trk_search.strip():
            _q = _trk_search.strip().lower()
            filtered_apps = [a for a in filtered_apps if _q in (a.company or "").lower() or _q in (a.role or "").lower()]
        if _trk_status != "All statuses":
            filtered_apps = [a for a in filtered_apps if a.status == _trk_status]
        if _trk_sort == "Oldest first":
            filtered_apps = list(reversed(filtered_apps))

        st.caption(f"Showing **{len(filtered_apps)}** of **{len(apps)}** application(s)")
        st.divider()

        for app in filtered_apps:
            c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
            with c1:
                st.markdown(f"**{app.role}**")
                st.caption(f"{app.company} · {app.platform}")
            with c2:
                st.caption(f"Applied: **{app.applied_at}**")
            with c3:
                new_status = st.selectbox(
                    "Status",
                    STATUS_OPTIONS,
                    index=STATUS_OPTIONS.index(app.status) if app.status in STATUS_OPTIONS else 0,
                    key=f"st_{app.id}",
                    label_visibility="collapsed",
                )
                if new_status != app.status:
                    _update_status_cloud(app.id, new_status)
                    st.rerun()
            with c4:
                if app.job_url:
                    st.link_button("Opening ↗", url=app.job_url)
            with st.expander("Cover letter & notes"):
                st.text(app.cover_letter[:2000] if app.cover_letter else "—")
            st.divider()
