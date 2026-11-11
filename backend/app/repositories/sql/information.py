from datetime import datetime
from math import cos, degrees, radians, sin
from uuid import UUID, uuid4

from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session, contains_eager

from app.db.models import InformationRecord, MapPlaceRecord
from app.schemas.information import InformationInput, InformationQuery, LocationResolution

EARTH_RADIUS_M = 6_371_008.8


class InformationRepository:
    """SQL operations only; the aggregation service owns the transaction."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert(
        self,
        item: InformationInput,
        processed_at: datetime,
        resolution: LocationResolution | None = None,
    ) -> None:
        dialect = self.session.get_bind().dialect.name
        if dialect == "postgresql":
            insert = pg_insert
        elif dialect == "sqlite":
            insert = sqlite_insert
        else:
            raise ValueError("information storage supports PostgreSQL and test SQLite only")

        values = item.model_dump(exclude={"raw_payload", "source_url"})
        values.update(
            id=uuid4(),
            source_url=str(item.source_url) if item.source_url is not None else None,
            content=item.content.strip(),
            raw_content=item.content,
            raw_payload=item.raw_payload,
            first_fetched_at=item.fetched_at,
            processed_at=processed_at,
            location_resolution=resolution.model_dump(mode="json") if resolution else None,
        )
        if resolution is not None:
            values["place_id"] = resolution.place_id
        statement = insert(InformationRecord).values(**values)
        statement = statement.on_conflict_do_update(
            index_elements=["platform", "source_id"],
            set_={
                key: getattr(statement.excluded, key)
                for key in values
                if key not in {"id", "platform", "source_id", "first_fetched_at"}
            },
            # Replays and late arrivals cannot overwrite a newer snapshot.
            where=InformationRecord.fetched_at < statement.excluded.fetched_at,
        )
        self.session.execute(statement)

    def get(self, information_id: UUID) -> InformationRecord | None:
        return self.session.get(InformationRecord, information_id, populate_existing=True)

    def get_by_source(self, platform: str, source_id: str) -> InformationRecord:
        statement = select(InformationRecord).where(
            InformationRecord.platform == platform, InformationRecord.source_id == source_id
        )
        return self.session.scalars(statement.execution_options(populate_existing=True)).one()

    def list(self, query: InformationQuery) -> list[InformationRecord]:
        statement = select(InformationRecord)
        if query.events_only:
            statement = statement.where(
                InformationRecord.activity_start_at.is_not(None),
                InformationRecord.place_id.is_not(None),
            )
        if query.keyword is not None:
            statement = statement.where(
                or_(
                    InformationRecord.title.icontains(query.keyword, autoescape=True),
                    InformationRecord.content.icontains(query.keyword, autoescape=True),
                    InformationRecord.source_name.icontains(query.keyword, autoescape=True),
                    InformationRecord.activity_location.icontains(query.keyword, autoescape=True),
                )
            )
        if (
            query.longitude is not None
            and query.latitude is not None
            and query.radius_m is not None
        ):
            angular_radius = query.radius_m / EARTH_RADIUS_M
            delta_latitude = degrees(angular_radius)
            lat_term = func.sin(func.radians(MapPlaceRecord.latitude - query.latitude) / 2)
            lon_term = func.sin(func.radians(MapPlaceRecord.longitude - query.longitude) / 2)
            haversine = lat_term * lat_term + (
                cos(radians(query.latitude))
                * func.cos(func.radians(MapPlaceRecord.latitude))
                * lon_term
                * lon_term
            )
            statement = (
                statement.join(InformationRecord.place)
                .options(contains_eager(InformationRecord.place))
                .where(
                    MapPlaceRecord.latitude.between(
                        query.latitude - delta_latitude, query.latitude + delta_latitude
                    ),
                    haversine <= sin(angular_radius / 2) ** 2,
                )
            )
        if query.platform is not None:
            statement = statement.where(InformationRecord.platform == query.platform)
        if query.fetched_after is not None:
            statement = statement.where(InformationRecord.fetched_at >= query.fetched_after)
        if query.fetched_before is not None:
            statement = statement.where(InformationRecord.fetched_at < query.fetched_before)
        if query.activity_location is not None:
            statement = statement.where(
                InformationRecord.activity_location.contains(
                    query.activity_location, autoescape=True
                )
            )
        if query.activity_after is not None or query.activity_before is not None:
            statement = statement.where(InformationRecord.activity_start_at.is_not(None))
        if query.activity_before is not None:
            statement = statement.where(InformationRecord.activity_start_at < query.activity_before)
        if query.activity_after is not None:
            statement = statement.where(
                or_(
                    InformationRecord.activity_end_at > query.activity_after,
                    and_(
                        InformationRecord.activity_end_at.is_(None),
                        InformationRecord.activity_start_at >= query.activity_after,
                    ),
                )
            )
        statement = (
            statement.order_by(InformationRecord.fetched_at.desc(), InformationRecord.id.desc())
            .limit(query.limit)
            .offset(query.offset)
        )
        return list(self.session.scalars(statement.execution_options(populate_existing=True)))
