from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok", "not_ready"]
    database: Literal["connected", "not_configured", "unavailable"] | None = None
