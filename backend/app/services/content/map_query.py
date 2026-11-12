"""One information-system policy for map filtering, ordering and nearby places."""

from datetime import UTC, datetime, time, timedelta
from math import asin, cos, radians, sin, sqrt
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import MapPlaceRecord
from app.repositories.sql.information import EARTH_RADIUS_M, InformationRepository
from app.schemas.information import InformationQuery, MapPlace
from app.schemas.location_activity import (
    MapActivity,
    MapActivityPage,
    MapActivityQuery,
    NearbyBuilding,
)
from app.services.content.provider import InformationProvider

BEIJING = ZoneInfo("Asia/Shanghai")


def distance_m(latitude: float, longitude: float, place: MapPlace) -> float:
    h = (
        sin(radians(place.latitude - latitude) / 2) ** 2
        + cos(radians(latitude))
        * cos(radians(place.latitude))
        * sin(radians(place.longitude - longitude) / 2) ** 2
    )
    return EARTH_RADIUS_M * 2 * asin(sqrt(min(1, max(0, h))))


def map_activities(session: Session, request: MapActivityQuery) -> MapActivityPage:
    now = datetime.now(UTC)
    if (
        request.timestamp is not None
        and not -10_000 <= now.timestamp() * 1000 - request.timestamp <= 120_000
    ):
        raise ValueError("Refresh location before searching nearby")
    instant = request.as_of.astimezone(UTC) if request.as_of else now
    end = request.activity_before or datetime.combine(
        instant.astimezone(BEIJING).date() + timedelta(days=3), time.min, BEIJING
    )
    query = InformationQuery(
        activity_after=instant,
        activity_before=end,
        keyword=request.keyword,
        latitude=request.latitude,
        longitude=request.longitude,
        radius_m=request.radius_m,
        events_only=True,
        order_by="activity",
        limit=request.limit,
        offset=request.offset,
    )
    records = InformationProvider(session).list(query)

    def distance(place):
        return (
            distance_m(request.latitude, request.longitude, place)
            if request.latitude is not None
            else None
        )

    buildings = []
    if request.latitude is not None:
        # Aggregate over the full filtered set, not just the current response page.
        statement = InformationRepository(session).statement(query).subquery()
        starts = dict(
            session.execute(
                select(statement.c.place_id, func.min(statement.c.activity_start_at)).group_by(
                    statement.c.place_id
                )
            ).all()
        )
        for row in session.scalars(
            select(MapPlaceRecord).where(MapPlaceRecord.building_id.is_not(None))
        ):
            place = MapPlace.model_validate(row)
            meters = distance(place)
            if meters <= request.radius_m:
                buildings.append(
                    NearbyBuilding(
                        place=place, distance_m=meters, first_activity_at=starts.get(place.id)
                    )
                )
        buildings.sort(
            key=lambda b: (
                b.first_activity_at is None,
                b.first_activity_at or datetime.max.replace(tzinfo=UTC),
                b.distance_m,
                b.place.id,
            )
        )
    return MapActivityPage(
        as_of=instant,
        window_end=end,
        nearby_buildings=tuple(buildings[:5]),
        items=tuple(
            MapActivity(
                id=item.id,
                title=item.title,
                summary=item.content[:300],
                platform=item.platform,
                source_url=item.source_url,
                source_name=item.source_name,
                location=item.activity_location or item.place.name,
                start_at=item.activity_start_at,
                end_at=item.activity_end_at,
                place=item.place,
                location_resolution=item.location_resolution,
                distance_m=distance(item.place),
            )
            for item in records
        ),
        next_offset=request.offset + request.limit if len(records) == request.limit else None,
    )
