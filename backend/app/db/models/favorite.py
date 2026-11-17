"""Account-owned bookmarks survive removal of the source information row."""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import Date, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base
from app.db.types import UTCDateTime


class ActivityFavorite(Base):
    __tablename__ = "activity_favorites"
    __table_args__ = (
        Index("ix_favorites_owner_created", "user_id", "created_at", "information_id"),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    # Intentionally no source FK: cleanup must leave an identifiable unavailable bookmark.
    information_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())
    title: Mapped[str | None] = mapped_column(String(500))
    platform: Mapped[str] = mapped_column(String(64))
    source_name: Mapped[str | None] = mapped_column(String(500))
    source_url: Mapped[str | None] = mapped_column(Text)
    activity_date: Mapped[date | None] = mapped_column(Date)
    start_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    end_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
