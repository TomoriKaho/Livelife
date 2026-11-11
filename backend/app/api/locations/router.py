"""Read-only HTTP adapter; location and filtering policy live in content services."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.db.dependencies import get_session
from app.schemas.location_activity import MapActivityPage, MapActivityQuery
from app.services.content.map_query import map_activities

router = APIRouter(prefix="/locations", tags=["locations"])


@router.get(
    "/activities", response_model=MapActivityPage, responses={503: {"description": "数据库未配置"}}
)
def list_map_activities(
    response: Response,
    session: Annotated[Session, Depends(get_session)],
    query: Annotated[MapActivityQuery, Query()],
) -> MapActivityPage:
    response.headers["Cache-Control"] = "no-store"
    try:
        return map_activities(session, query)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
