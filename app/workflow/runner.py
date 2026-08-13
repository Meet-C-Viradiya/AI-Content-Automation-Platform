from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.database.models import Job, AutomationLog, GeneratedContent
from app.workflow.graph import workflow


def _log_step(
    db: Session,
    job_id: int,
    step: str,
    status: str,
    message: str | None = None,
) -> None:
    db.add(
        AutomationLog(
            job_id=job_id,
            step=step,
            status=status,
            message=message,
        )
    )
    db.commit()


def run_automation_job(job_id: int, topic: str) -> None:
    """
    Executed by FastAPI's BackgroundTasks after POST /api/jobs returns.

    Runs in a separate context from the request, so it opens its own
    DB session rather than reusing the request-scoped one (which is
    already closed by the time this runs).

    Uses workflow.stream(..., stream_mode="updates") instead of
    workflow.invoke() so each node's completion - including each
    parallel worker - can be written to automation_logs as it
    happens, giving the dashboard real progress instead of only a
    final result. The graph still only runs once; no extra LLM calls.
    """

    db = SessionLocal()

    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if job is None:
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

        # Manually accumulated mirror of the graph's final state.
        # "sections" is the one field the graph reduces with
        # operator.add (parallel workers each contribute one item),
        # so it's extended rather than overwritten; every other key
        # is last-write-wins, matching LangGraph's default behavior.
        final_state: dict = dict(initial_state)

        for update in workflow.stream(initial_state, stream_mode="updates"):
            for node_name, partial in update.items():

                for key, value in partial.items():
                    if key == "sections":
                        final_state["sections"] = (
                            final_state.get("sections", []) + value
                        )
                    else:
                        final_state[key] = value

                if node_name == "worker":
                    section = partial.get("sections", [{}])[0]
                    message = f"Generated section {section.get('task_id')}"
                elif node_name == "research":
                    evidence_count = len(partial.get("evidence", []))
                    message = (
                        partial.get("error")
                        or f"Found {evidence_count} evidence item(s)"
                    )
                else:
                    message = partial.get("error") or f"{node_name} finished"

                _log_step(
                    db,
                    job_id,
                    step=node_name,
                    status="warning" if partial.get("error") else "completed",
                    message=message,
                )

        if final_state.get("status") != "completed" or not final_state.get(
            "final_content"
        ):
            job.status = "failed"
            job.completed_at = datetime.now(timezone.utc)
            db.commit()

            _log_step(
                db,
                job_id,
                "job_failed",
                "failed",
                final_state.get("error", "No content was generated."),
            )
            return

        plan = final_state.get("plan")

        db.add(
            GeneratedContent(
                job_id=job_id,
                title=plan.blog_title if plan else topic,
                content=final_state["final_content"],
            )
        )

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