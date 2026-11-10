from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import AgentSettings
from app.db.models import AgentSession, InformationRecord
from app.db.session import Database
from app.main import create_app
from app.services.agent.llm import AgentModelError, stream_completion
from app.services.agent.retrieval import search_information
from app.services.agent.service import (
    AgentError,
    begin_request,
    close_session,
    create_session,
    finish_request,
    get_history,
)

BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def sessions(tmp_path: Path) -> Iterator[sessionmaker[Session]]:
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'agent.db').as_posix()}")
    config = Config(str(BACKEND / "alembic.ini"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    try:
        yield sessionmaker(engine, expire_on_commit=False)
    finally:
        engine.dispose()


def settings(**changes) -> AgentSettings:
    values = {
        "session_secret": "a-local-test-secret-that-is-not-used-in-production",
        "llm_base_url": "",
        "llm_api_key": "",
        "llm_model": "",
        "llm_timeout_seconds": 10,
        "max_output_tokens": 128,
        "max_message_chars": 40,
        "max_context_chars": 1000,
        "requests_per_minute": 5,
        "ip_requests_per_hour": 30,
        "daily_token_quota": 1000,
    }
    values.update(changes)
    return AgentSettings(**values)


def make_information(session: Session, *, title: str, content: str, published_at=None) -> None:
    now = datetime.now(UTC)
    session.add(
        InformationRecord(
            id=uuid4(),
            platform="public",
            source_id=title,
            source_url="https://example.test/source",
            title=title,
            content=content,
            raw_content=content,
            raw_payload={},
            fetched_at=now,
            first_fetched_at=now,
            processed_at=now,
            published_at=published_at,
            activity_location=None,
            activity_start_at=None,
            activity_end_at=None,
            registration_deadline_at=None,
        )
    )


def make_api_app(tmp_path: Path, monkeypatch, *, model: bool = False) -> tuple[FastAPI, Database]:
    monkeypatch.setenv("AGENT_SESSION_SECRET", "test-only-session-hmac-secret")
    if model:
        monkeypatch.setenv("AGENT_LLM_BASE_URL", "https://llm.example.test/v1")
        monkeypatch.setenv("AGENT_LLM_API_KEY", "test-key")
        monkeypatch.setenv("AGENT_LLM_MODEL", "test-model")
    else:
        monkeypatch.delenv("AGENT_LLM_BASE_URL", raising=False)
        monkeypatch.delenv("AGENT_LLM_API_KEY", raising=False)
        monkeypatch.delenv("AGENT_LLM_MODEL", raising=False)
    app = create_app()
    database = Database(f"sqlite+pysqlite:///{(tmp_path / 'api.db').as_posix()}")
    app.state.database = database
    config = Config(str(BACKEND / "alembic.ini"))
    with database.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    return app, database


def test_session_token_is_hashed_and_history_is_private(sessions):
    config = settings()
    first = create_session(sessions, config, "127.0.0.1")
    second = create_session(sessions, config, "127.0.0.1")

    assert first["session_token"] != second["session_token"]
    with sessions() as session, session.begin():
        stored = session.scalar(select(AgentSession).where(AgentSession.id == first["session_id"]))
        assert first["session_token"] not in stored.token_hash
        stored.messages = [
            {
                "id": str(uuid4()),
                "role": "user",
                "content": "仅属于首个会话",
                "status": "completed",
                "citations": [],
                "created_at": datetime.now(UTC).isoformat(),
            }
        ]
    assert (
        get_history(sessions, config, first["session_token"])["messages"][0]["content"]
        == "仅属于首个会话"
    )
    assert get_history(sessions, config, second["session_token"])["messages"] == []


def test_request_length_rate_limit_and_active_lease(sessions):
    config = settings(requests_per_minute=1, max_message_chars=10)
    created = create_session(sessions, config, "127.0.0.1")
    with pytest.raises(AgentError, match="message_too_long"):
        begin_request(
            sessions,
            config,
            token=created["session_token"],
            content="x" * 11,
            client_request_id=uuid4(),
            ip="127.0.0.1",
        )

    request_id = uuid4()
    begin_request(
        sessions,
        config,
        token=created["session_token"],
        content="问题",
        client_request_id=request_id,
        ip="127.0.0.1",
    )
    with pytest.raises(AgentError, match="session_request_in_progress"):
        begin_request(
            sessions,
            config,
            token=created["session_token"],
            content="另一个问题",
            client_request_id=uuid4(),
            ip="127.0.0.1",
        )
    finish_request(
        sessions,
        config,
        token=created["session_token"],
        request_id=str(request_id),
        answer="无资料",
        status="completed",
        input_tokens=0,
        output_tokens=0,
        estimated_usage=True,
    )
    with pytest.raises(AgentError, match="session_rate_limited"):
        begin_request(
            sessions,
            config,
            token=created["session_token"],
            content="第三问",
            client_request_id=uuid4(),
            ip="127.0.0.1",
        )


def test_ip_limit_is_shared_across_sessions(sessions):
    config = settings(ip_requests_per_hour=3)
    first = create_session(sessions, config, "127.0.0.1")
    second = create_session(sessions, config, "127.0.0.1")
    request_id = uuid4()
    begin_request(
        sessions,
        config,
        token=first["session_token"],
        content="问题",
        client_request_id=request_id,
        ip="127.0.0.1",
    )
    finish_request(
        sessions,
        config,
        token=first["session_token"],
        request_id=str(request_id),
        answer="无资料",
        status="completed",
        input_tokens=0,
        output_tokens=0,
        estimated_usage=True,
    )
    with pytest.raises(AgentError, match="ip_rate_limited"):
        begin_request(
            sessions,
            config,
            token=second["session_token"],
            content="问题",
            client_request_id=uuid4(),
            ip="127.0.0.1",
        )


def test_chinese_information_retrieval_prefers_title_matches(sessions):
    with sessions() as session, session.begin():
        make_information(session, title="百讲活动安排", content="百周年纪念讲堂活动。")
        make_information(session, title="其他校园消息", content="百讲附近的校园信息。")
    with sessions() as session:
        results = search_information(session, "百讲活动")
    assert len(results) == 2
    assert results[0].title == "百讲活动安排"
    assert results[0].citation(1)["source_url"] == "https://example.test/source"


class _FakeStreamResponse:
    def __init__(self, lines=(), *, status_code=200, enter_error=None):
        self.lines = lines
        self.status_code = status_code
        self.enter_error = enter_error

    async def __aenter__(self):
        if self.enter_error:
            raise self.enter_error
        return self

    async def __aexit__(self, *_args):
        return None

    async def aiter_lines(self):
        for line in self.lines:
            yield line


class _FakeAsyncClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    def stream(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.response


@pytest.mark.anyio
async def test_model_stream_parses_text_and_usage(monkeypatch):
    fake = _FakeAsyncClient(
        _FakeStreamResponse(
            [
                'data: {"choices":[{"delta":{"content":"你好"}}]}',
                'data: {"choices":[{"delta":{"content":"，校园"}}]}',
                'data: {"choices":[],"usage":{"prompt_tokens":3,"completion_tokens":2}}',
                "data: [DONE]",
            ]
        )
    )
    monkeypatch.setattr("app.services.agent.llm.httpx.AsyncClient", lambda **_kwargs: fake)

    values = [
        value
        async for value in stream_completion(
            settings(
                llm_base_url="https://llm.example.test/v1",
                llm_api_key="test-key",
                llm_model="test-model",
            ),
            history=[],
            sources=(),
        )
    ]

    assert values == [
        ("你好", None),
        ("，校园", None),
        (None, {"input_tokens": 3, "output_tokens": 2}),
    ]
    assert fake.calls[0][0:2] == ("POST", "https://llm.example.test/v1/chat/completions")
    assert fake.calls[0][2]["json"]["stream"] is True


@pytest.mark.anyio
async def test_model_stream_sanitizes_timeout_and_http_failure(monkeypatch):
    timeout_client = _FakeAsyncClient(
        _FakeStreamResponse(enter_error=httpx.ReadTimeout("timed out"))
    )
    monkeypatch.setattr(
        "app.services.agent.llm.httpx.AsyncClient", lambda **_kwargs: timeout_client
    )
    with pytest.raises(AgentModelError, match="model_timeout"):
        async for _ in stream_completion(
            settings(llm_base_url="https://llm.example.test", llm_api_key="key", llm_model="m"),
            history=[],
            sources=(),
        ):
            pass

    failure_client = _FakeAsyncClient(_FakeStreamResponse(status_code=502))
    monkeypatch.setattr(
        "app.services.agent.llm.httpx.AsyncClient", lambda **_kwargs: failure_client
    )
    with pytest.raises(AgentModelError, match="model_unavailable"):
        async for _ in stream_completion(
            settings(llm_base_url="https://llm.example.test", llm_api_key="key", llm_model="m"),
            history=[],
            sources=(),
        ):
            pass


def test_close_session_deletes_only_that_session(sessions):
    config = settings()
    first = create_session(sessions, config, "127.0.0.1")
    second = create_session(sessions, config, "127.0.0.1")
    close_session(sessions, config, first["session_token"])
    with pytest.raises(AgentError, match="invalid_session"):
        get_history(sessions, config, first["session_token"])
    assert get_history(sessions, config, second["session_token"])["messages"] == []


def test_expired_session_is_removed_on_access(sessions):
    config = settings()
    created = create_session(sessions, config, "127.0.0.1")
    with sessions() as session, session.begin():
        row = session.scalar(select(AgentSession).where(AgentSession.id == created["session_id"]))
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)

    with pytest.raises(AgentError, match="session_expired"):
        get_history(sessions, config, created["session_token"])


@pytest.mark.anyio
async def test_http_session_and_no_source_sse_flow(tmp_path, monkeypatch):
    app, database = make_api_app(tmp_path, monkeypatch)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            created = await client.post("/agent/sessions")
            assert created.status_code == 201
            session = created.json()
            headers = {"Authorization": f"Bearer {session['session_token']}"}
            response = await client.post(
                "/agent/messages/stream",
                headers=headers,
                json={"content": "没有资料的问题", "client_request_id": str(uuid4())},
            )
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            assert "event: delta" in response.text
            assert "我目前没有找到足够的公开资料来回答这个问题。" in response.text
            assert "event: done" in response.text

            current = await client.get("/agent/sessions/current", headers=headers)
            assert current.status_code == 200
            messages = current.json()["messages"]
            assert [message["role"] for message in messages] == ["user", "assistant"]
            assert messages[-1]["status"] == "completed"
            assert messages[-1]["citations"] == []
    finally:
        database.close()


@pytest.mark.anyio
async def test_http_model_sse_persists_citations_and_usage(tmp_path, monkeypatch):
    app, database = make_api_app(tmp_path, monkeypatch, model=True)
    try:
        with database.session_factory() as session, session.begin():
            make_information(session, title="百讲活动安排", content="今天有公开讲座。")

        async def fake_completion(_settings, *, history, sources):
            assert history[-1]["role"] == "user"
            assert sources[0].title == "百讲活动安排"
            yield "今天有", None
            yield "公开讲座。", None
            yield None, {"input_tokens": 12, "output_tokens": 5}

        monkeypatch.setattr("app.api.agent.router.stream_completion", fake_completion)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            created = await client.post("/agent/sessions")
            headers = {"Authorization": f"Bearer {created.json()['session_token']}"}
            response = await client.post(
                "/agent/messages/stream",
                headers=headers,
                json={"content": "百讲活动", "client_request_id": str(uuid4())},
            )
            assert response.status_code == 200
            assert "event: citation" in response.text
            assert '"text":"今天有"' in response.text
            assert '"input_tokens":12' in response.text
            assert "event: done" in response.text

            current = await client.get("/agent/sessions/current", headers=headers)
            assistant = current.json()["messages"][-1]
            assert assistant["status"] == "completed"
            assert assistant["content"] == "今天有公开讲座。"
            assert assistant["citations"][0]["title"] == "百讲活动安排"
    finally:
        database.close()


@pytest.mark.anyio
async def test_http_model_failure_emits_retryable_error_and_marks_message_failed(
    tmp_path, monkeypatch
):
    app, database = make_api_app(tmp_path, monkeypatch, model=True)
    try:
        with database.session_factory() as session, session.begin():
            make_information(session, title="百讲活动安排", content="今天有公开讲座。")

        async def broken_completion(*_args, **_kwargs):
            raise AgentModelError("model_timeout")
            yield  # pragma: no cover

        monkeypatch.setattr("app.api.agent.router.stream_completion", broken_completion)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            created = await client.post("/agent/sessions")
            headers = {"Authorization": f"Bearer {created.json()['session_token']}"}
            response = await client.post(
                "/agent/messages/stream",
                headers=headers,
                json={"content": "百讲活动", "client_request_id": str(uuid4())},
            )
            assert response.status_code == 200
            assert '"code":"model_timeout"' in response.text
            assert '"retryable":true' in response.text
            assert "event: done" not in response.text

            current = await client.get("/agent/sessions/current", headers=headers)
            assert current.json()["messages"][-1]["status"] == "failed"
    finally:
        database.close()
