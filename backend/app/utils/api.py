from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

import httpx


async def api_request(
    method: str,
    url: str,
    *,
    timeout: float | httpx.Timeout | None = None,
    client_factory: Callable[..., httpx.AsyncClient] | None = None,
    **kwargs: Any,
) -> httpx.Response:
    """Send a one-shot async HTTP request with any httpx request options."""
    factory = client_factory or httpx.AsyncClient
    async with factory(timeout=timeout) as client:
        return await client.request(method, url, **kwargs)


@asynccontextmanager
async def api_stream(
    method: str,
    url: str,
    *,
    timeout: float | httpx.Timeout | None = None,
    client_factory: Callable[..., httpx.AsyncClient] | None = None,
    **kwargs: Any,
) -> AsyncIterator[httpx.Response]:
    """Open a streaming async HTTP request and yield its response."""
    factory = client_factory or httpx.AsyncClient
    async with factory(timeout=timeout) as client:
        async with client.stream(method, url, **kwargs) as response:
            yield response
