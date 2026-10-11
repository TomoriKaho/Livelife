from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import and_, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.db.models import InformationRecord
from app.schemas.information import InformationInput, InformationQuery


class InformationRepository:
    """SQL operations only; the aggregation service owns the transaction."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert(self, item: InformationInput, processed_at: datetime) -> None:
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
        )
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
