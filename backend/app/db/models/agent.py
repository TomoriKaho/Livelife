from datetime import date, datetime
from uuid import UUID

from sqlalchemy import JSON, Date, Index, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base
from app.db.types import UTCDateTime


class AgentSession(Base):
    """Short-lived anonymous conversation, including its bounded transcript."""

    __tablename__ = "agent_sessions"
    __table_args__ = (Index("ix_agent_session_expires", "expires_at"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    messages: Mapped[list[dict]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime())
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    request_window_start: Mapped[datetime] = mapped_column(UTCDateTime())
    request_count: Mapped[int] = mapped_column(Integer, default=0)
    active_request_id: Mapped[str | None] = mapped_column(String(36))
    active_request_expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    usage_day: Mapped[date] = mapped_column(Date)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    tokens_reserved: Mapped[int] = mapped_column(Integer, default=0)


class AgentIpWindow(Base):
    """Atomic hourly request counter shared by sessions with the same IP digest."""

    __tablename__ = "agent_ip_windows"

    ip_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(UTCDateTime())
    request_count: Mapped[int] = mapped_column(Integer, default=0)
