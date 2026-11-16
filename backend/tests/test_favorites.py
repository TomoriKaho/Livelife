"""Account isolation, durable bookmarks, strict time semantics and migrations."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, delete, func, inspect, select
from sqlalchemy.orm import sessionmaker

from app.db.models import ActivityFavorite, InformationRecord, User, UserSession
from app.db.session import Database
from app.main import app
from app.schemas.information import InformationInput
from app.services.accounts.auth import create_session, password_hash, utcnow
from app.services.content.aggregation import InformationAggregator
from app.services.favorites.service import list_favorites, remove_favorite, save_favorite, status_at

BACKEND = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 11, 16, 8, tzinfo=UTC)


@pytest.fixture
def anyio_backend():
    return "asyncio"


def migrate(engine, target="head"):
    config = Config(str(BACKEND / "alembic.ini"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, target)


@pytest.fixture
def database(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'favorites.db').as_posix()}")
    migrate(engine)
    db = Database.__new__(Database)
    db.engine = engine
    db.session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(app.state, "database", db)
    yield db
    db.close()


@pytest.fixture
async def client(database):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


def account(db):
    with db.session_factory() as session:
        user = User(
            id=uuid4(),
            email=f"{uuid4().hex}@pku.edu.cn",
            password_hash=password_hash("test-password-100"),
            created_at=utcnow(),
        )
        session.add(user)
        session.flush()
        token, _ = create_session(session, user, False)
        return user.id, {"Authorization": f"Bearer {token}"}


def activity(db, **changes):
    data = dict(
        platform="pku",
        source_id=uuid4().hex,
        title="收藏测试讲座",
        content="原文正文不得复制到收藏表",
        fetched_at=NOW,
        source_url="https://example.com/lecture",
        source_name="公开官网",
        activity_date=date(2026, 11, 16),
        activity_start_at=NOW,
        activity_end_at=NOW + timedelta(hours=1),
        activity_location="图书馆",
    )
    data.update(changes)
    with db.session_factory() as session:
        return InformationAggregator(session).ingest([InformationInput(**data)])[0].id


@pytest.mark.anyio
async def test_bookmark_is_idempotent_persistent_and_account_owned(client, database):
    owner, headers = account(database)
    _, other = account(database)
    target = activity(database)
    url = f"/favorites/activities/{target}"
    first = await client.put(url, headers=headers)
    assert first.status_code == 200, first.text
    assert (await client.put(url, headers=headers)).json() == first.json()
    assert first.headers["cache-control"] == "no-store"
    assert (await client.get("/favorites/activities", headers=other)).json()["total"] == 0
    assert (await client.get(url, headers=other)).status_code == 404
    assert (await client.delete(url, headers=other)).status_code == 204
    assert (await client.get(url, headers=headers)).status_code == 200
    with database.session_factory() as session:
        user = session.get(User, owner)
        token, _ = create_session(session, user, False)
        assert session.scalar(select(func.count()).select_from(ActivityFavorite)) == 1
    # A distinct login credential, like another device, restores the same history.
    restored = await client.get(
        "/favorites/activities", headers={"Authorization": f"Bearer {token}"}
    )
    assert restored.json()["items"][0]["id"] == str(target)
    status = await client.post(
        "/favorites/activities/status", headers=headers, json={"ids": [str(target), str(uuid4())]}
    )
    assert status.json() == {"saved_ids": [str(target)]}
    for _ in range(2):
        assert (await client.delete(url, headers=headers)).status_code == 204
    assert (await client.get("/favorites/activities", headers=headers)).json()["total"] == 0


@pytest.mark.anyio
async def test_current_fields_and_cleanup_preserve_minimal_snapshot(client, database):
    _, headers = account(database)
    target = activity(database)
    url = f"/favorites/activities/{target}"
    original = (await client.put(url, headers=headers)).json()
    with database.session_factory() as session:
        source = session.get(InformationRecord, target)
        source.title = "改期后的标题"
        source.activity_start_at = None
        source.activity_end_at = None
        session.commit()
    live = (await client.get(url, headers=headers)).json()
    assert live["title"] == "改期后的标题"
    assert live["start_at"] is None and live["end_at"] is None and live["status"] == "unknown"
    assert (await client.get("/favorites/activities?status=unknown", headers=headers)).json()[
        "total"
    ] == 1
    with database.session_factory() as session:
        session.execute(delete(InformationRecord).where(InformationRecord.id == target))
        session.commit()
        snapshot = session.scalar(select(ActivityFavorite))
        assert snapshot.title == original["title"]
        assert not {"content", "raw_content", "raw_payload", "location"} & set(
            snapshot.__table__.columns.keys()
        )
    missing = (await client.get(url, headers=headers)).json()
    assert missing["available"] is False and missing["title"] == original["title"]
    assert missing["location"] is None and missing["place"] is None
    assert (await client.put(url, headers=headers)).status_code == 200
    assert (await client.delete(url, headers=headers)).status_code == 204
    assert (await client.put(url, headers=headers)).status_code == 404


@pytest.mark.anyio
async def test_invalid_targets_authentication_and_parameters(client, database):
    owner, headers = account(database)
    target = activity(database)
    article = activity(database, activity_date=None, activity_start_at=None, activity_end_at=None)
    demo = activity(database, platform="demo")
    for value in [uuid4(), article, demo]:
        assert (
            await client.put(f"/favorites/activities/{value}", headers=headers)
        ).status_code == 404
    assert (await client.put("/favorites/activities/film", headers=headers)).status_code == 422
    for method, path, payload in [
        ("GET", "", None),
        ("POST", "/status", {"ids": []}),
        ("PUT", f"/{target}", None),
        ("DELETE", f"/{target}", None),
    ]:
        response = await client.request(method, f"/favorites/activities{path}", json=payload)
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"
    for query in ["limit=101", "offset=-1", "status=bad", "as_of=2026-11-16T08:00:00"]:
        assert (
            await client.get(f"/favorites/activities?{query}", headers=headers)
        ).status_code == 422
    assert (
        await client.post(
            "/favorites/activities/status", headers=headers, json={"ids": [str(target)] * 101}
        )
    ).status_code == 422
    assert (
        await client.post(
            "/favorites/activities/status", headers=headers, json={"ids": [], "user_id": str(owner)}
        )
    ).status_code == 422
    with database.session_factory() as session:
        login = session.scalar(select(UserSession).where(UserSession.user_id == owner))
        login.expires_at = utcnow() - timedelta(seconds=1)
        session.commit()
    assert (await client.get("/favorites/activities", headers=headers)).status_code == 401


@pytest.mark.anyio
async def test_pagination_and_time_boundaries(client, database):
    _, headers = account(database)
    for i in range(24):
        target = activity(database, title=f"活动{i}")
        await client.put(f"/favorites/activities/{target}", headers=headers)
    point = activity(database, activity_end_at=None)
    unknown = activity(database, activity_start_at=None, activity_end_at=None)
    for target in (point, unknown):
        await client.put(f"/favorites/activities/{target}", headers=headers)
    query = {"as_of": NOW.isoformat(), "limit": 20}
    first = (await client.get("/favorites/activities", headers=headers, params=query)).json()
    second = (
        await client.get(
            "/favorites/activities",
            headers=headers,
            params={**query, "offset": first["next_offset"]},
        )
    ).json()
    assert len(first["items"]) == 20 and len(second["items"]) == 6 and second["next_offset"] is None
    assert len({item["id"] for item in first["items"] + second["items"]}) == 26
    assert first["counts"] == {"upcoming": 0, "ongoing": 24, "ended": 1, "unknown": 1}
    for instant, status in [
        (NOW - timedelta(microseconds=1), "upcoming"),
        (NOW, "ongoing"),
        (NOW + timedelta(hours=1), "ended"),
    ]:
        page = (
            await client.get(
                "/favorites/activities",
                headers=headers,
                params={"status": status, "as_of": instant.isoformat()},
            )
        ).json()
        assert page["counts"][status] >= 24
        assert all(item["status"] == status for item in page["items"])
    assert status_at(None, NOW, NOW) == "unknown"
    assert status_at(NOW, None, NOW) == "ended"


@pytest.mark.anyio
async def test_logout_and_deletion_cleanup(client, database):
    owner, headers = account(database)
    target = activity(database)
    await client.put(f"/favorites/activities/{target}", headers=headers)
    assert (await client.post("/auth/logout", headers=headers)).status_code == 204
    assert (await client.get("/favorites/activities", headers=headers)).status_code == 401
    with database.session_factory() as session:
        token, _ = create_session(session, session.get(User, owner), False)
    headers = {"Authorization": f"Bearer {token}"}
    response = await client.request(
        "DELETE", "/auth/me", headers=headers, json={"password": "test-password-100"}
    )
    assert response.status_code == 204, response.text
    with database.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ActivityFavorite)) == 0
        assert session.get(InformationRecord, target) is not None


def test_migration_downgrade_only_removes_favorites(database):
    owner, _ = account(database)
    target = activity(database)
    with database.session_factory() as session:
        save_favorite(session, owner, target)
    migrate(database.engine)
    with database.session_factory() as session:
        assert session.get(ActivityFavorite, (owner, target)) is not None
    config = Config(str(BACKEND / "alembic.ini"))
    with database.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "0003_place_resolution")
    assert "activity_favorites" not in inspect(database.engine).get_table_names()
    with database.session_factory() as session:
        assert session.get(User, owner) is not None
        assert session.get(InformationRecord, target) is not None
    migrate(database.engine)


def test_postgres_concurrent_idempotence_and_cleanup(tmp_path, request):
    if not request.config.getoption("--local-postgres"):
        pytest.skip("Enable --local-postgres for real database concurrency")
    from app.db.local import local_database

    with local_database(tmp_path / "postgres") as url:
        db = Database(url)
        try:
            owner, _ = account(db)
            target = activity(db)

            def save(_):
                with db.session_factory() as session:
                    return save_favorite(session, owner, target).id

            with ThreadPoolExecutor(max_workers=4) as executor:
                assert list(executor.map(save, range(8))) == [target] * 8
            with db.session_factory() as session:
                assert list_favorites(session, owner, None, 20, 0, NOW).total == 1
                session.execute(delete(InformationRecord).where(InformationRecord.id == target))
                session.commit()
                page = list_favorites(session, owner, None, 20, 0, NOW)
                assert page.items[0].available is False
                remove_favorite(session, owner, target)
        finally:
            db.close()
