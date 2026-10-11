from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, CheckConstraint, Index, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base
from app.db.types import UTCDateTime


class InformationRecord(Base):
    __tablename__ = "information_items"
    __table_args__ = (
        UniqueConstraint("platform", "source_id", name="uq_information_source"),
        CheckConstraint(
            "activity_end_at IS NULL OR activity_start_at IS NULL "
            "OR activity_end_at > activity_start_at",
            name="ck_information_activity_interval",
        ),
        Index("ix_information_fetched", "fetched_at", "id"),
        Index("ix_information_platform_fetched", "platform", "fetched_at", "id"),
        Index("ix_information_activity", "activity_start_at", "activity_end_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    platform: Mapped[str] = mapped_column(String(64))
    source_id: Mapped[str] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text)
    raw_content: Mapped[str] = mapped_column(Text)
    raw_payload: Mapped[dict] = mapped_column(JSON)
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime())
    first_fetched_at: Mapped[datetime] = mapped_column(UTCDateTime())
    processed_at: Mapped[datetime] = mapped_column(UTCDateTime())
    published_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    activity_location: Mapped[str | None] = mapped_column(String(500))
    activity_start_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    activity_end_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    registration_deadline_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
