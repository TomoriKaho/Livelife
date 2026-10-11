from fastapi import APIRouter, Request, Response
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import Database
from app.schemas.health import HealthResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=HealthResponse)
def live() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get(
    "/ready",
    response_model=HealthResponse,
    responses={503: {"model": HealthResponse}},
)
def ready(request: Request, response: Response) -> HealthResponse:
    database: Database = request.app.state.database
    if not database.configured:
        response.status_code = 503
        return HealthResponse(status="not_ready", database="not_configured")

    try:
        database.check_connection()
    except SQLAlchemyError:
        response.status_code = 503
        return HealthResponse(status="not_ready", database="unavailable")

    return HealthResponse(status="ok", database="connected")
