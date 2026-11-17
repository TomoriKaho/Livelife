"""Favorite projections; a missing source never fabricates current activity data."""

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, HttpUrl

from app.schemas.information import MapPlace

FavoriteStatus = Literal["upcoming", "ongoing", "ended", "unknown"]


class FavoriteItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    saved_at: AwareDatetime
    available: bool
    title: str | None
    platform: str
    source_name: str | None
    source_url: HttpUrl | None
    activity_date: date | None
    start_at: AwareDatetime | None
    end_at: AwareDatetime | None
    location: str | None
    place: MapPlace | None
    status: FavoriteStatus


class FavoritePage(BaseModel):
    items: list[FavoriteItem]
    as_of: AwareDatetime
    counts: dict[FavoriteStatus, int]
    total: int
    next_offset: int | None


class FavoriteIds(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ids: list[UUID] = Field(max_length=100)


class FavoriteMembership(BaseModel):
    saved_ids: list[UUID]
