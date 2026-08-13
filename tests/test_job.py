from datetime import datetime
from app.database.database import SessionLocal, Base, engine
from app.database.models import Job, AutomationLog, GeneratedContent

def test_job_creation():

    Base.metadata.create_all(bind=engine)
        
    db = SessionLocal()

    try:
        # 1. Create a new automation job
        job = Job(
            topic="AI Automation for Small Businesses",
            status="processing"
        )

        db.add(job)
        db.commit()
        db.refresh(job)

        print(f"Job created successfully!")
        print(f"Job ID: {job.id}")

        # 2. Add workflow logs
        steps = [
            ("request_received", "completed", "Client request received"),
            ("research", "completed", "Web research completed"),
            ("planning", "completed", "Content plan created"),
            ("generation", "completed", "AI content generated"),
        ]

        for step, status, message in steps:
            log = AutomationLog(
                job_id=job.id,
                step=step,
                status=status,
                message=message
            )

            db.add(log)

        db.commit()

        print("Workflow logs added successfully!")

        # 3. Save generated content
        content = GeneratedContent(
            job_id=job.id,
            title="AI Automation for Small Businesses",
            content=(
                "Artificial intelligence automation can help "
                "small businesses improve productivity, reduce "
                "manual work, and streamline repetitive processes."
            )
        )

        db.add(content)

        # 4. Mark job as completed
        job.status = "completed"
        job.completed_at = datetime.utcnow()

        db.commit()

        print("Generated content saved successfully!")
        print("Job marked as completed!")

    finally:
        db.close()


if __name__ == "__main__":
    test_job_creation()