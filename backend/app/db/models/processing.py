"""System extraction jobs and conservative per-attempt usage accounting."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base
from app.db.types import UTCDateTime


class ProcessingJob(Base):
    __tablename__ = "information_processing_jobs"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True)
    content_hash: Mapped[str] = mapped_column(String(64))
    version: Mapped[str] = mapped_column(String(100))
    model: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(32))
    source: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(String(100))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime())
    review: Mapped[dict | None] = mapped_column(JSON)


class ProcessingAttempt(Base):
    __tablename__ = "information_processing_attempts"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    job_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    reserved_tokens: Mapped[int] = mapped_column(Integer)
    diagnostics: Mapped[dict | None] = mapped_column(JSON)
    usage: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(String(100))


class ProcessingGate(Base):
    __tablename__ = "information_processing_gate"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner: Mapped[UUID | None] = mapped_column(Uuid)
    lease_until: Mapped[datetime] = mapped_column(UTCDateTime())
