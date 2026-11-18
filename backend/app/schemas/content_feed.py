from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.schemas.information import Platform, ShortText


class ContentQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    keyword: ShortText | None = None
    platform: Platform | None = None
    source_name: ShortText | None = None
    limit: int = Field(default=20, ge=1, le=50)
    offset: int = Field(default=0, ge=0)


class ContentArticle(BaseModel):
    id: UUID
    title: str | None
    excerpt: str
    platform: str
    source_name: str | None
    source_url: HttpUrl | None
    published_at: datetime | None
    fetched_at: datetime


class ContentPage(BaseModel):
    items: list[ContentArticle]
    next_offset: int | None
