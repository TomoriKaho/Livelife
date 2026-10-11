"""Transport-independent input, output and query contracts for information services."""

from datetime import UTC, datetime
from typing import Annotated, Self
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
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


class InformationFields(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    platform: Platform
    source_id: SourceId
    source_url: HttpUrl | None = None
    title: ShortText | None = None
    content: str = Field(min_length=1)
    fetched_at: AwareDatetime
    published_at: AwareDatetime | None = None
    activity_location: ShortText | None = None
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
        return self
