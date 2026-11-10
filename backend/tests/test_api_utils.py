from collections.abc import Callable

import httpx
import pytest

from app.utils.api import api_request, api_stream


@pytest.fixture
def client_factory() -> tuple[Callable[..., httpx.AsyncClient], list[httpx.Request]]:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"method": request.method, "path": request.url.path})

    transport = httpx.MockTransport(respond)

    def factory(**kwargs: object) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=transport, **kwargs)

    return factory, requests


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_api_request_passes_through_arbitrary_request_options(client_factory) -> None:
    factory, requests = client_factory

    response = await api_request(
        "PATCH",
        "https://example.test/items/7",
        client_factory=factory,
        params={"verbose": "true"},
        headers={"X-Caller": "test"},
        json={"enabled": True},
    )

    assert response.json() == {"method": "PATCH", "path": "/items/7"}
    assert requests[0].url.params["verbose"] == "true"
    assert requests[0].headers["X-Caller"] == "test"
    assert requests[0].read() == b'{"enabled":true}'


@pytest.mark.anyio
async def test_api_stream_yields_response_for_incremental_reads() -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, content=b"one\ntwo\n")

    transport = httpx.MockTransport(respond)

    def factory(**kwargs: object) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=transport, **kwargs)

    async with api_stream("GET", "https://example.test/events", client_factory=factory) as response:
        lines = [line async for line in response.aiter_lines()]

    assert lines == ["one", "two"]
    assert requests[0].url.path == "/events"
