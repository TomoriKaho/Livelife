"""Public activity records consumed by the campus map."""

from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, HttpUrl


class MapActivity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    title: str | None
    summary: str
    platform: str
    source_url: HttpUrl | None
    location: str
    start_at: AwareDatetime
    end_at: AwareDatetime | None


class MapActivityPage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    as_of: AwareDatetime
    items: tuple[MapActivity, ...]
    next_offset: int | None
