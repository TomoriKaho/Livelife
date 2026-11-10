from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CreateSessionResponse(BaseModel):
    session_id: UUID
    session_token: str
    expires_at: datetime


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


class SessionResponse(BaseModel):
    session_id: UUID
    expires_at: datetime
    messages: list[MessageResponse]


class SendMessageRequest(BaseModel):
    content: str
    client_request_id: UUID


class AgentRatingRequest(BaseModel):
    rating: str | None
