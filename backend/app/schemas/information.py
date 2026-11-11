"""Transport-independent input, output and query contracts for information services."""

from datetime import UTC, date, datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    FiniteFloat,
    HttpUrl,
    JsonValue,
    StringConstraints,
    field_validator,
    model_validator,
)

Platform = Annotated[
    str, StringConstraints(strip_whitespace=True, pattern=r"^[a-z][a-z0-9_]*$", max_length=64)
]
SourceId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
PlaceId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Longitude = Annotated[FiniteFloat, Field(ge=-180, le=180)]
Latitude = Annotated[FiniteFloat, Field(ge=-90, le=90)]


class MapPlace(BaseModel):
    """A point keyed by the building ID in the campus map."""

    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: PlaceId
    name: ShortText
    longitude: Longitude
    latitude: Latitude
    building_id: PlaceId | None = None
    campus: str = "北京大学燕园"
    coordinate_system: Literal["WGS84"] = "WGS84"


class LocationResolution(BaseModel):
    status: Literal["matched", "ambiguous", "unmatched"]
    place_id: PlaceId | None = None
    candidates: tuple[str, ...] = ()
    room: str | None = None
    floor: str | None = None
    precision: Literal["building"] | None = None
    method: Literal["alias", "explicit", "none"] = "none"
    matched_alias: str | None = None
    evidence: str | None = None
    resolver_version: str = "campus-alias-v1"


class InformationFields(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    platform: Platform
    source_id: SourceId
    source_url: HttpUrl | None = None
    source_name: ShortText | None = None
    title: ShortText | None = None
    content: str = Field(min_length=1)
    fetched_at: AwareDatetime
    published_at: AwareDatetime | None = None
    activity_location: ShortText | None = None
    place_id: PlaceId | None = None
    activity_date: date | None = None
    activity_start_at: AwareDatetime | None = None
    activity_end_at: AwareDatetime | None = None
    registration_deadline_at: AwareDatetime | None = None

    @field_validator("content")
    @classmethod
    def require_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("content must contain non-whitespace text")
        # Preserve the adapter's original text until aggregation.
        return value

    @field_validator(
        "fetched_at",
        "published_at",
        "activity_start_at",
        "activity_end_at",
        "registration_deadline_at",
    )
    @classmethod
    def normalize_time(cls, value: datetime | None) -> datetime | None:
        return value.astimezone(UTC) if value is not None else None

    @model_validator(mode="after")
    def check_activity_interval(self) -> Self:
        if (
            self.activity_start_at is not None
            and self.activity_end_at is not None
            and self.activity_end_at <= self.activity_start_at
        ):
            raise ValueError("activity_end_at must be later than activity_start_at")
        return self


class InformationInput(InformationFields):
    raw_payload: dict[str, JsonValue] = Field(default_factory=dict)


class Information(InformationFields):
    model_config = ConfigDict(extra="forbid", frozen=True, from_attributes=True)

    id: UUID
    place: MapPlace | None = None
    location_resolution: LocationResolution | None = None
    first_fetched_at: AwareDatetime
    processed_at: AwareDatetime


class InformationQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    platform: Platform | None = None
    fetched_after: AwareDatetime | None = None
    fetched_before: AwareDatetime | None = None
    activity_after: AwareDatetime | None = None
    activity_before: AwareDatetime | None = None
    activity_location: ShortText | None = None
    keyword: ShortText | None = None
    longitude: Longitude | None = None
    latitude: Latitude | None = None
    radius_m: Annotated[FiniteFloat, Field(gt=0, le=50_000)] | None = None
    events_only: bool = False
    order_by: Literal["fetched", "activity"] = "fetched"
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

    @field_validator("fetched_after", "fetched_before", "activity_after", "activity_before")
    @classmethod
    def normalize_time(cls, value: datetime | None) -> datetime | None:
        return value.astimezone(UTC) if value is not None else None

    @model_validator(mode="after")
    def check_windows(self) -> Self:
        for start, end in (
            (self.fetched_after, self.fetched_before),
            (self.activity_after, self.activity_before),
        ):
            if start is not None and end is not None and end <= start:
                raise ValueError("query window end must be later than its start")
        coordinates = (self.longitude, self.latitude, self.radius_m)
        if any(value is not None for value in coordinates) and any(
            value is None for value in coordinates
        ):
            raise ValueError("longitude, latitude and radius_m must be supplied together")
        return self
