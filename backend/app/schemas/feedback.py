from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator


class FeedbackSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_request_id: UUID
    content: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]

    @field_validator("content")
    @classmethod
    def valid_content(cls, value: str) -> str:
        if "\x00" in value:
            raise ValueError("Feedback must contain 1-500 characters and no NUL")
        return value


class FeedbackReceipt(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    submitted_at: datetime
