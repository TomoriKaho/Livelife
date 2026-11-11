"""Account authorization, lifecycle and shared budget regressions through real routes."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import select
from test_agent import ACCOUNT_ID, make_api_app, settings

from app.db.models import AgentSession, AgentUserUsage, User, UserSession
from app.services.accounts.auth import (
    TEST_USER_ID,
    get_test_user,
    password_hash,
    token_digest,
)
from app.services.accounts.auth import (
    create_session as login_session,
)
from app.services.agent.service import (
    AgentError,
    begin_request,
    close_session,
    create_session,
    finish_request,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


def add_account(factory):
    with factory() as db:
        user = User(
            id=uuid4(),
            email=f"{uuid4().hex}@stu.pku.edu.cn",
            password_hash=password_hash("test-only-password"),
            created_at=datetime.now(UTC),
        )
        db.add(user)
        db.flush()
        token, _ = login_session(db, user, False)
        return user.id, token


def headers(token="account-test-token", conversation=None):
    result = {"Authorization": f"Bearer {token}"}
    if conversation:
        result["X-Agent-Session"] = conversation
    return result


async def protected_requests(client, credential, conversation):
    auth = headers(credential, conversation)
    return [
        await client.post("/agent/sessions", headers=auth),
        await client.get("/agent/sessions/current", headers=auth),
        await client.post(
            "/agent/messages/stream",
            headers=auth,
            json={"content": "hello", "client_request_id": str(uuid4())},
        ),
        await client.post(
            f"/agent/messages/{uuid4()}/rating", headers=auth, json={"rating": "like"}
        ),
        await client.post("/agent/sessions/close", headers=auth),
    ]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "kind", ["missing", "forged", "expired", "revoked", "deleted", "test", "old-agent"]
)
async def test_all_agent_routes_require_real_current_account(tmp_path, monkeypatch, kind):
    app, database = make_api_app(tmp_path, monkeypatch, model=True)
    calls = []

    async def unexpected(*args, **kwargs):
        calls.append(True)
        yield "forbidden", None

    monkeypatch.setattr("app.api.agent.router.stream_completion", unexpected)
    try:
        factory = database.session_factory
        config = settings()
        conversation = create_session(factory, config, "test", user_id=ACCOUNT_ID)
        credential = "account-test-token"
        expected = 401
        with factory() as db, db.begin():
            login = db.scalar(select(UserSession))
            if kind == "expired":
                login.expires_at = datetime.now(UTC) - timedelta(seconds=1)
            elif kind == "revoked":
                login.revoked_at = datetime.now(UTC)
            elif kind == "deleted":
                db.delete(db.get(User, ACCOUNT_ID))
        if kind == "test":
            monkeypatch.setenv("AUTH_TEST_LOGIN_ENABLED", "true")
            with factory() as db:
                credential, _ = login_session(db, get_test_user(db), False)
            expected = 403  # Even opt-in local test users never get model privileges.
        elif kind == "forged":
            credential = "forged"
        elif kind == "missing":
            credential = ""
        elif kind == "old-agent":
            credential = conversation["session_token"]
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            results = await protected_requests(client, credential, conversation["session_token"])
        assert [r.status_code for r in results] == [expected] * 5
        assert calls == []
        with factory() as db:
            assert db.get(AgentSession, conversation["session_id"]).messages == []
    finally:
        database.close()


@pytest.mark.anyio
async def test_ownership_legacy_and_legitimate_flow(tmp_path, monkeypatch):
    app, database = make_api_app(tmp_path, monkeypatch)
    try:
        _, other_token = add_account(database.session_factory)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            created = await client.post(
                "/agent/sessions", headers=headers(), json={"user_id": str(uuid4())}
            )
            assert created.status_code == 201
            conversation = created.json()["session_token"]
            own = headers(conversation=conversation)
            forbidden = await protected_requests(client, other_token, conversation)
            assert forbidden[0].status_code == 201
            assert [r.status_code for r in forbidden[1:]] == [401] * 4
            assert (await client.get("/agent/sessions/current", headers=own)).json()[
                "messages"
            ] == []
            response = await client.post(
                "/agent/messages/stream",
                headers=own,
                json={"content": "hello", "client_request_id": str(uuid4())},
            )
            assert "event: done" in response.text
            history = (await client.get("/agent/sessions/current", headers=own)).json()["messages"]
            message_id = history[-1]["id"]
            assert (
                await client.post(
                    f"/agent/messages/{message_id}/rating", headers=own, json={"rating": "like"}
                )
            ).status_code == 204
            assert (await client.post("/agent/sessions/close", headers=own)).status_code == 204
            # Simulate an anonymous pre-upgrade row (NULL owner), never adopt it.
            legacy = (await client.post("/agent/sessions", headers=headers())).json()
            with database.session_factory() as db, db.begin():
                row = db.get(AgentSession, UUID(legacy["session_id"]))
                row.user_id = None
            assert (
                await client.get(
                    "/agent/sessions/current", headers=headers(conversation=legacy["session_token"])
                )
            ).status_code == 401
    finally:
        database.close()


@pytest.mark.anyio
async def test_default_blank_login_and_old_test_login_are_disabled(tmp_path, monkeypatch):
    app, database = make_api_app(tmp_path, monkeypatch)
    try:
        monkeypatch.setenv("AUTH_TEST_LOGIN_ENABLED", "true")
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            test = (await client.post("/auth/login", json={"email": "", "password": ""})).json()
            monkeypatch.delenv("AUTH_TEST_LOGIN_ENABLED")
            assert (
                await client.post("/auth/login", json={"email": "", "password": ""})
            ).status_code == 403
            assert (
                await client.get("/auth/me", headers=headers(test["access_token"]))
            ).status_code == 401
            assert (
                await client.post("/agent/sessions", headers=headers(test["access_token"]))
            ).status_code == 401
            assert test["user"]["id"] == str(TEST_USER_ID)
    finally:
        database.close()


@pytest.mark.anyio
@pytest.mark.parametrize("change", ["logout", "expire", "delete"])
async def test_stream_revocation_stops_upstream_and_settles_budget(tmp_path, monkeypatch, change):
    app, database = make_api_app(tmp_path, monkeypatch, model=True)
    ended = []
    user_id, account = add_account(database.session_factory)

    async def completion(*args, **kwargs):
        try:
            yield "first", None
            with database.session_factory() as db, db.begin():
                record = db.scalar(
                    select(UserSession).where(UserSession.token_hash == token_digest(account))
                )
                if change == "logout":
                    record.revoked_at = datetime.now(UTC)
                elif change == "expire":
                    record.expires_at = datetime.now(UTC) - timedelta(seconds=1)
                else:
                    db.delete(db.get(User, user_id))
            # The monitor must stop an upstream that stalls without another chunk.
            await asyncio.sleep(3)
            yield "must-not-leak", None
        finally:
            ended.append(True)

    monkeypatch.setattr("app.api.agent.router.stream_completion", completion)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            created = (await client.post("/agent/sessions", headers=headers(account))).json()
            response = await client.post(
                "/agent/messages/stream",
                headers=headers(account, created["session_token"]),
                json={"content": "hello", "client_request_id": str(uuid4())},
            )
            assert "first" in response.text
            assert "must-not-leak" not in response.text
            assert "authentication_required" in response.text
            assert "event: done" not in response.text
            assert ended == [True]
            assert (
                await client.get(
                    "/agent/sessions/current", headers=headers(account, created["session_token"])
                )
            ).status_code == 401
        with database.session_factory() as db:
            usage = db.get(AgentUserUsage, user_id)
            if usage:
                assert usage.active_request_id is None
                assert usage.tokens_reserved == 0
                assert usage.tokens_used > 0
    finally:
        database.close()


def test_budget_rate_and_active_request_follow_user_across_sessions(tmp_path, monkeypatch):
    _, database = make_api_app(tmp_path, monkeypatch)
    factory = database.session_factory
    config = settings(
        llm_base_url="https://example.test",
        llm_api_key="test",
        llm_model="test",
        daily_token_quota=1000,
        requests_per_minute=2,
    )
    try:
        first = create_session(factory, config, "one", user_id=ACCOUNT_ID)
        second = create_session(factory, config, "two", user_id=ACCOUNT_ID)

        def begin(conversation):
            return begin_request(
                factory,
                config,
                token=conversation["session_token"],
                user_id=ACCOUNT_ID,
                content="hello",
                client_request_id=uuid4(),
                ip="three",
            )

        state = begin(first)
        with pytest.raises(AgentError, match="user_request_in_progress"):
            begin(second)
        with pytest.raises(AgentError, match="user_request_in_progress"):
            close_session(factory, config, first["session_token"], user_id=ACCOUNT_ID)
        kwargs = dict(
            token=first["session_token"],
            user_id=ACCOUNT_ID,
            request_id=state["assistant_message"]["request_id"],
            answer="hello",
            status="completed",
            input_tokens=900,
            output_tokens=0,
            estimated_usage=False,
        )
        finish_request(factory, config, **kwargs)
        finish_request(factory, config, **kwargs)  # No double debit.
        close_session(factory, config, first["session_token"], user_id=ACCOUNT_ID)
        with pytest.raises(AgentError, match="token_quota_exceeded"):
            begin(second)
        with factory() as db:
            assert db.get(AgentUserUsage, ACCOUNT_ID).tokens_used == 900
        another_id, _ = add_account(factory)
        other = create_session(factory, config, "four", user_id=another_id)
        begin_request(
            factory,
            config,
            token=other["session_token"],
            user_id=another_id,
            content="hello",
            client_request_id=uuid4(),
            ip="five",
        )
    finally:
        database.close()


def test_user_rate_limit_and_expired_lease_cannot_reset_budget(tmp_path, monkeypatch):
    _, database = make_api_app(tmp_path, monkeypatch)
    factory = database.session_factory
    config = settings(requests_per_minute=1)
    try:
        first = create_session(factory, config, "one", user_id=ACCOUNT_ID)
        second = create_session(factory, config, "two", user_id=ACCOUNT_ID)
        state = begin_request(
            factory,
            config,
            token=first["session_token"],
            user_id=ACCOUNT_ID,
            content="hello",
            client_request_id=uuid4(),
            ip="three",
        )
        finish_request(
            factory,
            config,
            token=first["session_token"],
            user_id=ACCOUNT_ID,
            request_id=state["assistant_message"]["request_id"],
            answer="ok",
            status="completed",
            input_tokens=1,
            output_tokens=1,
            estimated_usage=False,
        )
        with pytest.raises(AgentError, match="user_rate_limited"):
            begin_request(
                factory,
                config,
                token=second["session_token"],
                user_id=ACCOUNT_ID,
                content="hello",
                client_request_id=uuid4(),
                ip="four",
            )
        with factory() as db, db.begin():
            usage = db.get(AgentUserUsage, ACCOUNT_ID)
            usage.request_window_start -= timedelta(minutes=2)
            usage.usage_day -= timedelta(days=1)
            usage.tokens_used = 500
            usage.tokens_reserved = 700
            usage.active_request_id = str(uuid4())
            usage.active_request_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        state = begin_request(
            factory,
            config,
            token=second["session_token"],
            user_id=ACCOUNT_ID,
            content="hello",
            client_request_id=uuid4(),
            ip="five",
        )
        with factory() as db:
            usage = db.get(AgentUserUsage, ACCOUNT_ID)
            assert usage.tokens_used == 700
            assert usage.usage_day == datetime.now(UTC).date()
    finally:
        database.close()


@pytest.mark.anyio
async def test_revocation_before_first_event_blocks_replay_and_new_model(tmp_path, monkeypatch):
    from starlette.requests import Request

    from app.api.agent.router import send_message
    from app.services.agent.schemas import SendMessageRequest

    app, database = make_api_app(tmp_path, monkeypatch, model=True)
    calls = []

    async def completion(*args, **kwargs):
        calls.append(True)
        yield "answer", None

    monkeypatch.setattr("app.api.agent.router.stream_completion", completion)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            for replay in (False, True):
                user_id, token = add_account(database.session_factory)
                created = (await client.post("/agent/sessions", headers=headers(token))).json()
                request_id = str(uuid4())
                if replay:
                    result = await client.post(
                        "/agent/messages/stream",
                        headers=headers(token, created["session_token"]),
                        json={"content": "hello", "client_request_id": request_id},
                    )
                    assert "event: done" in result.text
                with database.session_factory() as db:
                    user = db.get(User, user_id)
                request = Request(
                    {
                        "type": "http",
                        "app": app,
                        "client": ("test", 1),
                        "headers": [
                            (b"authorization", f"Bearer {token}".encode()),
                            (b"x-agent-session", created["session_token"].encode()),
                        ],
                    }
                )
                response = await send_message(
                    request, SendMessageRequest(content="hello", client_request_id=request_id), user
                )
                assert (
                    await client.post("/auth/logout", headers=headers(token))
                ).status_code == 204
                count = len(calls)
                body = "".join([part async for part in response.body_iterator])
                assert "authentication_required" in body
                assert "answer" not in body
                assert len(calls) == count
                with database.session_factory() as db:
                    usage = db.get(AgentUserUsage, user_id)
                    assert usage.active_request_id is None
                    assert usage.tokens_reserved == 0
    finally:
        database.close()


@pytest.mark.anyio
async def test_account_deletion_removes_conversations_and_usage(tmp_path, monkeypatch):
    app, database = make_api_app(tmp_path, monkeypatch)
    user_id, token = add_account(database.session_factory)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            created = (await client.post("/agent/sessions", headers=headers(token))).json()
            await client.post(
                "/agent/messages/stream",
                headers=headers(token, created["session_token"]),
                json={"content": "hello", "client_request_id": str(uuid4())},
            )
            rejected = await client.request(
                "DELETE", "/auth/me", headers=headers(token), json={"password": "wrong"}
            )
            assert rejected.status_code == 400
            assert (
                await client.get(
                    "/agent/sessions/current", headers=headers(token, created["session_token"])
                )
            ).status_code == 200
            deleted = await client.request(
                "DELETE",
                "/auth/me",
                headers=headers(token),
                json={"password": "test-only-password"},
            )
            assert deleted.status_code == 204
            assert (await client.post("/agent/sessions", headers=headers(token))).status_code == 401
        with database.session_factory() as db:
            assert db.get(AgentUserUsage, user_id) is None
            assert db.scalar(select(AgentSession).where(AgentSession.user_id == user_id)) is None
    finally:
        database.close()


def test_postgres_concurrent_sessions_share_one_active_budget(request, tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from test_agent import seed_account

    from app.db.local import local_database

    if not request.config.getoption("--local-postgres"):
        pytest.skip("Use --local-postgres with the local-db dependency group")
    with local_database(tmp_path / "postgres") as url:
        engine = create_engine(url)
        factory = sessionmaker(engine, expire_on_commit=False)
        try:
            seed_account(factory)
            config = settings(
                llm_base_url="https://example.test", llm_api_key="test", llm_model="test"
            )
            conversations = [
                create_session(factory, config, str(i), user_id=ACCOUNT_ID) for i in range(2)
            ]
            barrier = Barrier(2)

            def start(conversation):
                barrier.wait(timeout=5)
                try:
                    return begin_request(
                        factory,
                        config,
                        token=conversation["session_token"],
                        user_id=ACCOUNT_ID,
                        content="hello",
                        client_request_id=uuid4(),
                        ip="test",
                    )
                except AgentError as error:
                    return error.code

            with ThreadPoolExecutor(max_workers=2) as pool:
                outcomes = list(pool.map(start, conversations))
            assert sum(isinstance(item, dict) for item in outcomes) == 1
            assert "user_request_in_progress" in outcomes
            with factory() as db:
                usage = db.get(AgentUserUsage, ACCOUNT_ID)
                assert usage.request_count == 1
                assert usage.tokens_reserved > 0
        finally:
            engine.dispose()


@pytest.mark.anyio
async def test_continuously_producing_model_obeys_total_deadline(tmp_path, monkeypatch):
    from dataclasses import replace

    from app.core.config import get_agent_settings

    app, database = make_api_app(tmp_path, monkeypatch, model=True)
    config = replace(get_agent_settings(), llm_timeout_seconds=0.1)
    monkeypatch.setattr("app.api.agent.router.get_agent_settings", lambda: config)
    closed = []

    async def endless(*args, **kwargs):
        assert database.engine.pool.checkedout() == 0
        try:
            while True:
                await asyncio.sleep(0.01)
                yield "tick", None
        finally:
            closed.append(True)

    monkeypatch.setattr("app.api.agent.router.stream_completion", endless)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            created = (await client.post("/agent/sessions", headers=headers())).json()
            async with asyncio.timeout(2):
                response = await client.post(
                    "/agent/messages/stream",
                    headers=headers(conversation=created["session_token"]),
                    json={"content": "hello", "client_request_id": str(uuid4())},
                )
            assert "tick" in response.text
            assert "model_timeout" in response.text
            assert "event: done" not in response.text
            assert closed == [True]
            history = (
                await client.get(
                    "/agent/sessions/current",
                    headers=headers(conversation=created["session_token"]),
                )
            ).json()
            assert history["messages"][-1]["status"] == "failed"
        with database.session_factory() as db:
            usage = db.get(AgentUserUsage, ACCOUNT_ID)
            assert usage.active_request_id is None
            assert usage.tokens_reserved == 0
            assert usage.tokens_used > 0
    finally:
        database.close()


def test_postgres_delete_and_finalize_have_consistent_lock_order(request, tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event, local

    from fastapi import Response
    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import sessionmaker

    from app.api.accounts.router import delete_account
    from app.db.local import local_database
    from app.schemas.accounts import AccountDeletionRequest

    if not request.config.getoption("--local-postgres"):
        pytest.skip("Use --local-postgres with the local-db dependency group")
    with local_database(tmp_path / "postgres") as url:
        engine = create_engine(url)
        factory = sessionmaker(engine, expire_on_commit=False)
        usage_locked, deletion_started = Event(), Event()
        thread = local()
        try:
            user_id, _ = add_account(factory)
            config = settings()
            conversation = create_session(factory, config, "test", user_id=user_id)
            state = begin_request(
                factory,
                config,
                token=conversation["session_token"],
                user_id=user_id,
                content="hello",
                client_request_id=uuid4(),
                ip="test",
            )

            @event.listens_for(engine, "after_cursor_execute")
            def hold_usage(_conn, _cursor, statement, _parameters, _context, _many):
                if (
                    getattr(thread, "role", None) == "finish"
                    and "FROM agent_user_usage" in statement
                ):
                    usage_locked.set()
                    assert deletion_started.wait(5)

            @event.listens_for(engine, "before_cursor_execute")
            def start_delete(_conn, _cursor, statement, _parameters, _context, _many):
                if (
                    getattr(thread, "role", None) == "delete"
                    and "DELETE FROM agent_user_usage" in statement
                ):
                    deletion_started.set()

            def finalize():
                thread.role = "finish"
                finish_request(
                    factory,
                    config,
                    token=conversation["session_token"],
                    user_id=user_id,
                    request_id=state["assistant_message"]["request_id"],
                    answer="ok",
                    status="completed",
                    input_tokens=2,
                    output_tokens=1,
                    estimated_usage=False,
                )

            def remove():
                thread.role = "delete"
                assert usage_locked.wait(5)
                with factory() as db:
                    return delete_account(
                        AccountDeletionRequest(password="test-only-password"),
                        Response(),
                        db,
                        db.get(User, user_id),
                    ).status_code

            with ThreadPoolExecutor(max_workers=2) as pool:
                finishing, deleting = pool.submit(finalize), pool.submit(remove)
                assert deleting.result(timeout=10) == 204
                finishing.result(timeout=10)
            with factory() as db:
                assert db.get(User, user_id) is None
                assert db.get(AgentUserUsage, user_id) is None
                assert (
                    db.scalar(select(AgentSession).where(AgentSession.user_id == user_id)) is None
                )
        finally:
            usage_locked.set()
            deletion_started.set()
            engine.dispose()


@pytest.mark.anyio
async def test_stalled_downstream_does_not_hold_model_past_deadline(tmp_path, monkeypatch):
    from dataclasses import replace

    from starlette.requests import Request

    from app.api.agent.router import send_message
    from app.core.config import get_agent_settings
    from app.services.agent.schemas import SendMessageRequest

    app, database = make_api_app(tmp_path, monkeypatch, model=True)
    config = replace(get_agent_settings(), llm_timeout_seconds=0.1)
    monkeypatch.setattr("app.api.agent.router.get_agent_settings", lambda: config)
    closed = []

    async def completion(*args, **kwargs):
        try:
            yield "first", None
            await asyncio.sleep(10)
        finally:
            closed.append(True)

    monkeypatch.setattr("app.api.agent.router.stream_completion", completion)
    try:
        created = create_session(database.session_factory, config, "test", user_id=ACCOUNT_ID)
        with database.session_factory() as db:
            user = db.get(User, ACCOUNT_ID)
        request = Request(
            {
                "type": "http",
                "app": app,
                "client": ("test", 1),
                "headers": [
                    (b"authorization", b"Bearer account-test-token"),
                    (b"x-agent-session", created["session_token"].encode()),
                ],
            }
        )
        response = await send_message(
            request, SendMessageRequest(content="hello", client_request_id=uuid4()), user
        )
        iterator = response.body_iterator
        assert "message_start" in await anext(iterator)
        assert "first" in await anext(iterator)
        await asyncio.sleep(0.25)  # Client stops reading after the first delta.
        assert closed == [True]
        with database.session_factory() as db:
            assert db.get(AgentUserUsage, ACCOUNT_ID).active_request_id is None
        assert "model_timeout" in await anext(iterator)
        await iterator.aclose()
    finally:
        database.close()
