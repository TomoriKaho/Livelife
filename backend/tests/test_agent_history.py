"""Permanent, account-owned conversation API and extractive context regressions."""

import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import MetaData, Table, create_engine, func, select
from sqlalchemy.orm import sessionmaker
from test_agent import (
    ACCOUNT_ID,
    BACKEND,
    make_api_app,
    make_information,
    seed_account,
    settings,
)
from test_agent import sessions as sessions

from app.db.models import AgentMessage, AgentSession, AgentUserUsage, User, UserSession
from app.services.accounts.auth import token_digest
from app.services.agent.context import conversation_context
from app.services.agent.llm import completion_messages
from app.services.agent.service import (
    AgentError,
    begin_request,
    close_session,
    create_session,
    finish_request,
    get_conversation,
    get_history,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_permanent_paged_messages_and_deletion(sessions):
    config = settings()
    created = create_session(sessions, config, "local", user_id=ACCOUNT_ID)
    sid = str(created["session_id"])
    assert created["expires_at"] is None
    values = [
        {
            "id": str(uuid4()),
            "role": "assistant" if i % 2 else "user",
            "content": f"message {i}",
            "status": ["completed", "failed", "cancelled", "pending"][i % 4],
            "request_id": str(uuid4()),
            "citations": [],
            "rating": "like" if i == 0 else None,
            "created_at": datetime.now(UTC).isoformat(),
        }
        for i in range(63)
    ]
    with sessions() as db, db.begin():
        row = db.get(AgentSession, created["session_id"])
        row.messages = values
        row.created_at = datetime.now(UTC) - timedelta(days=365)
    recent = get_conversation(sessions, config, sid, user_id=ACCOUNT_ID, limit=20)
    assert recent["messages"] == values[-20:]
    earlier = get_conversation(
        sessions, config, sid, user_id=ACCOUNT_ID, limit=50, before=recent["next_before"]
    )
    assert earlier["messages"] + recent["messages"] == values
    assert earlier["next_before"] is None
    assert get_history(sessions, config, sid, user_id=ACCOUNT_ID)["messages"] == values
    close_session(sessions, config, sid, user_id=ACCOUNT_ID)
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(AgentMessage)) == 0
    with pytest.raises(AgentError):
        get_conversation(sessions, config, sid, user_id=ACCOUNT_ID)


def test_context_recalls_source_task_after_many_messages_and_never_persists_location(sessions):
    config = settings(max_message_chars=4000, max_context_chars=2000)
    now = datetime.now(UTC)
    with sessions() as db, db.begin():
        make_information(db, title="数据结构课程", content="主讲老师为测试教师。")
    with sessions() as db:
        info = db.scalar(
            select(__import__("app.db.models", fromlist=["InformationRecord"]).InformationRecord)
        )
    history = [
        {
            "id": str(uuid4()),
            "role": "user",
            "content": "二教101的数据结构课程",
            "status": "completed",
            "created_at": now.isoformat(),
        },
        {
            "id": str(uuid4()),
            "role": "assistant",
            "content": "历史生成文本不可作为事实",
            "status": "completed",
            "created_at": now.isoformat(),
            "citations": [{"information_id": str(info.id), "title": "数据结构课程"}],
        },
    ]
    history += [
        {
            "id": str(uuid4()),
            "role": "user",
            "content": "谢谢" + str(i),
            "status": "completed",
            "created_at": now.isoformat(),
        }
        for i in range(20)
    ]
    created = create_session(sessions, config, "local", user_id=ACCOUNT_ID)
    with sessions() as db, db.begin():
        db.get(AgentSession, created["session_id"]).messages = history
    location = {
        "latitude": 39.99,
        "longitude": 116.3,
        "accuracy": 35,
        "timestamp": now.timestamp() * 1000,
    }
    state = begin_request(
        sessions,
        config,
        token=str(created["session_id"]),
        user_id=ACCOUNT_ID,
        content="这门课的老师是谁",
        client_request_id=uuid4(),
        ip="local",
        location=location,
    )
    assert info.id in [s.id for s in state["sources"]]
    payload = completion_messages(config, history=state["history"], sources=state["sources"])
    assert any("二教101" in m["content"] for m in payload)
    assert "主讲老师" in payload[1]["content"]
    assert "<current_context>" in payload[-1]["content"]
    assert "received_at" in payload[-1]["content"]
    assert sum(len(m["content"]) for m in payload[2:]) <= config.max_context_chars // 2
    saved = get_history(sessions, config, str(created["session_id"]), user_id=ACCOUNT_ID)
    assert "latitude" not in json.dumps(saved["messages"])
    stale = {**location, "timestamp": (now - timedelta(minutes=3)).timestamp() * 1000}
    context, _, _ = conversation_context([], "你好", now, stale)
    assert "latitude" not in context[-1]["content"]
    finish_request(
        sessions,
        config,
        token=str(created["session_id"]),
        user_id=ACCOUNT_ID,
        request_id=state["assistant_message"]["request_id"],
        answer="完成",
        status="completed",
        input_tokens=1,
        output_tokens=1,
        estimated_usage=False,
    )


@pytest.mark.anyio
async def test_account_only_multidevice_api_and_isolation(tmp_path, monkeypatch):
    app, database = make_api_app(tmp_path, monkeypatch)
    now = datetime.now(UTC)
    other = uuid4()
    with database.session_factory() as db, db.begin():
        db.add(
            User(id=other, email="other@stu.pku.edu.cn", password_hash="!unused", created_at=now)
        )
        db.flush()
        for uid, token in [(ACCOUNT_ID, "second-device"), (other, "other-account")]:
            db.add(
                UserSession(
                    id=uuid4(),
                    user_id=uid,
                    token_hash=token_digest(token),
                    created_at=now,
                    expires_at=now + timedelta(days=1),
                )
            )
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": "Bearer account-test-token"},
        ) as client:
            first = (await client.post("/agent/sessions")).json()
            second = (await client.post("/agent/sessions")).json()
            sid = first["session_id"]
            mid = str(uuid4())
            reply = await client.post(
                f"/agent/sessions/{sid}/messages/stream",
                json={
                    "content": "literal%_!",
                    "client_request_id": mid,
                    "location": {
                        "latitude": 39.99,
                        "longitude": 116.3,
                        "accuracy": 35,
                        "timestamp": now.timestamp() * 1000,
                    },
                },
            )
            assert reply.status_code == 200 and "event: done" in reply.text
            restored = await client.get(
                f"/agent/sessions/{sid}", headers={"Authorization": "Bearer second-device"}
            )
            assert restored.status_code == 200
            messages = restored.json()["messages"]
            assert messages[0]["client_request_id"] == mid
            assert messages[0]["request_id"] == messages[1]["request_id"]
            assert len((await client.get("/agent/sessions")).json()["items"]) == 2
            assert (
                len((await client.get("/agent/sessions", params={"query": "%_!"})).json()["items"])
                == 1
            )
            assert (await client.get(f"/agent/sessions/{second['session_id']}")).json()[
                "messages"
            ] == []
            for method, path, kw in [
                ("GET", f"/agent/sessions/{sid}", {}),
                ("DELETE", f"/agent/sessions/{sid}", {}),
                (
                    "POST",
                    f"/agent/sessions/{sid}/messages/stream",
                    {"json": {"content": "hack", "client_request_id": str(uuid4())}},
                ),
            ]:
                response = await client.request(
                    method, path, headers={"Authorization": "Bearer other-account"}, **kw
                )
                assert response.status_code == 404
            assert (
                await client.get(
                    "/agent/sessions", headers={"Authorization": "Bearer other-account"}
                )
            ).json()["items"] == []
            message_id = messages[1]["id"]
            assert (
                await client.post(
                    f"/agent/sessions/{sid}/messages/{message_id}/rating", json={"rating": "like"}
                )
            ).status_code == 204
            assert (await client.get(f"/agent/sessions/{sid}")).json()["messages"][1][
                "rating"
            ] == "like"
            assert (await client.delete(f"/agent/sessions/{sid}")).status_code == 204
            assert (await client.get(f"/agent/sessions/{sid}")).status_code == 404
    finally:
        database.close()


def test_development_cleanup_is_once_and_preserves_budget(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'upgrade.db').as_posix()}")
    config = Config(str(BACKEND / "alembic.ini"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "0003_place_resolution")
    factory = sessionmaker(engine, expire_on_commit=False)
    seed_account(factory)
    now = datetime.now(UTC)
    old = Table("agent_sessions", MetaData(), autoload_with=engine)
    with engine.begin() as connection:
        connection.execute(
            old.insert().values(
                id=uuid4().hex,
                user_id=ACCOUNT_ID.hex,
                token_hash="a" * 64,
                messages=[],
                created_at=now,
                last_seen_at=now,
                expires_at=now + timedelta(days=1),
                request_window_start=now,
                request_count=0,
                usage_day=now.date(),
                tokens_used=0,
                tokens_reserved=0,
            )
        )
    with factory() as db, db.begin():
        db.add(
            AgentUserUsage(
                user_id=ACCOUNT_ID,
                request_window_start=now,
                request_count=0,
                usage_day=now.date(),
                tokens_used=10,
                tokens_reserved=5,
                active_request_id=str(uuid4()),
                active_request_expires_at=now + timedelta(minutes=1),
            )
        )
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(AgentSession)) == 0
        usage = db.get(AgentUserUsage, ACCOUNT_ID)
        assert (
            usage.tokens_used == 15
            and usage.tokens_reserved == 0
            and usage.active_request_id is None
        )
    created = create_session(factory, settings(), "local", user_id=ACCOUNT_ID)
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    assert (
        get_history(factory, settings(), str(created["session_id"]), user_id=ACCOUNT_ID)[
            "expires_at"
        ]
        is None
    )
    engine.dispose()


def test_expired_generation_lease_recovers_without_double_billing(sessions):
    config = settings(
        llm_base_url="https://unused.invalid/v1", llm_api_key="synthetic", llm_model="synthetic"
    )
    created = create_session(sessions, config, "local", user_id=ACCOUNT_ID)
    sid = str(created["session_id"])
    state = begin_request(
        sessions,
        config,
        token=sid,
        user_id=ACCOUNT_ID,
        content="你好",
        client_request_id=uuid4(),
        ip="local",
    )
    with pytest.raises(AgentError, match="user_request_in_progress"):
        close_session(sessions, config, sid, user_id=ACCOUNT_ID)
    with sessions() as db, db.begin():
        row = db.get(AgentSession, created["session_id"])
        row.active_request_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        usage = db.get(AgentUserUsage, ACCOUNT_ID)
        usage.active_request_expires_at = row.active_request_expires_at
        reserved = usage.tokens_reserved
    assert (
        get_conversation(sessions, config, sid, user_id=ACCOUNT_ID)["messages"][1]["status"]
        == "failed"
    )
    get_conversation(sessions, config, sid, user_id=ACCOUNT_ID)
    with sessions() as db:
        usage = db.get(AgentUserUsage, ACCOUNT_ID)
        assert (
            usage.tokens_used == reserved
            and usage.tokens_reserved == 0
            and usage.active_request_id is None
        )
    finish_request(
        sessions,
        config,
        token=sid,
        user_id=ACCOUNT_ID,
        request_id=state["assistant_message"]["request_id"],
        answer="late",
        status="completed",
        input_tokens=1,
        output_tokens=1,
        estimated_usage=False,
    )
    assert (
        get_conversation(sessions, config, sid, user_id=ACCOUNT_ID)["messages"][1]["status"]
        == "failed"
    )


@pytest.mark.anyio
async def test_account_deletion_removes_normalized_messages_without_sqlite_fk(
    tmp_path, monkeypatch
):
    app, database = make_api_app(tmp_path, monkeypatch)
    monkeypatch.setattr("app.api.accounts.router.verify_password", lambda *_args: True)
    with database.session_factory() as db, db.begin():
        db.get(User, ACCOUNT_ID).password_hash = "scrypt$synthetic"
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": "Bearer account-test-token"},
        ) as client:
            sid = (await client.post("/agent/sessions")).json()["session_id"]
            await client.post(
                f"/agent/sessions/{sid}/messages/stream",
                json={"content": "测试数据", "client_request_id": str(uuid4())},
            )
            with database.session_factory() as db:
                assert db.scalar(select(func.count()).select_from(AgentMessage)) == 2
            assert (
                await client.request("DELETE", "/auth/me", json={"password": "synthetic"})
            ).status_code == 204
            with database.session_factory() as db:
                assert db.scalar(select(func.count()).select_from(AgentMessage)) == 0
                assert db.scalar(select(func.count()).select_from(AgentSession)) == 0
    finally:
        database.close()


def test_real_postgresql_history_and_context(request, tmp_path):
    if not request.config.getoption("--local-postgres"):
        pytest.skip("Use --local-postgres for real PostgreSQL migration/history validation")
    from app.db.local import local_database

    with local_database(tmp_path / "postgres-history") as url:
        engine = create_engine(url)
        try:
            factory = sessionmaker(engine, expire_on_commit=False)
            seed_account(factory)
            test_permanent_paged_messages_and_deletion(factory)
            test_context_recalls_source_task_after_many_messages_and_never_persists_location(
                factory
            )
        finally:
            engine.dispose()
