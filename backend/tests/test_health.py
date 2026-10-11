import httpx
import pytest
from sqlalchemy.exc import OperationalError

from app.db.session import Database
from app.main import app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client() -> httpx.AsyncClient:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as test_client:
        yield test_client


@pytest.mark.anyio
async def test_unknown_path_returns_not_found(client: httpx.AsyncClient) -> None:
    response = await client.get("/not-found")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


@pytest.mark.anyio
async def test_live_health_does_not_require_database(client: httpx.AsyncClient) -> None:
    response = await client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": None}


@pytest.mark.anyio
async def test_ready_reports_unconfigured_database(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(app.state, "database", Database(None))

    response = await client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "database": "not_configured"}


@pytest.mark.anyio
async def test_ready_checks_database_connection(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = Database("sqlite+pysqlite:///:memory:")
    monkeypatch.setattr(app.state, "database", database)

    try:
        response = await client.get("/health/ready")
    finally:
        database.close()

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected"}


@pytest.mark.anyio
async def test_ready_hides_database_connection_errors(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = Database("sqlite+pysqlite:///:memory:")

    def fail_connection() -> None:
        raise OperationalError("SELECT 1", {}, RuntimeError("private connection detail"))

    monkeypatch.setattr(database, "check_connection", fail_connection)
    monkeypatch.setattr(app.state, "database", database)

    try:
        response = await client.get("/health/ready")
    finally:
        database.close()

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "database": "unavailable"}
