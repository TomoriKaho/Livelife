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
from app.services.content.feed import excerpt


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def database(tmp_path, monkeypatch) -> Iterator[Database]:
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'feed.db').as_posix()}")
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    db = Database.__new__(Database)
    db.engine = engine
    db.session_factory = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(app.state, "database", db)
    yield db
    db.close()


@pytest.fixture
async def client(database) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


@pytest.mark.anyio
async def test_feed_pages_filters_missing_fields_and_no_private_payload(client, database):
    with database.session_factory() as session:
        records = InformationAggregator(session).ingest(
            [
                InformationInput(
                    platform="wechat" if index < 3 else "manual",
                    source_id=str(index),
                    source_name="图书馆" if index < 2 else None,
                    title="校园讲座" if index else None,
                    content="公开正文 & 报名 100%\nCompare a<b and c>d. Use vector<int>.",
                    source_url="https://lib.pku.edu.cn/" if index else None,
                    fetched_at="2026-11-18T12:00:00+08:00",
                    raw_payload={"private": "never expose"},
                )
                for index in range(4)
            ]
        )
    page = (await client.get("/content/articles", params={"limit": 2})).json()
    second = (await client.get("/content/articles", params={"limit": 2, "offset": 2})).json()
    assert page["next_offset"] == 2
    assert second["next_offset"] is None
    items = page["items"] + second["items"]
    assert {entry["id"] for entry in items} == {str(record.id) for record in records}
    assert all(
        entry["excerpt"] == "公开正文 & 报名 100% Compare a<b and c>d. Use vector<int>."
        for entry in items
    )
    assert all("raw_payload" not in entry and "content" not in entry for entry in items)
    assert any(entry["title"] is None and entry["source_url"] is None for entry in items)
    response = await client.get(
        "/content/articles",
        params={"keyword": "100%", "platform": "wechat", "source_name": "图书馆"},
    )
    assert response.status_code == 200
    assert len(response.json()["items"]) == 2
    assert response.headers["cache-control"] == "no-store"
    assert (await client.get("/content/articles", params={"keyword": "100_"})).json()["items"] == []
    assert (await client.get("/content/articles", params={"source_name": "图书"})).json()[
        "items"
    ] == []


@pytest.mark.anyio
async def test_empty_validation_and_database_disabled(client, database):
    assert (await client.get("/content/articles")).json() == {"items": [], "next_offset": None}
    for params in ({"limit": 51}, {"offset": -1}, {"platform": "invalid!"}, {"tag": "demo"}):
        assert (await client.get("/content/articles", params=params)).status_code == 422
    database.session_factory = None
    assert (await client.get("/content/articles")).status_code == 503


def test_excerpt_is_bounded_plain_text():
    assert excerpt("  hello\n\tworld  ") == "hello world"
    assert excerpt(" \n\t ") == ""
    assert excerpt("文" * 300) == "文" * 300
    assert excerpt("文" * 301) == "文" * 300 + "…"


@pytest.mark.parametrize(
    "content",
    [
        "Compare a<b and c>d.",
        "Use vector<int> and std::map<K,V>.",
        "Literal &lt;script&gt;hello&lt;/script&gt; &amp; remains text.",
        "<script>alert('literal example')</script>",
        "<style>literal example</style>",
        "<img src='x' onerror='example()'>",
    ],
)
def test_excerpt_preserves_plain_text_syntax(content):
    assert excerpt(content) == content
