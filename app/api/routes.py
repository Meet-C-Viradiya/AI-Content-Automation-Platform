from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models import AutomationLog, GeneratedContent, Job
from app.workflow.runner import run_automation_job


router = APIRouter(
    prefix="/api",
    tags=["Automation"]
)


class JobRequest(BaseModel):
    topic: str


@router.post("/jobs")
def create_job(
    request: JobRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    job = Job(
        topic=request.topic,
        status="pending"
    )

    db.add(job)
    db.commit()
    db.refresh(job)

    # Runs after this response is sent. run_automation_job opens its
    # own DB session, since this request's session closes as soon as
    # this function returns.
    background_tasks.add_task(
        run_automation_job,
        job.id,
        request.topic,
    )

    return {
        "job_id": job.id,
        "topic": job.topic,
        "status": job.status,
        "message": "Automation job created successfully"
    }


@router.get("/jobs")
def list_jobs(
    limit: int = 20,
    db: Session = Depends(get_db)
):
    jobs = (
        db.query(Job)
        .order_by(Job.id.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "job_id": job.id,
            "topic": job.topic,
            "status": job.status,
            "created_at": job.created_at,
            "completed_at": job.completed_at,
        }
        for job in jobs
    ]


@router.get("/jobs/{job_id}")
def get_job(
    job_id: int,
    db: Session = Depends(get_db)
):
    job = db.query(Job).filter(Job.id == job_id).first()

    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    logs = (
        db.query(AutomationLog)
        .filter(AutomationLog.job_id == job_id)
        .order_by(AutomationLog.id.asc())
        .all()
    )

    content = (
        db.query(GeneratedContent)
        .filter(GeneratedContent.job_id == job_id)
        .first()
    )

    return {
        "job_id": job.id,
        "topic": job.topic,
        "status": job.status,
        "created_at": job.created_at,
        "completed_at": job.completed_at,
        "logs": [
            {
                "step": log.step,
                "status": log.status,
                "message": log.message,
                "timestamp": log.timestamp,
            }
            for log in logs
        ],
        "content": (
            {
                "title": content.title,
                "content": content.content,
            }
            if content else None
        ),
    }


@router.delete("/jobs/{job_id}")
def delete_job(
    job_id: int,
    db: Session = Depends(get_db)
):
    job = db.query(Job).filter(Job.id == job_id).first()

    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    db.delete(job)
    db.commit()

    return {
        "message": f"Job #{job_id} deleted successfully"
    }