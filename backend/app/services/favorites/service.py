"""Current source projection plus an immutable, minimal bookmark snapshot."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import case, delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session, load_only

from app.db.models.accounts import User
from app.db.models.favorite import ActivityFavorite as Favorite
from app.db.models.information import InformationRecord as Information
from app.schemas.favorite import FavoriteItem, FavoritePage, FavoriteStatus
from app.schemas.information import MapPlace

STATUSES = ("upcoming", "ongoing", "ended", "unknown")


def is_activity():
    # The information system has no moderation flag yet. Future visibility policy
    # belongs here as well, so hidden sources are never re-exposed by bookmarks.
    return (Information.platform != "demo") & or_(
        Information.activity_date.is_not(None), Information.activity_start_at.is_not(None)
    )


def status_at(start: datetime | None, end: datetime | None, now: datetime) -> FavoriteStatus:
    if start is None:
        return "unknown"
    if now < start:
        return "upcoming"
    return "ongoing" if end is not None and now < end else "ended"


def project(row: Favorite, source: Information | None, now: datetime) -> FavoriteItem:
    available = (
        source is not None
        and source.platform != "demo"
        and (source.activity_date is not None or source.activity_start_at is not None)
    )
    start = source.activity_start_at if available else row.start_at
    end = source.activity_end_at if available else row.end_at
    return FavoriteItem(
        id=row.information_id,
        saved_at=row.created_at,
        available=available,
        title=source.title if available else row.title,
        platform=source.platform if available else row.platform,
        source_name=source.source_name if available else row.source_name,
        source_url=source.source_url if available else row.source_url,
        activity_date=source.activity_date if available else row.activity_date,
        start_at=start,
        end_at=end,
        location=source.activity_location if available else None,
        place=MapPlace.model_validate(source.place) if available and source.place else None,
        status=status_at(start, end, now),
    )


def lock_owner(session: Session, owner: UUID) -> None:
    # Same first lock as account deletion; serializes simultaneous bookmark writes.
    if session.scalar(select(User.id).where(User.id == owner).with_for_update()) is None:
        raise HTTPException(status_code=401, detail="Session is invalid or expired")


def read_favorite(session: Session, owner: UUID, target: UUID) -> FavoriteItem:
    row = session.get(Favorite, (owner, target))
    if row is None:
        raise HTTPException(status_code=404, detail="Favorite not found")
    return project(row, session.get(Information, target), datetime.now(UTC))


def save_favorite(session: Session, owner: UUID, target: UUID) -> FavoriteItem:
    lock_owner(session, owner)
    existing = session.get(Favorite, (owner, target))
    if existing is None:
        source = session.scalar(select(Information).where(Information.id == target, is_activity()))
        if source is None:
            raise HTTPException(status_code=404, detail="Activity not found")
        values = dict(
            user_id=owner,
            information_id=target,
            created_at=datetime.now(UTC),
            title=source.title,
            platform=source.platform,
            source_name=source.source_name,
            source_url=source.source_url,
            activity_date=source.activity_date,
            start_at=source.activity_start_at,
            end_at=source.activity_end_at,
        )
        insert = pg_insert if session.bind.dialect.name == "postgresql" else sqlite_insert
        session.execute(
            insert(Favorite)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["user_id", "information_id"])
        )
    session.commit()
    return read_favorite(session, owner, target)


def remove_favorite(session: Session, owner: UUID, target: UUID) -> None:
    lock_owner(session, owner)
    session.execute(
        delete(Favorite).where(Favorite.user_id == owner, Favorite.information_id == target)
    )
    session.commit()


def list_favorites(
    session: Session,
    owner: UUID,
    status: FavoriteStatus | None,
    limit: int,
    offset: int,
    now: datetime,
) -> FavoritePage:
    available = is_activity()
    start = case((available, Information.activity_start_at), else_=Favorite.start_at)
    end = case((available, Information.activity_end_at), else_=Favorite.end_at)
    classification = case(
        (start.is_(None), "unknown"),
        (start > now, "upcoming"),
        ((end.is_not(None)) & (end > now), "ongoing"),
        else_="ended",
    )
    base = (
        select(Favorite, Information)
        .outerjoin(Information, Information.id == Favorite.information_id)
        .where(Favorite.user_id == owner)
    )
    counts = dict.fromkeys(STATUSES, 0)
    counts.update(
        dict(
            session.execute(
                base.with_only_columns(classification, func.count()).group_by(classification)
            ).all()
        )
    )
    if status:
        base = base.where(classification == status)
    rows = session.execute(
        base.options(
            load_only(
                Information.id,
                Information.platform,
                Information.title,
                Information.source_name,
                Information.source_url,
                Information.activity_date,
                Information.activity_start_at,
                Information.activity_end_at,
                Information.activity_location,
                Information.place_id,
            )
        )
        .order_by(Favorite.created_at.desc(), Favorite.information_id.desc())
        .offset(offset)
        .limit(limit + 1)
    ).all()
    return FavoritePage(
        items=[project(row, source, now) for row, source in rows[:limit]],
        as_of=now,
        counts=counts,
        total=sum(counts.values()),
        next_offset=offset + limit if len(rows) > limit else None,
    )
