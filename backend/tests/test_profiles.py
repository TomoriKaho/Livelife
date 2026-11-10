from pathlib import Path

import httpx
import pytest

from app.db.models import Base
from app.db.session import Database
from app.main import app

AUTH = {"Authorization": "Bearer test-token-profile"}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client() -> httpx.AsyncClient:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as test_client:
        yield test_client


@pytest.fixture
def configured_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Database:
    database = Database(f"sqlite+pysqlite:///{tmp_path / 'profiles.db'}")
    Base.metadata.create_all(database.engine)
    monkeypatch.setattr(app.state, "database", database)
    yield database
    database.close()


@pytest.mark.anyio
async def test_interest_catalog_is_public(
    client: httpx.AsyncClient, configured_database: Database
) -> None:
    response = await client.get("/profile/interests")

    assert response.status_code == 200
    assert {"tag": "sport", "label": "体育运动"} in response.json()


@pytest.mark.anyio
async def test_profile_requires_bearer_token(
    client: httpx.AsyncClient, configured_database: Database
) -> None:
    response = await client.get("/profile/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.anyio
async def test_profile_is_created_then_updated(
    client: httpx.AsyncClient, configured_database: Database
) -> None:
    first = await client.get("/profile/me", headers=AUTH)
    assert first.status_code == 200
    assert first.json() == {"display_name": "", "bio": "", "interests": []}

    updated = await client.patch(
        "/profile/me",
        headers=AUTH,
        json={"display_name": " 小燕 ", "bio": " 常去图书馆 ", "interests": ["film", "sport"]},
    )
    assert updated.status_code == 200
    assert updated.json() == {
        "display_name": "小燕",
        "bio": "常去图书馆",
        "interests": ["sport", "film"],
    }

    again = await client.get("/profile/me", headers=AUTH)
    assert again.json() == updated.json()


@pytest.mark.anyio
async def test_unknown_and_duplicate_tags_are_rejected(
    client: httpx.AsyncClient, configured_database: Database
) -> None:
    unknown = await client.patch("/profile/me", headers=AUTH, json={"interests": ["astrology"]})
    assert unknown.status_code == 400

    duplicated = await client.patch(
        "/profile/me", headers=AUTH, json={"interests": ["sport", "sport"]}
    )
    assert duplicated.status_code == 400


@pytest.mark.anyio
async def test_update_rejects_out_of_range_values(
    client: httpx.AsyncClient, configured_database: Database
) -> None:
    too_many = await client.patch("/profile/me", headers=AUTH, json={"interests": ["sport"] * 11})
    assert too_many.status_code == 422

    long_name = await client.patch("/profile/me", headers=AUTH, json={"display_name": "名" * 33})
    assert long_name.status_code == 422

    blank_name = await client.patch("/profile/me", headers=AUTH, json={"display_name": "   "})
    assert blank_name.status_code == 422

    long_bio = await client.patch("/profile/me", headers=AUTH, json={"bio": "字" * 201})
    assert long_bio.status_code == 422


@pytest.mark.anyio
async def test_profile_reports_missing_database(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(app.state, "database", Database(None))

    response = await client.get("/profile/me", headers=AUTH)

    assert response.status_code == 503
    assert response.json() == {"detail": "Database is not configured"}
