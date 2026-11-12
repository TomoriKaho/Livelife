"""Map activity HTTP contract over the existing information store."""

from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Database
from app.main import app
from app.schemas.information import InformationInput
from app.services.content import InformationAggregator
from app.services.content.catalog import register_places

BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Database]:
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'map.db').as_posix()}")
    config = Config(str(BACKEND / "alembic.ini"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    database = Database.__new__(Database)
    database.engine = engine
    database.session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with database.session_factory.begin() as session:
        register_places(session)
    monkeypatch.setattr(app.state, "database", database)
    try:
        yield database
    finally:
        database.close()


@pytest.fixture
async def client(database: Database) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as value:
        yield value


@pytest.mark.anyio
async def test_map_activity_pages_skip_missing_location_and_expired_events(
    client: httpx.AsyncClient, database: Database
) -> None:
    with database.session_factory() as session:
        InformationAggregator(session).ingest(
            [
                InformationInput(
                    platform="manual",
                    source_id=str(index),
                    title=f"活动 {index}",
                    content="公开活动正文",
                    fetched_at=f"2026-11-11T{index:02d}:00:00+08:00",
                    activity_location=location,
                    activity_start_at=start,
                    activity_end_at=end,
                )
                for index, location, start, end in [
                    (1, "理科教学楼 101", "2026-11-11T14:00:00+08:00", None),
                    (2, None, "2026-11-11T15:00:00+08:00", None),
                    (
                        3,
                        "百周年纪念讲堂",
                        "2026-11-11T09:00:00+08:00",
                        "2026-11-11T12:00:00+08:00",
                    ),
                    (
                        4,
                        "第一教学楼",
                        "2026-11-11T08:00:00+08:00",
                        "2026-11-11T09:00:00+08:00",
                    ),
                ]
            ]
        )

    params = {"as_of": "2026-11-11T10:00:00+08:00", "limit": 2}
    first = await client.get("/locations/activities", params=params)
    assert first.status_code == 200
    assert first.headers["cache-control"] == "no-store"
    assert first.json()["next_offset"] == 2
    assert [item["title"] for item in first.json()["items"]] == ["活动 3", "活动 1"]

    second = await client.get("/locations/activities", params={**params, "offset": 2})
    assert second.status_code == 200
    assert second.json()["next_offset"] is None
    assert second.json()["items"] == []
    assert first.json()["items"][1]["location"] == "理科教学楼 101"
    assert first.json()["items"][1]["location_resolution"]["room"] == "101"


@pytest.mark.anyio
async def test_map_activity_rejects_naive_time(client: httpx.AsyncClient) -> None:
    response = await client.get("/locations/activities", params={"as_of": "2026-11-11T10:00:00"})
    assert response.status_code == 422


@pytest.mark.anyio
async def test_map_activity_window_includes_today_and_next_two_beijing_dates(
    client: httpx.AsyncClient, database: Database
) -> None:
    with database.session_factory() as session:
        InformationAggregator(session).ingest(
            [
                InformationInput(
                    platform="manual",
                    source_id=f"window-{index}",
                    title=f"日期 {index}",
                    content="公开活动正文",
                    fetched_at=f"2026-11-11T0{index}:00:00+08:00",
                    activity_location="理科教学楼 101",
                    activity_start_at=start,
                )
                for index, start in [
                    (1, "2026-11-11T14:00:00+08:00"),
                    (2, "2026-11-12T14:00:00+08:00"),
                    (3, "2026-11-13T23:59:00+08:00"),
                    (4, "2026-11-14T00:00:00+08:00"),
                ]
            ]
        )
    response = await client.get(
        "/locations/activities", params={"as_of": "2026-11-11T10:00:00+08:00"}
    )
    assert response.status_code == 200
    assert {item["title"] for item in response.json()["items"]} == {"日期 1", "日期 2", "日期 3"}


@pytest.mark.anyio
async def test_server_resolves_alias_filters_before_paging_and_ranks_buildings(client, database):
    from datetime import UTC, datetime

    from app.db.models import MapPlaceRecord

    with database.session_factory() as session:
        InformationAggregator(session).ingest(
            [
                InformationInput(
                    platform="manual",
                    source_id=str(i),
                    title=title,
                    content="测试公开活动",
                    fetched_at=f"2026-11-11T0{i}:00:00+08:00",
                    activity_location=location,
                    activity_start_at=start,
                )
                for i, title, location, start in [
                    (1, "较晚数据课", "图书馆培训教室208", "2026-11-12T15:00:00+08:00"),
                    (2, "最早数据课", "图书馆 101", "2026-11-11T15:00:00+08:00"),
                    (3, "远处活动", "百讲", "2026-11-11T12:00:00+08:00"),
                    (4, "歧义数据课", "教学楼106", "2026-11-11T11:00:00+08:00"),
                ]
            ]
        )
    with database.session_factory() as session:
        place = session.get(MapPlaceRecord, "pku:yanyuan:library")
        params = dict(
            latitude=place.latitude,
            longitude=place.longitude,
            radius_m=100,
            timestamp=datetime.now(UTC).timestamp() * 1000,
            as_of="2026-11-11T10:00:00+08:00",
            keyword="数据",
            limit=1,
        )
    first = await client.get("/locations/activities", params=params)
    assert first.status_code == 200, first.text
    body = first.json()
    assert [i["title"] for i in body["items"]] == ["最早数据课"]
    assert body["items"][0]["distance_m"] < 0.01
    assert body["items"][0]["place"]["building_id"] == "r3249649"
    assert body["nearby_buildings"][0]["place"]["id"] == "pku:yanyuan:library"
    assert all(b["distance_m"] <= 100 for b in body["nearby_buildings"])
    second = await client.get("/locations/activities", params={**params, "offset": 1})
    assert second.json()["items"][0]["title"] == "较晚数据课"
    assert second.json()["nearby_buildings"] == body["nearby_buildings"]
    assert second.json()["items"][0]["location_resolution"]["room"] == "208"
    empty = await client.get("/locations/activities", params={**params, "keyword": "不会匹配"})
    assert empty.json()["items"] == []
    assert empty.json()["nearby_buildings"]  # empty buildings still fill the section
    assert all(b["first_activity_at"] is None for b in empty.json()["nearby_buildings"])


@pytest.mark.anyio
@pytest.mark.parametrize(
    "params",
    [
        {"latitude": 39.99},
        {"latitude": 39.99, "longitude": 116.3, "radius_m": 100},
        {"latitude": 39.99, "longitude": 116.3, "radius_m": 100, "timestamp": 0},
        {"latitude": 99, "longitude": 116.3, "radius_m": 100, "timestamp": 0},
        {"as_of": "2026-11-12T00:00:00Z", "activity_before": "2026-11-11T00:00:00Z"},
    ],
)
async def test_invalid_or_stale_map_queries(client, params):
    assert (await client.get("/locations/activities", params=params)).status_code == 422


def test_catalog_backfill_is_idempotent_and_preserves_manual_coordinates(database):
    from datetime import UTC, datetime
    from uuid import uuid4

    from sqlalchemy import func, select

    from app.db.models import InformationRecord, MapPlaceRecord, PlaceAliasRecord
    from app.services.content.catalog import backfill_locations

    with database.session_factory.begin() as session:
        place = session.get(MapPlaceRecord, "pku:yanyuan:library")
        place.latitude = 39.9901
        now = datetime.now(UTC)
        session.add(
            InformationRecord(
                id=uuid4(),
                platform="manual",
                source_id="old",
                title="已有活动",
                content="旧记录",
                raw_content="旧记录",
                raw_payload={},
                activity_location="图书馆208",
                fetched_at=now,
                first_fetched_at=now,
                processed_at=now,
            )
        )
    with database.session_factory.begin() as session:
        before = session.scalar(select(func.count()).select_from(PlaceAliasRecord))
        register_places(session)
        assert backfill_locations(session) == 1
        session.flush()
        assert backfill_locations(session) == 0
        assert session.scalar(select(func.count()).select_from(PlaceAliasRecord)) == before
        assert session.get(MapPlaceRecord, "pku:yanyuan:library").latitude == 39.9901
        record = session.scalar(
            select(InformationRecord).where(InformationRecord.source_id == "old")
        )
        assert record.place_id == "pku:yanyuan:library"
        assert record.location_resolution["room"] == "208"
