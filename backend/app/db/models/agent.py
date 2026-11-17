from datetime import date, datetime
from uuid import UUID

from sqlalchemy import JSON, Boolean, Date, ForeignKey, Index, Integer, String, Uuid, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base
from app.db.types import UTCDateTime


class AgentSession(Base):
    """Account-owned conversation; login expiry does not expire history."""

    __tablename__ = "agent_sessions"
    __table_args__ = (
        Index("ix_agent_session_expires", "expires_at"),
        Index("ix_agent_owner_updated", "user_id", "last_seen_at", "id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    legacy_messages: Mapped[list[dict]] = mapped_column("messages", JSON, default=list)
    title: Mapped[str] = mapped_column(String(100), default="新的对话")
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    message_rows: Mapped[list["AgentMessage"]] = relationship(
        cascade="all, delete-orphan", order_by="AgentMessage.sequence", lazy="select"
    )

    @property
    def messages(self) -> list[dict]:
        return [dict(row.payload) for row in self.message_rows]

    @messages.setter
    def messages(self, values: list[dict]) -> None:
        existing = {str(row.id): row for row in self.message_rows}
        rows = []
        for sequence, value in enumerate(values, 1):
            key = str(value["id"])
            row = existing.get(key) or AgentMessage(id=UUID(key), sequence=sequence)
            row.sequence = sequence
            row.payload = dict(value)
            rows.append(row)
        self.message_rows = rows

    created_at: Mapped[datetime] = mapped_column(UTCDateTime())
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime())
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
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


class AgentUserUsage(Base):
    """One locked budget and active model request across all of an account's sessions."""

    __tablename__ = "agent_user_usage"

    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    request_window_start: Mapped[datetime] = mapped_column(UTCDateTime())
    request_count: Mapped[int] = mapped_column(Integer, default=0)
    active_request_id: Mapped[str | None] = mapped_column(String(36))
    active_request_expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    usage_day: Mapped[date] = mapped_column(Date)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    tokens_reserved: Mapped[int] = mapped_column(Integer, default=0)


class AgentMessage(Base):
    __tablename__ = "agent_messages"
    __table_args__ = (Index("ix_agent_message_order", "session_id", "sequence", unique=True),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    session_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("agent_sessions.id", ondelete="CASCADE")
    )
    sequence: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSON)
