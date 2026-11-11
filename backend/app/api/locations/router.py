"""Read-only public activity feed for map-side building matching."""

from datetime import UTC, datetime, time, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Response
from pydantic import AwareDatetime
from sqlalchemy.orm import Session

from app.db.dependencies import get_session
from app.schemas.information import InformationQuery
from app.schemas.location_activity import MapActivity, MapActivityPage
from app.services.content import InformationProvider

router = APIRouter(prefix="/locations", tags=["locations"])
BEIJING = ZoneInfo("Asia/Shanghai")


@router.get(
    "/activities",
    response_model=MapActivityPage,
    responses={503: {"description": "数据库未配置"}},
)
def list_map_activities(
    response: Response,
    session: Annotated[Session, Depends(get_session)],
    as_of: Annotated[AwareDatetime | None, Query(description="带时区的查询时刻")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> MapActivityPage:
    """Return non-ended activities in the current Beijing day, with source positions."""

    instant = as_of.astimezone(UTC) if as_of is not None else datetime.now(UTC)
    local_day = instant.astimezone(BEIJING).date()
    tomorrow = datetime.combine(local_day + timedelta(days=1), time.min, BEIJING)
    records = InformationProvider(session).list(
        InformationQuery(
            activity_after=instant,
            activity_before=tomorrow,
            limit=limit,
            offset=offset,
        )
    )
    response.headers["Cache-Control"] = "no-store"
    return MapActivityPage(
        as_of=instant,
        items=tuple(
            MapActivity(
                id=item.id,
                title=item.title,
                summary=item.content[:300],
                platform=item.platform,
                source_url=item.source_url,
                location=item.activity_location,
                start_at=item.activity_start_at,
                end_at=item.activity_end_at,
            )
            for item in records
            if item.activity_location is not None and item.activity_start_at is not None
        ),
        next_offset=offset + limit if len(records) == limit else None,
    )
