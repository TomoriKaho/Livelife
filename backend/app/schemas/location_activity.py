"""Public map projection of information-system queries."""

from datetime import datetime
from typing import Annotated, Self
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    FiniteFloat,
    HttpUrl,
    model_validator,
)

from app.schemas.information import Latitude, LocationResolution, Longitude, MapPlace, ShortText


class MapActivityQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    as_of: AwareDatetime | None = None
    activity_before: AwareDatetime | None = None
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    radius_m: Annotated[FiniteFloat, Field(gt=0, le=50_000)] | None = None
    timestamp: Annotated[FiniteFloat, Field(ge=0)] | None = None
    keyword: ShortText | None = None
    limit: int = Field(default=100, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_center(self) -> Self:
        center = (self.latitude, self.longitude, self.radius_m)
        if any(v is not None for v in center) and any(v is None for v in center):
            raise ValueError("latitude, longitude and radius_m must be supplied together")
        if self.latitude is not None and self.timestamp is None:
            raise ValueError("nearby queries require a fresh location timestamp")
        if self.timestamp is not None and self.latitude is None:
            raise ValueError("timestamp requires a query center")
        if self.as_of and self.activity_before and self.activity_before <= self.as_of:
            raise ValueError("activity_before must be later than as_of")
        return self


class MapActivity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: UUID
    title: str | None
    summary: str
    platform: str
    source_url: HttpUrl | None
    source_name: str | None
    location: str
    start_at: AwareDatetime
    end_at: AwareDatetime | None
    place: MapPlace
    location_resolution: LocationResolution | None
    distance_m: float | None


class NearbyBuilding(BaseModel):
    place: MapPlace
    distance_m: float
    first_activity_at: datetime | None


class MapActivityPage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    as_of: AwareDatetime
    window_end: AwareDatetime
    items: tuple[MapActivity, ...]
    nearby_buildings: tuple[NearbyBuilding, ...]
    next_offset: int | None
