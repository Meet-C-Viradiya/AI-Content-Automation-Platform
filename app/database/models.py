from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, Text, String, ForeignKey
from sqlalchemy.orm import relationship

from app.database.database import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    topic = Column(String(500), nullable=False)
    status = Column(String(50), default="pending", nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    logs = relationship(
        "AutomationLog",
        back_populates="job",
        cascade="all, delete-orphan"
    )

    content = relationship(
        "GeneratedContent",
        back_populates="job",
        cascade="all, delete-orphan",
        uselist=False
    )


class AutomationLog(Base):
    __tablename__ = "automation_logs"

    id = Column(Integer, primary_key=True, index=True)

    job_id = Column(
        Integer,
        ForeignKey("jobs.id"),
        nullable=False
    )

    step = Column(String(100), nullable=False)
    status = Column(String(50), nullable=False)
    message = Column(Text, nullable=True)

    timestamp = Column(DateTime, default=datetime.utcnow)

    job = relationship(
        "Job",
        back_populates="logs"
    )


class GeneratedContent(Base):
    __tablename__ = "generated_content"

    id = Column(Integer, primary_key=True, index=True)

    job_id = Column(
        Integer,
        ForeignKey("jobs.id"),
        nullable=False,
        unique=True
    )

    title = Column(String(500), nullable=True)
    content = Column(Text, nullable=False)

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    job = relationship(
        "Job",
        back_populates="content"
    )