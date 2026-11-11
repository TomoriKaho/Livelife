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
    assert [item["title"] for item in first.json()["items"]] == ["活动 3"]

    second = await client.get("/locations/activities", params={**params, "offset": 2})
    assert second.status_code == 200
    assert second.json()["next_offset"] is None
    assert [item["title"] for item in second.json()["items"]] == ["活动 1"]
    assert second.json()["items"][0]["location"] == "理科教学楼 101"


@pytest.mark.anyio
async def test_map_activity_rejects_naive_time(client: httpx.AsyncClient) -> None:
    response = await client.get("/locations/activities", params={"as_of": "2026-11-11T10:00:00"})
    assert response.status_code == 422
