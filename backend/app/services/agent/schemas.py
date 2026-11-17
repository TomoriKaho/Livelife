from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CreateSessionResponse(BaseModel):
    is_pinned: bool = False
    session_id: UUID
    session_token: str
    title: str
    created_at: datetime
    updated_at: datetime
    expires_at: datetime | None


class CitationResponse(BaseModel):
    rank: int
    information_id: UUID
    title: str | None
    source_url: str | None
    platform: str
    source_id: str
    published_at: datetime | None
    snippet: str
    activity_location: str | None = None
    activity_start_at: datetime | None = None
    activity_end_at: datetime | None = None
    registration_deadline_at: datetime | None = None


class MessageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    role: str
    content: str
    status: str
    citations: list[CitationResponse] = Field(default_factory=list)
    rating: str | None = None
    created_at: datetime
    client_request_id: UUID | None = None
    request_id: UUID | None = None
    completed_at: datetime | None = None


class SessionResponse(BaseModel):
    session_id: UUID
    expires_at: datetime | None
    messages: list[MessageResponse]


class LocationContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    accuracy: float = Field(ge=0, allow_inf_nan=False)
    timestamp: float = Field(ge=0, allow_inf_nan=False)


class SendMessageRequest(BaseModel):
    content: str
    client_request_id: UUID
    location: LocationContext | None = None


class AgentRatingRequest(BaseModel):
    rating: str | None


class SessionSummary(BaseModel):
    is_pinned: bool = False
    session_id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    expires_at: datetime | None


class SessionListResponse(BaseModel):
    items: list[SessionSummary]
    next_offset: int | None


class ConversationResponse(SessionSummary):
    messages: list[MessageResponse]
    next_before: int | None


class PinSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_pinned: bool = Field(strict=True)
