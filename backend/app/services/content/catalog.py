"""Explicit catalogue import/backfill; never run automatically at API startup."""

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import InformationRecord, MapPlaceRecord, PlaceAliasRecord
from app.db.session import Database
from app.services.content.locations import LocationResolver, normalize_location

CATALOG = Path(__file__).with_name("places.json")


def register_places(session: Session) -> None:
    """Insert missing catalogue entries without overwriting maintained coordinates/aliases."""
    for data in json.loads(CATALOG.read_text(encoding="utf-8")):
        aliases = data.pop("aliases")
        if session.get(MapPlaceRecord, data["id"]) is None:
            session.add(MapPlaceRecord(**data))
            session.flush()
        for alias in aliases:
            alias = normalize_location(alias)
            existing = session.scalar(
                select(PlaceAliasRecord).where(
                    PlaceAliasRecord.place_id == data["id"], PlaceAliasRecord.alias == alias
                )
            )
            if existing is None:
                session.add(PlaceAliasRecord(place_id=data["id"], alias=alias))
                session.flush()


def backfill_locations(session: Session) -> int:
    resolver = LocationResolver(session)
    count = 0
    for record in session.scalars(
        select(InformationRecord).where(InformationRecord.place_id.is_(None))
    ):
        resolution = resolver.resolve(record.activity_location)
        record.location_resolution = resolution.model_dump(mode="json")
        record.place_id = resolution.place_id
        count += resolution.status == "matched"
    return count


def main() -> None:
    database = Database.from_environment()
    if database.session_factory is None:
        raise RuntimeError("Set DATABASE_URL and migrate before importing the catalogue")
    try:
        with database.session_factory.begin() as session:
            register_places(session)
            count = backfill_locations(session)
        print(f"Catalogue registered; {count} existing records resolved.")
    finally:
        database.close()


if __name__ == "__main__":
    main()
