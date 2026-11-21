from datetime import datetime, timezone
from sqlalchemy import String, Text, Integer, Float, DateTime, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base

def now(): return datetime.now(timezone.utc)

class Profile(Base):
    __tablename__ = "profile"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str | None] = mapped_column(String(200))
    resume_text: Mapped[str] = mapped_column(Text, default="")
    skills: Mapped[str] = mapped_column(Text, default="[]")
    roles: Mapped[str] = mapped_column(Text, default='["Software Engineer", "Backend Developer", "Java Developer"]')
    locations: Mapped[str] = mapped_column(Text, default="[]")
    graduation_year: Mapped[int | None] = mapped_column(Integer)
    education: Mapped[str | None] = mapped_column(Text, nullable=True)
    college: Mapped[str | None] = mapped_column(String(300), nullable=True)
    degree: Mapped[str | None] = mapped_column(String(200), nullable=True)
    cgpa: Mapped[str | None] = mapped_column(String(40), nullable=True)
    experience_json: Mapped[str] = mapped_column(Text, default="[]")
    projects_json: Mapped[str] = mapped_column(Text, default="[]")
    certifications_json: Mapped[str] = mapped_column(Text, default="[]")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)

class Resume(Base):
    __tablename__ = "resumes"
    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(500))
    file_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    extracted_text: Mapped[str] = mapped_column(Text)
    profile_version: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Source(Base):
    __tablename__ = "sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[str] = mapped_column(String(100), unique=True)
    title: Mapped[str] = mapped_column(String(300))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_message_id: Mapped[int] = mapped_column(Integer, default=0)

class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[str] = mapped_column(String(100))
    message_id: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (UniqueConstraint("chat_id", "message_id"),)

class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(300), default="Opportunity")
    company: Mapped[str | None] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(300))
    employment_type: Mapped[str | None] = mapped_column(String(100))
    experience_required: Mapped[str | None] = mapped_column(String(200), nullable=True)
    education_required: Mapped[str | None] = mapped_column(Text, nullable=True)
    graduation_year: Mapped[str | None] = mapped_column(String(100), nullable=True)
    work_mode: Mapped[str | None] = mapped_column(String(100), nullable=True)
    salary: Mapped[str | None] = mapped_column(String(200), nullable=True)
    application_deadline: Mapped[str | None] = mapped_column(String(100), nullable=True)
    application_url: Mapped[str | None] = mapped_column(String(1000))
    contact_email: Mapped[str | None] = mapped_column(String(300), nullable=True)
    contact_information: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_title: Mapped[str] = mapped_column(String(300), default="")
    source_chat_id: Mapped[str] = mapped_column(String(100), default="")
    source_message_id: Mapped[int] = mapped_column(Integer, default=0)
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    score: Mapped[int] = mapped_column(Integer, default=0)
    matched_skills: Mapped[str] = mapped_column(Text, default="[]")
    missing_skills: Mapped[str] = mapped_column(Text, default="[]")
    required_skills: Mapped[str] = mapped_column(Text, default="[]")
    notified: Mapped[bool] = mapped_column(Boolean, default=False)
    extraction_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    eligibility: Mapped[str] = mapped_column(String(40), default="Insufficient Information")
    review_reasons: Mapped[str] = mapped_column(Text, default="[]")
    application_status: Mapped[str] = mapped_column(String(40), default="New")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class JobSource(Base):
    __tablename__ = "job_sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    chat_id: Mapped[str] = mapped_column(String(100))
    message_id: Mapped[int] = mapped_column(Integer)
    source_title: Mapped[str] = mapped_column(String(300))
    original_message: Mapped[str] = mapped_column(Text)
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("chat_id", "message_id"),)

class Application(Base):
    __tablename__ = "applications"
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), unique=True)
    status: Mapped[str] = mapped_column(String(40), default="Saved")
    notes: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)

class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    immediate_threshold: Mapped[int] = mapped_column(Integer, default=65)
    daily_digest: Mapped[bool] = mapped_column(Boolean, default=False)
    last_digest_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    chat_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    channel: Mapped[str] = mapped_column(String(30), default="telegram")
    status: Mapped[str] = mapped_column(String(30), default="pending")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
