"""Feedback and processing audit records, both deleted with the account."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base
from app.db.types import UTCDateTime


class UserFeedback(Base):
    __tablename__ = "user_feedback"
    __table_args__ = (
        UniqueConstraint("user_id", "client_request_id", name="uq_feedback_owner_request"),
        CheckConstraint(
            "status IN ('pending', 'processing', 'resolved', 'closed')",
            name="ck_feedback_status",
        ),
        Index("ix_feedback_owner_submitted", "user_id", "submitted_at"),
        Index("ix_feedback_status_submitted", "status", "submitted_at", "id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    client_request_id: Mapped[UUID] = mapped_column(Uuid)
    content: Mapped[str] = mapped_column(Text)
    submitted_at: Mapped[datetime] = mapped_column(UTCDateTime())
    status: Mapped[str] = mapped_column(String(16))
    version: Mapped[int] = mapped_column()


class FeedbackEvent(Base):
    __tablename__ = "feedback_events"
    __table_args__ = (Index("ix_feedback_events_feedback", "feedback_id", "version"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    feedback_id: Mapped[UUID] = mapped_column(ForeignKey("user_feedback.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())
    actor: Mapped[str] = mapped_column(String(100))
    reason: Mapped[str] = mapped_column(String(1000))
    from_status: Mapped[str] = mapped_column(String(16))
    to_status: Mapped[str] = mapped_column(String(16))
    version: Mapped[int] = mapped_column()
