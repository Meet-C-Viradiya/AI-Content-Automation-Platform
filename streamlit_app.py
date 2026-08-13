"""
Self-contained Streamlit app for deployment.
Combines dashboard + database + workflow in one process.
No separate FastAPI server needed.
"""

import os
import time
import threading
from datetime import datetime, timezone

import streamlit as st
from fpdf import FPDF

# ──────────────────────────────────────────────
# Database setup (inline, no API needed)
# ──────────────────────────────────────────────
from sqlalchemy import create_engine, Column, DateTime, Integer, Text, String, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

import tempfile
DB_PATH = os.path.join(tempfile.gettempdir(), "automation.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Job(Base):
    __tablename__ = "jobs"
    id = Column(Integer, primary_key=True, index=True)
    topic = Column(String(500), nullable=False)
    status = Column(String(50), default="pending", nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)
    logs = relationship("AutomationLog", back_populates="job", cascade="all, delete-orphan")
    content = relationship("GeneratedContent", back_populates="job", cascade="all, delete-orphan", uselist=False)


class AutomationLog(Base):
    __tablename__ = "automation_logs"
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    step = Column(String(100), nullable=False)
    status = Column(String(50), nullable=False)
    message = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    job = relationship("Job", back_populates="logs")


class GeneratedContent(Base):
    __tablename__ = "generated_content"
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False, unique=True)
    title = Column(String(500), nullable=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    job = relationship("Job", back_populates="content")



Base.metadata.create_all(bind=engine)


# ──────────────────────────────────────────────
# Workflow runner (background thread)
# ──────────────────────────────────────────────
def _log_step(db, job_id, step, status, message=None):
    db.add(AutomationLog(job_id=job_id, step=step, status=status, message=message))
    db.commit()


def run_job_background(job_id, topic):
    from app.workflow.graph import workflow

    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return

        job.status = "processing"
        db.commit()
        _log_step(db, job_id, "job_started", "completed", f"Topic: {topic}")

        initial_state = {
            "job_id": job_id,
            "topic": topic,
            "as_of": datetime.now(timezone.utc).date().isoformat(),
            "status": "pending",
            "current_step": "starting",
            "evidence": [],
            "sections": [],
        }

        final_state = dict(initial_state)

        for update in workflow.stream(initial_state, stream_mode="updates"):
            for node_name, partial in update.items():
                for key, value in partial.items():
                    if key == "sections":
                        final_state["sections"] = final_state.get("sections", []) + value
                    else:
                        final_state[key] = value

                if node_name == "worker":
                    section = partial.get("sections", [{}])[0]
                    message = f"Generated section {section.get('task_id')}"
                elif node_name == "research":
                    evidence_count = len(partial.get("evidence", []))
                    message = partial.get("error") or f"Found {evidence_count} evidence item(s)"
                else:
                    message = partial.get("error") or f"{node_name} finished"

                _log_step(
                    db, job_id, step=node_name,
                    status="warning" if partial.get("error") else "completed",
                    message=message,
                )

        if final_state.get("status") != "completed" or not final_state.get("final_content"):
            job.status = "failed"
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
            _log_step(db, job_id, "job_failed", "failed",
                      final_state.get("error", "No content was generated."))
            return

        plan = final_state.get("plan")
        db.add(GeneratedContent(
            job_id=job_id,
            title=plan.blog_title if plan else topic,
            content=final_state["final_content"],
        ))

        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        _log_step(db, job_id, "job_completed", "completed", "Final content saved.")

    except Exception as e:
        db.rollback()
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = "failed"
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
        _log_step(db, job_id, "job_failed", "failed", str(e))
    finally:
        db.close()


# ──────────────────────────────────────────────
# Database helper functions
# ──────────────────────────────────────────────
def create_job(topic):
    db = SessionLocal()
    try:
        job = Job(topic=topic, status="pending")
        db.add(job)
        db.commit()
        db.refresh(job)
        job_id = job.id
        threading.Thread(target=run_job_background, args=(job_id, topic), daemon=True).start()
        return {"job_id": job_id, "topic": topic, "status": "pending"}
    finally:
        db.close()


def fetch_jobs(limit=20):
    db = SessionLocal()
    try:
        jobs = db.query(Job).order_by(Job.id.desc()).limit(limit).all()
        return [
            {
                "job_id": j.id, "topic": j.topic, "status": j.status,
                "created_at": j.created_at.isoformat() if j.created_at else None,
                "completed_at": j.completed_at.isoformat() if j.completed_at else None,
            }
            for j in jobs
        ]
    finally:
        db.close()


def fetch_job_detail(job_id):
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return None

        logs = db.query(AutomationLog).filter(
            AutomationLog.job_id == job_id
        ).order_by(AutomationLog.id.asc()).all()

        content = db.query(GeneratedContent).filter(
            GeneratedContent.job_id == job_id
        ).first()

        return {
            "job_id": job.id, "topic": job.topic, "status": job.status,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "logs": [
                {"step": l.step, "status": l.status, "message": l.message,
                 "timestamp": l.timestamp.isoformat() if l.timestamp else None}
                for l in logs
            ],
            "content": {"title": content.title, "content": content.content} if content else None,
        }
    finally:
        db.close()


def delete_job(job_id):
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            db.delete(job)
            db.commit()
    finally:
        db.close()


# ──────────────────────────────────────────────
# PDF Generation
# ──────────────────────────────────────────────
def generate_pdf(title, content):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    replacements = {
        "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
        "\u2013": "-", "\u2014": "-", "\u2026": "...", "\u2022": "-", "\u00a0": " ",
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
# Streamlit UI
# ──────────────────────────────────────────────
st.set_page_config(page_title="AI Content Automation Platform", page_icon="🤖", layout="wide")

st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem; border-radius: 16px; margin-bottom: 2rem;
        text-align: center; color: white;
    }
    .main-header h1 { color: white !important; font-size: 2.5rem; margin-bottom: 0.5rem; }
    .main-header p { color: rgba(255,255,255,0.9); font-size: 1.1rem; }
    .stat-card {
        background: white; border: 1px solid #e2e8f0; border-radius: 12px;
        padding: 1.5rem; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    .stat-number { font-size: 2.5rem; font-weight: 700; margin: 0; }
    .stat-label { color: #64748b; font-size: 0.9rem; margin: 0; }
    .status-completed { background: #dcfce7; color: #166534; padding: 4px 12px; border-radius: 20px; font-size: 0.85rem; font-weight: 600; }
    .status-processing { background: #fef3c7; color: #92400e; padding: 4px 12px; border-radius: 20px; font-size: 0.85rem; font-weight: 600; }
    .status-pending { background: #e0e7ff; color: #3730a3; padding: 4px 12px; border-radius: 20px; font-size: 0.85rem; font-weight: 600; }
    .status-failed { background: #fecaca; color: #991b1b; padding: 4px 12px; border-radius: 20px; font-size: 0.85rem; font-weight: 600; }
    .progress-step { text-align: center; padding: 0.5rem; }
    .progress-step .icon { font-size: 1.8rem; }
    .progress-step .label { font-size: 0.75rem; color: #475569; margin-top: 4px; }
    .content-box { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 2rem; margin-top: 1rem; }
    .create-section { background: #f0f9ff; border: 2px dashed #93c5fd; border-radius: 16px; padding: 2rem; margin-bottom: 2rem; }
    div[data-testid="stForm"] { border: none !important; padding: 0 !important; }
</style>
""", unsafe_allow_html=True)

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

# Header
st.markdown("""
<div class="main-header">
    <h1>🤖 AI Content Automation Platform</h1>
    <p>Enter any topic and let AI research, plan, and generate professional content automatically</p>
</div>
""", unsafe_allow_html=True)

# Stats Bar
all_jobs = fetch_jobs(limit=100)
total = len(all_jobs)
completed = sum(1 for j in all_jobs if j["status"] == "completed")
processing = sum(1 for j in all_jobs if j["status"] in ("pending", "processing"))
failed = sum(1 for j in all_jobs if j["status"] == "failed")

stat_cols = st.columns(4)
for col, (num, color, label) in zip(stat_cols, [
    (total, "#3b82f6", "📊 Total Jobs"),
    (completed, "#22c55e", "✅ Completed"),
    (processing, "#f59e0b", "⏳ In Progress"),
    (failed, "#ef4444", "❌ Failed"),
]):
    col.markdown(f"""
    <div class="stat-card">
        <p class="stat-number" style="color: {color};">{num}</p>
        <p class="stat-label">{label}</p>
    </div>
    """, unsafe_allow_html=True)

st.markdown("")

# Create New Job
st.markdown('<div class="create-section">', unsafe_allow_html=True)
st.markdown("### 🚀 Create New Automation Job")
st.markdown("Enter a topic below and our AI will automatically research, plan, and generate a complete article.")

with st.form("create_job_form", clear_on_submit=True):
    topic = st.text_input(
        "Topic",
        placeholder="e.g. AI Automation for Small Businesses, Digital Marketing Trends 2026...",
        label_visibility="collapsed",
    )
    submitted = st.form_submit_button("🤖 Start AI Automation", use_container_width=True)

    if submitted:
        if not topic.strip():
            st.warning("Please enter a topic to get started.")
        else:
            result = create_job(topic.strip())
            job_id = result["job_id"]
            st.success(f"✅ Job #{job_id} created successfully!")
            st.info(f"✍️ Generating content for: **{topic}** — please wait...")
            st.session_state["selected_job"] = job_id
            st.session_state["auto_refresh"] = True

st.markdown('</div>', unsafe_allow_html=True)

# Auto-refresh
if st.session_state.get("auto_refresh") and st.session_state.get("selected_job"):
    detail = fetch_job_detail(st.session_state["selected_job"])
    if detail and detail["status"] in ("pending", "processing"):
        time.sleep(2)
        st.rerun()
    else:
        st.session_state["auto_refresh"] = False

# Recent Jobs
st.markdown("---")
header_cols = st.columns([6, 1])
header_cols[0].markdown("### 📋 Recent Jobs")
if header_cols[1].button("🔄 Refresh", use_container_width=True):
    st.rerun()

jobs = fetch_jobs()
if not jobs:
    st.info("No jobs yet. Create your first automation job above! 👆")
else:
    for job in jobs:
        cols = st.columns([1, 5, 2, 3, 1, 1])
        cols[0].markdown(f"**#{job['job_id']}**")
        cols[1].markdown(f"**{job['topic']}**")
        cols[2].markdown(STATUS_HTML.get(job["status"], job["status"]), unsafe_allow_html=True)
        created = (job.get("created_at") or "")[:19].replace("T", " ")
        cols[3].markdown(f"🕐 {created}")

        if cols[4].button("👁️", key=f"view_{job['job_id']}", help="View details"):
            st.session_state["selected_job"] = job["job_id"]
            st.session_state["auto_refresh"] = False
            st.rerun()

        if cols[5].button("🗑️", key=f"del_{job['job_id']}", help="Delete job"):
            delete_job(job["job_id"])
            if st.session_state.get("selected_job") == job["job_id"]:
                st.session_state.pop("selected_job", None)
            st.rerun()

        st.markdown("<hr style='margin:0; border:none; border-top:1px solid #f1f5f9;'>", unsafe_allow_html=True)

# Job Detail
selected_job_id = st.session_state.get("selected_job")
if selected_job_id:
    st.markdown("---")
    detail = fetch_job_detail(selected_job_id)

    if detail:
        st.markdown(f"### 📄 Job #{selected_job_id} — {detail['topic']}")

        info_cols = st.columns(3)
        info_cols[0].markdown(STATUS_HTML.get(detail["status"], detail["status"]), unsafe_allow_html=True)

        logs = detail.get("logs", [])
        provider_fallback = any("unavailable" in (l.get("message") or "").lower() for l in logs)
        info_cols[1].markdown("**AI Provider:** " + ("⚠️ Fallback" if provider_fallback else "✅ Gemini AI"))

        evidence_log = next((l for l in logs if l["step"] == "research"), None)
        if evidence_log:
            info_cols[2].markdown(f"**Research:** {evidence_log['message']}")

        if detail["status"] in ("pending", "processing"):
            last_step = logs[-1]["step"] if logs else "pending"
            st.info(PROGRESS_MESSAGES.get(last_step, "Working on it..."))

        st.markdown("#### Workflow Progress")
        completed_steps = {l["step"] for l in logs}
        warning_steps = {l["step"] for l in logs if l["status"] == "warning"}

        progress_cols = st.columns(len(STEP_ORDER))
        for col, (step_key, label, emoji) in zip(progress_cols, STEP_ORDER):
            if step_key in completed_steps:
                icon = "⚠️" if step_key in warning_steps else "✅"
            else:
                icon = "⬜"
            col.markdown(
                f'<div class="progress-step"><div class="icon">{icon}</div><div class="label">{label}</div></div>',
                unsafe_allow_html=True,
            )

        with st.expander("📜 Full Workflow Log"):
            for log in logs:
                ts = (log.get("timestamp") or "")[:19].replace("T", " ")
                si = "✅" if log["status"] == "completed" else "⚠️" if log["status"] == "warning" else "❌"
                st.text(f"  {si} [{ts}] {log['step']}: {log['message']}")

        content_data = detail.get("content")
        if content_data:
            st.markdown("#### 📝 Generated Content")
            st.markdown(f'<div class="content-box">', unsafe_allow_html=True)
            st.markdown(f"## {content_data['title']}")
            st.markdown(content_data["content"])
            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown("")
            export_cols = st.columns([1, 1, 4])
            md_content = f"# {content_data['title']}\n\n{content_data['content']}"
            export_cols[0].download_button(
                label="📥 Download Markdown", data=md_content,
                file_name=f"{content_data['title'][:50].replace(' ', '_')}.md",
                mime="text/markdown", use_container_width=True,
            )
            try:
                pdf_bytes = generate_pdf(content_data["title"], content_data["content"])
                export_cols[1].download_button(
                    label="📄 Download PDF", data=pdf_bytes,
                    file_name=f"{content_data['title'][:50].replace(' ', '_')}.pdf",
                    mime="application/pdf", use_container_width=True,
                )
            except Exception:
                export_cols[1].warning("PDF generation unavailable")

        elif detail["status"] == "completed":
            st.warning("Content was generated but could not be loaded.")
        else:
            st.info("⏳ Content is being generated... The page will refresh automatically.")

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #94a3b8; padding: 1rem;">
    <p>🤖 AI Content Automation Platform — Powered by LangGraph, Gemini AI & Tavily</p>
    <p style="font-size: 0.8rem;">Built with FastAPI • Streamlit • SQLite • LangChain</p>
</div>
""", unsafe_allow_html=True)