"""个人资料接口测试：使用账户模块签发的真实会话令牌。"""

from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models.accounts import User
from app.db.session import Database
from app.main import app
from app.services.accounts.auth import create_session, get_test_user, utcnow

BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Database]:
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'profiles.db').as_posix()}")
    config = Config(str(BACKEND / "alembic.ini"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    database = Database.__new__(Database)
    database.engine = engine
    database.session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(app.state, "database", database)
    yield database
    database.close()


@pytest.fixture
async def client(database: Database) -> Iterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as value:
        yield value


def auth_headers(database: Database) -> dict[str, str]:
    """创建内置测试用户并签发真实会话令牌。"""

    with database.session_factory() as session:
        user = get_test_user(session)
        token, _expires_in = create_session(session, user, False)
    return {"Authorization": f"Bearer {token}"}


def second_user_headers(database: Database) -> dict[str, str]:
    """另建一个普通用户，用于验证资料按用户隔离。"""

    with database.session_factory() as session:
        other = User(
            id=uuid4(),
            email="other@pku.edu.cn",
            password_hash="!test-account-no-password",
            created_at=utcnow(),
        )
        session.add(other)
        token, _expires_in = create_session(session, other, False)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.anyio
async def test_interest_catalog_is_public(client: httpx.AsyncClient) -> None:
    response = await client.get("/profile/interests")

    assert response.status_code == 200
    assert {"tag": "sport", "label": "体育运动"} in response.json()


@pytest.mark.anyio
async def test_profile_requires_bearer_token(client: httpx.AsyncClient) -> None:
    response = await client.get("/profile/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.anyio
async def test_profile_is_created_then_updated(
    client: httpx.AsyncClient, database: Database
) -> None:
    headers = auth_headers(database)
    first = await client.get("/profile/me", headers=headers)
    assert first.status_code == 200
    assert first.json() == {"display_name": "", "bio": "", "interests": []}
    assert first.headers["cache-control"] == "no-store"

    updated = await client.patch(
        "/profile/me",
        headers=headers,
        json={"display_name": " 小燕 ", "bio": " 常去图书馆 ", "interests": ["film", "sport"]},
    )
    assert updated.status_code == 200
    assert updated.json() == {
        "display_name": "小燕",
        "bio": "常去图书馆",
        "interests": ["sport", "film"],
    }

    again = await client.get("/profile/me", headers=headers)
    assert again.json() == updated.json()


@pytest.mark.anyio
async def test_profiles_are_isolated_between_users(
    client: httpx.AsyncClient, database: Database
) -> None:
    mine = auth_headers(database)
    assert (
        await client.patch("/profile/me", headers=mine, json={"display_name": "甲"})
    ).status_code == 200

    theirs = second_user_headers(database)
    assert (await client.get("/profile/me", headers=theirs)).json()["display_name"] == ""
    assert (await client.get("/profile/me", headers=mine)).json()["display_name"] == "甲"


@pytest.mark.anyio
async def test_unknown_and_duplicate_tags_are_rejected(
    client: httpx.AsyncClient, database: Database
) -> None:
    headers = auth_headers(database)
    unknown = await client.patch("/profile/me", headers=headers, json={"interests": ["astrology"]})
    assert unknown.status_code == 400

    duplicated = await client.patch(
        "/profile/me", headers=headers, json={"interests": ["sport", "sport"]}
    )
    assert duplicated.status_code == 400


@pytest.mark.anyio
async def test_update_rejects_out_of_range_values(
    client: httpx.AsyncClient, database: Database
) -> None:
    headers = auth_headers(database)
    too_many = await client.patch(
        "/profile/me", headers=headers, json={"interests": ["sport"] * 11}
    )
    assert too_many.status_code == 422

    long_name = await client.patch("/profile/me", headers=headers, json={"display_name": "名" * 33})
    assert long_name.status_code == 422

    blank_name = await client.patch("/profile/me", headers=headers, json={"display_name": "   "})
    assert blank_name.status_code == 422

    long_bio = await client.patch("/profile/me", headers=headers, json={"bio": "字" * 201})
    assert long_bio.status_code == 422


@pytest.mark.anyio
async def test_profile_reports_missing_database(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(app.state, "database", Database(None))

    response = await client.get("/profile/me")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database is not configured"}
