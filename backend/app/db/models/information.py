from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base
from app.db.types import UTCDateTime


class MapPlaceRecord(Base):
    __tablename__ = "information_places"
    __table_args__ = (
        CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_place_longitude"),
        CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_place_latitude"),
        Index("ix_information_places_latitude", "latitude"),
    )

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(500))
    longitude: Mapped[float] = mapped_column(Float)
    latitude: Mapped[float] = mapped_column(Float)
    building_id: Mapped[str | None] = mapped_column(String(100), index=True)
    campus: Mapped[str] = mapped_column(String(100), default="北京大学燕园")


class PlaceAliasRecord(Base):
    __tablename__ = "information_place_aliases"

    place_id: Mapped[str] = mapped_column(ForeignKey("information_places.id"), primary_key=True)
    alias: Mapped[str] = mapped_column(String(500), primary_key=True)


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
        Index("ix_information_place", "place_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    platform: Mapped[str] = mapped_column(String(64))
    source_id: Mapped[str] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(Text)
    source_name: Mapped[str | None] = mapped_column(String(500))
    title: Mapped[str | None] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text)
    raw_content: Mapped[str] = mapped_column(Text)
    raw_payload: Mapped[dict] = mapped_column(JSON)
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime())
    first_fetched_at: Mapped[datetime] = mapped_column(UTCDateTime())
    processed_at: Mapped[datetime] = mapped_column(UTCDateTime())
    published_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    activity_location: Mapped[str | None] = mapped_column(String(500))
    place_id: Mapped[str | None] = mapped_column(
        ForeignKey("information_places.id", name="fk_information_place")
    )
    place: Mapped[MapPlaceRecord | None] = relationship(lazy="joined")
    location_resolution: Mapped[dict | None] = mapped_column(JSON)
    activity_date: Mapped[date | None] = mapped_column(Date)
    activity_start_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    activity_end_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    registration_deadline_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
