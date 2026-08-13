import os
import time
import requests
import streamlit as st
from fpdf import FPDF
import tempfile

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000/api")

st.set_page_config(
    page_title="AI Content Automation Platform",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ──────────────────────────────────────────────
# Custom CSS
# ──────────────────────────────────────────────
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 16px;
        margin-bottom: 2rem;
        text-align: center;
        color: white;
    }
    .main-header h1 {
        color: white !important;
        font-size: 2.5rem;
        margin-bottom: 0.5rem;
    }
    .main-header p {
        color: rgba(255,255,255,0.9);
        font-size: 1.1rem;
    }
    .stat-card {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 1.5rem;
        text-align: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    .stat-number {
        font-size: 2.5rem;
        font-weight: 700;
        margin: 0;
    }
    .stat-label {
        color: #64748b;
        font-size: 0.9rem;
        margin: 0;
    }
    .job-card {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 1.2rem 1.5rem;
        margin-bottom: 0.8rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        transition: box-shadow 0.2s;
    }
    .job-card:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    .status-completed {
        background: #dcfce7;
        color: #166534;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
    }
    .status-processing {
        background: #fef3c7;
        color: #92400e;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
    }
    .status-pending {
        background: #e0e7ff;
        color: #3730a3;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
    }
    .status-failed {
        background: #fecaca;
        color: #991b1b;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
    }
    .progress-step {
        text-align: center;
        padding: 0.5rem;
    }
    .progress-step .icon {
        font-size: 1.8rem;
    }
    .progress-step .label {
        font-size: 0.75rem;
        color: #475569;
        margin-top: 4px;
    }
    .content-box {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 2rem;
        margin-top: 1rem;
    }
    .create-section {
        background: #f0f9ff;
        border: 2px dashed #93c5fd;
        border-radius: 16px;
        padding: 2rem;
        margin-bottom: 2rem;
    }
    div[data-testid="stForm"] {
        border: none !important;
        padding: 0 !important;
    }
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────
# Progress Messages
# ──────────────────────────────────────────────
PROGRESS_MESSAGES = {
    "pending": "🕒 Job queued — preparing automation pipeline...",
    "job_started": "🚀 Automation started — initializing AI workflow...",
    "router": "🧠 AI Router is analyzing your topic...",
    "research": "🌐 Searching the web for latest information...",
    "orchestrator": "📋 Creating structured content plan...",
    "worker": "✍️ AI workers are writing content sections...",
    "reducer": "🔗 Combining all sections into final article...",
    "job_completed": "✅ Content is ready! Your article has been generated.",
    "job_failed": "❌ Something went wrong. Please try again.",
}

STEP_ORDER = [
    ("job_started", "Job Created", "🎯"),
    ("router", "AI Router", "🧠"),
    ("research", "Web Research", "🌐"),
    ("orchestrator", "Content Planning", "📋"),
    ("worker", "Content Generation", "✍️"),
    ("reducer", "Content Reduction", "🔗"),
    ("job_completed", "Final Content", "✅"),
]

STATUS_HTML = {
    "completed": '<span class="status-completed">✅ Completed</span>',
    "processing": '<span class="status-processing">⏳ Processing</span>',
    "pending": '<span class="status-pending">🕒 Pending</span>',
    "failed": '<span class="status-failed">❌ Failed</span>',
}


# ──────────────────────────────────────────────
# API Functions
# ──────────────────────────────────────────────
def create_job(topic: str) -> dict:
    resp = requests.post(f"{API_BASE_URL}/jobs", json={"topic": topic}, timeout=10)
    resp.raise_for_status()
    return resp.json()


def fetch_jobs(limit: int = 20) -> list:
    resp = requests.get(f"{API_BASE_URL}/jobs", params={"limit": limit}, timeout=10)
    resp.raise_for_status()
    return resp.json()


def fetch_job_detail(job_id: int) -> dict:
    resp = requests.get(f"{API_BASE_URL}/jobs/{job_id}", timeout=10)
    resp.raise_for_status()
    return resp.json()


def delete_job(job_id: int) -> dict:
    resp = requests.delete(f"{API_BASE_URL}/jobs/{job_id}", timeout=10)
    resp.raise_for_status()
    return resp.json()


def generate_pdf(title: str, content: str) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Clean special characters that Helvetica can't render
    replacements = {
        "\u2018": "'", "\u2019": "'",
        "\u201c": '"', "\u201d": '"',
        "\u2013": "-", "\u2014": "-",
        "\u2026": "...", "\u2022": "-",
        "\u00a0": " ",
    }
    for old, new in replacements.items():
        title = title.replace(old, new)
        content = content.replace(old, new)

    content = content.encode("latin-1", errors="replace").decode("latin-1")
    title = title.encode("latin-1", errors="replace").decode("latin-1")

    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 15, title, new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(5)

    pdf.set_font("Helvetica", "", 11)

    for line in content.split("\n"):
        line = line.strip()

        if line.startswith("## "):
            pdf.ln(5)
            pdf.set_font("Helvetica", "B", 15)
            pdf.cell(0, 10, line[3:], new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 11)

        elif line.startswith("### "):
            pdf.ln(3)
            pdf.set_font("Helvetica", "B", 13)
            pdf.cell(0, 8, line[4:], new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 11)

        elif line.startswith("- "):
            pdf.cell(10, 7, "")
            pdf.cell(0, 7, f"  {line}", new_x="LMARGIN", new_y="NEXT")

        elif line == "":
            pdf.ln(3)

        else:
            pdf.multi_cell(0, 7, line)

    return pdf.output()


# ──────────────────────────────────────────────
# Header
# ──────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <h1>🤖 AI Content Automation Platform</h1>
    <p>Enter any topic and let AI research, plan, and generate professional content automatically</p>
</div>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────
# Stats Bar
# ──────────────────────────────────────────────
try:
    all_jobs = fetch_jobs(limit=100)
except requests.RequestException:
    all_jobs = []

total = len(all_jobs)
completed = sum(1 for j in all_jobs if j["status"] == "completed")
processing = sum(1 for j in all_jobs if j["status"] in ("pending", "processing"))
failed = sum(1 for j in all_jobs if j["status"] == "failed")

stat_cols = st.columns(4)

with stat_cols[0]:
    st.markdown(f"""
    <div class="stat-card">
        <p class="stat-number" style="color: #3b82f6;">{total}</p>
        <p class="stat-label">📊 Total Jobs</p>
    </div>
    """, unsafe_allow_html=True)

with stat_cols[1]:
    st.markdown(f"""
    <div class="stat-card">
        <p class="stat-number" style="color: #22c55e;">{completed}</p>
        <p class="stat-label">✅ Completed</p>
    </div>
    """, unsafe_allow_html=True)

with stat_cols[2]:
    st.markdown(f"""
    <div class="stat-card">
        <p class="stat-number" style="color: #f59e0b;">{processing}</p>
        <p class="stat-label">⏳ In Progress</p>
    </div>
    """, unsafe_allow_html=True)

with stat_cols[3]:
    st.markdown(f"""
    <div class="stat-card">
        <p class="stat-number" style="color: #ef4444;">{failed}</p>
        <p class="stat-label">❌ Failed</p>
    </div>
    """, unsafe_allow_html=True)

st.markdown("")


# ──────────────────────────────────────────────
# Create New Job
# ──────────────────────────────────────────────
st.markdown('<div class="create-section">', unsafe_allow_html=True)
st.markdown("### 🚀 Create New Automation Job")
st.markdown("Enter a topic below and our AI will automatically research, plan, and generate a complete article.")

with st.form("create_job_form", clear_on_submit=True):
    topic = st.text_input(
        "Topic",
        placeholder="e.g. AI Automation for Small Businesses, Digital Marketing Trends 2026...",
        label_visibility="collapsed",
    )

    submitted = st.form_submit_button(
        "🤖 Start AI Automation",
        use_container_width=True,
    )

    if submitted:
        if not topic.strip():
            st.warning("Please enter a topic to get started.")
        else:
            try:
                result = create_job(topic.strip())
                job_id = result["job_id"]
                st.success(f"✅ Job #{job_id} created successfully!")
                st.info(f"✍️ Generating content for: **{topic}** — please wait...")
                st.session_state["selected_job"] = job_id
                st.session_state["auto_refresh"] = True
            except requests.RequestException as e:
                st.error(f"Could not reach the API: {e}")

st.markdown('</div>', unsafe_allow_html=True)


# ──────────────────────────────────────────────
# Auto-refresh logic
# ──────────────────────────────────────────────
if st.session_state.get("auto_refresh") and st.session_state.get("selected_job"):
    try:
        check = fetch_job_detail(st.session_state["selected_job"])
        if check["status"] in ("pending", "processing"):
            time.sleep(2)
            st.rerun()
        else:
            st.session_state["auto_refresh"] = False
    except requests.RequestException:
        st.session_state["auto_refresh"] = False


# ──────────────────────────────────────────────
# Recent Jobs
# ──────────────────────────────────────────────
st.markdown("---")
header_cols = st.columns([6, 1])
header_cols[0].markdown("### 📋 Recent Jobs")
if header_cols[1].button("🔄 Refresh", use_container_width=True):
    st.rerun()

try:
    jobs = fetch_jobs()
except requests.RequestException as e:
    jobs = []
    st.error(f"Could not reach the API: {e}")

if not jobs:
    st.info("No jobs yet. Create your first automation job above! 👆")
else:
    for job in jobs:
        with st.container():
            cols = st.columns([1, 5, 2, 3, 1, 1])

            cols[0].markdown(f"**#{job['job_id']}**")
            cols[1].markdown(f"**{job['topic']}**")
            cols[2].markdown(
                STATUS_HTML.get(job["status"], job["status"]),
                unsafe_allow_html=True,
            )
            created = (job.get("created_at") or "")[:19].replace("T", " ")
            cols[3].markdown(f"🕐 {created}")

            if cols[4].button("👁️", key=f"view_{job['job_id']}", help="View details"):
                st.session_state["selected_job"] = job["job_id"]
                st.session_state["auto_refresh"] = False
                st.rerun()

            if cols[5].button("🗑️", key=f"del_{job['job_id']}", help="Delete job"):
                try:
                    delete_job(job["job_id"])
                    if st.session_state.get("selected_job") == job["job_id"]:
                        st.session_state.pop("selected_job", None)
                    st.rerun()
                except requests.RequestException as e:
                    st.error(f"Delete failed: {e}")

            st.markdown("<hr style='margin:0; border:none; border-top:1px solid #f1f5f9;'>", unsafe_allow_html=True)


# ──────────────────────────────────────────────
# Job Detail
# ──────────────────────────────────────────────
selected_job_id = st.session_state.get("selected_job")

if selected_job_id:
    st.markdown("---")

    try:
        detail = fetch_job_detail(selected_job_id)
    except requests.RequestException as e:
        detail = None
        st.error(f"Could not load job details: {e}")

    if detail:
        st.markdown(f"### 📄 Job #{selected_job_id} — {detail['topic']}")

        info_cols = st.columns(3)
        info_cols[0].markdown(
            STATUS_HTML.get(detail["status"], detail["status"]),
            unsafe_allow_html=True,
        )

        logs = detail.get("logs", [])
        provider_fallback = any(
            "unavailable" in (log.get("message") or "").lower() for log in logs
        )
        info_cols[1].markdown(
            "**AI Provider:** "
            + ("⚠️ Fallback" if provider_fallback else "✅ Gemini AI")
        )

        evidence_log = next((l for l in logs if l["step"] == "research"), None)
        if evidence_log:
            info_cols[2].markdown(f"**Research:** {evidence_log['message']}")

        # Live progress message
        if detail["status"] in ("pending", "processing"):
            last_step = logs[-1]["step"] if logs else "pending"
            progress_msg = PROGRESS_MESSAGES.get(last_step, "Working on it...")
            st.info(progress_msg)

        # Workflow progress bar
        st.markdown("#### Workflow Progress")

        completed_steps = {log["step"] for log in logs}
        warning_steps = {log["step"] for log in logs if log["status"] == "warning"}

        progress_cols = st.columns(len(STEP_ORDER))
        for col, (step_key, label, emoji) in zip(progress_cols, STEP_ORDER):
            if step_key in completed_steps:
                if step_key in warning_steps:
                    icon = "⚠️"
                else:
                    icon = "✅"
            elif detail["status"] in ("pending", "processing"):
                # Check if this is the "next" step
                icon = "⬜"
            else:
                icon = "⬜"

            col.markdown(
                f'<div class="progress-step">'
                f'<div class="icon">{icon}</div>'
                f'<div class="label">{label}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        # Full log
        with st.expander("📜 Full Workflow Log"):
            for log in logs:
                timestamp = (log.get("timestamp") or "")[:19].replace("T", " ")
                step = log["step"]
                status_icon = "✅" if log["status"] == "completed" else "⚠️" if log["status"] == "warning" else "❌"
                st.text(f"  {status_icon} [{timestamp}] {step}: {log['message']}")

        # Generated content
        content_data = detail.get("content")
        if content_data:
            st.markdown("#### 📝 Generated Content")

            st.markdown(f'<div class="content-box">', unsafe_allow_html=True)
            st.markdown(f"## {content_data['title']}")
            st.markdown(content_data["content"])
            st.markdown('</div>', unsafe_allow_html=True)

            # Export buttons
            st.markdown("")
            export_cols = st.columns([1, 1, 4])

            md_content = f"# {content_data['title']}\n\n{content_data['content']}"
            export_cols[0].download_button(
                label="📥 Download Markdown",
                data=md_content,
                file_name=f"{content_data['title'][:50].replace(' ', '_')}.md",
                mime="text/markdown",
                use_container_width=True,
            )

            try:
                pdf_bytes = generate_pdf(content_data["title"], content_data["content"])
                export_cols[1].download_button(
                    label="📄 Download PDF",
                    data=pdf_bytes,
                    file_name=f"{content_data['title'][:50].replace(' ', '_')}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            except Exception:
                export_cols[1].warning("PDF generation unavailable")

        elif detail["status"] == "completed":
            st.warning("Content was generated but could not be loaded.")
        else:
            st.info("⏳ Content is being generated... The page will refresh automatically.")


# ──────────────────────────────────────────────
# Footer
# ──────────────────────────────────────────────
st.markdown("---")
st.markdown(
    """
    <div style="text-align: center; color: #94a3b8; padding: 1rem;">
        <p>🤖 AI Content Automation Platform — Powered by LangGraph, Gemini AI & Tavily</p>
        <p style="font-size: 0.8rem;">Built with FastAPI • Streamlit • SQLite • LangChain</p>
    </div>
    """,
    unsafe_allow_html=True,
)