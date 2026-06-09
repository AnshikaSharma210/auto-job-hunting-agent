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

PAGE_SIZE = 5
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
.page-title{font-size:1.2rem;font-weight:800;color:#f1f5f9;margin-bottom:2px}
.page-sub{font-size:.82rem;color:#64748b;margin-bottom:10px}
.metric-card{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:10px;text-align:center}
.metric-card .val{font-size:1.5rem;font-weight:800;color:#a5b4fc}
.metric-card .lbl{font-size:.68rem;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em}
.done-badge{background:#14532d;color:#86efac;border-radius:999px;padding:3px 10px;font-size:.75rem;font-weight:600}
#MainMenu,footer,header{visibility:hidden}
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
    c1, c2, c3 = st.columns([1, 2, 1])
    with c1:
        if st.button("← Previous", key=f"prev_{page_key}", disabled=page == 0):
            st.session_state[page_key] = page - 1
            st.rerun()
    with c2:
        st.markdown(
            f"<p style='text-align:center;color:#94a3b8;font-size:.82rem;margin:6px 0'>"
            f"Page <b>{page + 1}</b> of <b>{pages}</b> · {total} openings</p>",
            unsafe_allow_html=True,
        )
    with c3:
        if st.button("Next →", key=f"next_{page_key}", disabled=page >= pages - 1):
            st.session_state[page_key] = page + 1
            st.rerun()


def _render_job_card(job: JobPosting, match: JobMatchResult, *, show_select: bool) -> None:
    strengths = "".join(_tag(s) for s in match.strengths[:4])
    gaps = "".join(_tag(g) for g in match.gaps[:3])
    highlights = "".join(_tag(h) for h in match.company_highlights[:3])
    st.markdown(
        f"""
<div class="job-card">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:6px">
    <div>
      <div style="font-size:1rem;font-weight:700;color:#f1f5f9">{job.title}</div>
      <div style="color:#94a3b8;font-size:0.82rem">{job.company or "Company confidential"}</div>
    </div>
    <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap">
      {_badge(match.hiring_chance, "Hiring chance")}
      {_badge(match.resume_fit, "Resume")} {_badge(match.company_reputation, "Brand")}
      {_badge(match.growth_potential, "Growth")} {_badge(match.flexibility, "Flex")}
    </div>
  </div>
  <div style="margin:6px 0 4px;font-size:0.78rem;color:#64748b">
    📍 {job.location or "—"} &nbsp;·&nbsp; 🏷 {job.platform} &nbsp;·&nbsp; 💰 {job.salary_text or "Not listed"}
  </div>
  <div style="font-size:0.82rem;color:#cbd5e1;margin-bottom:8px">{match.summary}</div>
  <div><span style="color:#86efac;font-size:0.7rem;font-weight:700">STRENGTHS</span> {strengths}</div>
  <div><span style="color:#fca5a5;font-size:0.7rem;font-weight:700">GAPS</span> {gaps}</div>
  <div><span style="color:#a5b4fc;font-size:0.72rem;font-weight:700">COMPANY</span> {highlights}</div>
</div>
""",
        unsafe_allow_html=True,
    )
    if show_select:
        queue = _queue_ids()
        shortlist = _shortlist_store()
        checked = st.checkbox("Shortlist for apply", value=job.id in queue, key=f"sel_{job.id}")
        if checked:
            queue.add(job.id)
            shortlist[job.id] = {"job": job.model_dump(), "match": match.model_dump()}
        else:
            queue.discard(job.id)
            shortlist.pop(job.id, None)
    if job.url and not str(job.url).startswith("https://example.com"):
        st.link_button("View opening ↗", url=job.url, use_container_width=False)


def _score_color(pct: int) -> str:
    if pct >= 75:
        return "#4ade80"   # green
    if pct >= 50:
        return "#facc15"   # yellow
    return "#f87171"       # red


def _render_ats(score: ATSResumeScore) -> None:
    # ── top metric row ──
    c1, c2, c3, c4 = st.columns(4)
    for col, val, lbl in zip(
        (c1, c2, c3, c4),
        (score.overall_pct, score.keyword_match_pct, score.formatting_score_pct, score.experience_clarity_pct),
        ("ATS Pass Rate", "Keyword Match", "Resume Format", "Experience Clarity"),
    ):
        color = _score_color(val)
        with col:
            st.markdown(
                f'<div class="metric-card">'
                f'<div class="val" style="color:{color}">{val}%</div>'
                f'<div class="lbl">{lbl}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    # ── role readiness badge + hiring outlook ──
    if score.role_readiness:
        st.markdown(f"**Readiness level:** `{score.role_readiness}`")
    if score.hiring_prospect:
        st.info(score.hiring_prospect, icon="🎯")
    elif score.summary:
        st.markdown(f"**Assessment:** {score.summary}")

    st.markdown("")

    left, right = st.columns(2)

    with left:
        if score.present_strengths:
            st.markdown("**What works in your favour**")
            for s in score.present_strengths:
                st.markdown(f"✅ {s}")

        if score.matched_keywords:
            st.markdown("**Keywords found**")
            st.caption(", ".join(score.matched_keywords[:15]))

    with right:
        if score.critical_missing:
            st.markdown("**Critical gaps (deal-breakers)**")
            for s in score.critical_missing:
                st.markdown(f"🚫 {s}")

        if score.missing_keywords:
            st.markdown("**Missing keywords**")
            st.caption(", ".join(score.missing_keywords[:15]))

    if score.gaps:
        st.markdown("**Specific weaknesses**")
        for g in score.gaps:
            st.markdown(f"- {g}")

    if score.improvements:
        st.markdown("**How to improve your chances**")
        for imp in score.improvements:
            st.markdown(f"- {imp}")


# ── sidebar (minimal) ────────────────────────────────────────────────────────

pipeline = _get_pipeline()
applications = load_applications()

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

    # ── BYOK: user supplies their own API key ─────────────────────────────
    st.markdown("#### API key")
    st.caption(
        "Paste your free Google Gemini key. "
        "Get one in seconds at [aistudio.google.com](https://aistudio.google.com/app/apikey)."
    )
    _user_key = st.text_input(
        "Google API key",
        type="password",
        value=st.session_state.get("_user_google_key", ""),
        placeholder="AIza…",
        key="_user_google_key_input",
        label_visibility="collapsed",
    )
    if _user_key and _user_key.strip():
        # Override env so LLM/embedding helpers pick it up this session
        os.environ["GOOGLE_API_KEY"] = _user_key.strip()
        st.session_state["_user_google_key"] = _user_key.strip()
        st.caption("✅ Key active for this session")
    elif os.getenv("GOOGLE_API_KEY"):
        st.caption("✅ Using key from server config")
    else:
        st.caption("⚠️ Enter a key to enable AI features")

    st.divider()
    st.caption("Your key is used only in your browser session and is never stored.")

# ── page-level scroll-to-top: inject button into parent DOM ──────────────────
import streamlit.components.v1 as _components  # noqa: E402
_components.html("""<script>
(function(){
  if(window.parent.document.getElementById('jhp-top-btn'))return;
  var b=window.parent.document.createElement('button');
  b.id='jhp-top-btn';
  b.innerHTML='&#8679;';
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

tab_resume, tab_search, tab_review, tab_apply, tab_tracker = st.tabs([
    "Resume & ATS",
    "Discover roles",
    "Shortlist",
    "Apply",
    "My applications",
])

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
        # Seed discover tab role fields so they are pre-filled
        for i, role in enumerate(roles_list_resume, 1):
            st.session_state[f"search_role_{i}"] = role
        for i in range(len(roles_list_resume) + 1, 4):
            st.session_state[f"search_role_{i}"] = ""
        primary_role = (roles_list_resume[0] if roles_list_resume else "Software Engineer")
        with st.spinner("Indexing resume…" + (" + ATS" if run_ats else "")):
            try:
                import time as _time
                pipeline.resume_store.ingest_upload(upload, upload.name)
                if run_ats:
                    ats_map: dict[str, dict] = {}
                    for idx, role in enumerate(roles_list_resume[:3]):
                        if idx > 0:
                            _time.sleep(5)  # avoid RPM quota between roles
                        ats = pipeline.score_resume_for_role(role, years_exp)
                        ats_map[role] = ats.model_dump()
                    st.session_state["ats_scores"] = ats_map
                    st.success(f"**{upload.name}** ready — ATS generated for {len(ats_map)} role(s).")
                else:
                    st.session_state.pop("ats_scores", None)
                    st.success(f"**{upload.name}** uploaded successfully.")
                st.rerun()
            except Exception as exc:
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
        """<script>
(function(){
  var tabs=window.parent.document.querySelectorAll('button[role=tab]');
  if(tabs&&tabs[1]){tabs[1].click();}
})();
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
        meta = st.session_state.get("search_meta", {})
        st.caption(
            f"Search: **{meta.get('roles', '—')}** · {meta.get('work_mode', '')} · "
            f"{meta.get('location', '')} · {meta.get('years', '')} yrs exp"
        )
        st.divider()
        page_items = _paginate(scored, "search_page")
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
        for r in page_items:
            _render_job_card(r.job, r.match, show_select=False)
            b1, b2 = st.columns([1, 4])
            with b1:
                if st.button("Remove", key=f"remove_short_{r.job.id}"):
                    _shortlist_store().pop(r.job.id, None)
                    _queue_ids().discard(r.job.id)
                    st.rerun()
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
                        add_application(rec)
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

    apps = applications
    if not apps:
        st.info("No applications yet. Confirm applies on the **Apply** tab.", icon="📋")
    else:
        for app in apps:
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
                    update_status(app.id, new_status)
                    st.rerun()
            with c4:
                if app.job_url:
                    st.link_button("Opening ↗", url=app.job_url)
            with st.expander("Cover letter & notes"):
                st.text(app.cover_letter[:2000] if app.cover_letter else "—")
            st.divider()
