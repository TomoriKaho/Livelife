import httpx
import pytest

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
async def test_hello_returns_contract_response(client: httpx.AsyncClient) -> None:
    response = await client.get("/test/hello")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {"message": "hello world"}


@pytest.mark.parametrize(
    "origin",
    [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8765",
        "http://127.0.0.1:8765",
        "http://localhost:8766",
        "http://127.0.0.1:8766",
    ],
)
@pytest.mark.anyio
async def test_hello_allows_local_frontend_origins(
    client: httpx.AsyncClient,
    origin: str,
) -> None:
    response = await client.get("/test/hello", headers={"Origin": origin})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin


@pytest.mark.anyio
async def test_hello_does_not_allow_unlisted_origin(client: httpx.AsyncClient) -> None:
    response = await client.get(
        "/test/hello",
        headers={"Origin": "https://example.com"},
    )

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.anyio
async def test_unknown_path_returns_not_found(client: httpx.AsyncClient) -> None:
    response = await client.get("/not-found")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


@pytest.mark.anyio
async def test_unsupported_method_returns_method_not_allowed(client: httpx.AsyncClient) -> None:
    response = await client.post("/test/hello")

    assert response.status_code == 405
    assert response.json() == {"detail": "Method Not Allowed"}
