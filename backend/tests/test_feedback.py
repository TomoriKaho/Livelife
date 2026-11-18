"""Feedback durability, retry safety, maintenance boundary and account deletion."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, func, inspect, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from app.db.models import FeedbackEvent, User, UserFeedback, UserSession
from app.db.session import Database
from app.main import app
from app.schemas.feedback import FeedbackSubmission
from app.services.accounts.auth import create_session, password_hash, utcnow
from app.services.feedback.__main__ import execute, main, parser
from app.services.feedback.service import FeedbackError, change_status, submit_feedback

BACKEND = Path(__file__).resolve().parents[1]
PASSWORD = "synthetic-feedback-password"


@pytest.fixture
def anyio_backend():
    return "asyncio"


def migrate(engine, target="head", *, downgrade=False):
    config = Config(str(BACKEND / "alembic.ini"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        (command.downgrade if downgrade else command.upgrade)(config, target)


@pytest.fixture
def database(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'feedback.db').as_posix()}")

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    migrate(engine)
    db = Database.__new__(Database)
    db.engine = engine
    db.session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(app.state, "database", db)
    yield db
    db.close()


@pytest.fixture
async def client(database):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


def account(db):
    with db.session_factory() as session:
        user = User(
            id=uuid4(),
            email=f"{uuid4().hex}@pku.edu.cn",
            password_hash=password_hash(PASSWORD),
            created_at=utcnow(),
        )
        session.add(user)
        session.flush()
        token, _ = create_session(session, user, False)
        return user.id, {"Authorization": f"Bearer {token}"}


def payload(content="反馈样本，不含真实用户数据"):
    return {"client_request_id": str(uuid4()), "content": content}


def counts(db):
    with db.session_factory() as session:
        return tuple(
            session.scalar(select(func.count()).select_from(model))
            for model in (UserFeedback, FeedbackEvent)
        )


@pytest.mark.anyio
async def test_persists_once_and_replays_original_receipt_after_processing(client, database):
    owner, headers = account(database)
    request = payload("  原始反馈\n第二行  ")
    first = await client.post("/feedback", headers=headers, json=request)
    assert first.status_code == 201, first.text
    assert first.headers["cache-control"] == "no-store"
    receipt = first.json()
    assert set(receipt) == {"id", "submitted_at"}
    row_id = UUID(receipt["id"])
    with database.session_factory() as session:
        row = session.get(UserFeedback, row_id)
        assert row.user_id == owner and row.content == request["content"].strip()
        assert row.status == "pending" and row.version == 1
        assert row.submitted_at.utcoffset() == timedelta(0)
        change_status(session, row_id, "processing", actor="qa", reason="已查阅", version=1)
    for _ in range(3):
        retry = await client.post("/feedback", headers=headers, json=request)
        assert retry.status_code == 200 and retry.json() == receipt
    conflict = await client.post(
        "/feedback", headers=headers, json={**request, "content": "不同正文"}
    )
    assert conflict.status_code == 409
    assert counts(database) == (1, 1)


@pytest.mark.anyio
async def test_account_namespace_and_no_public_read_or_processing_routes(client, database):
    _, owner = account(database)
    _, other = account(database)
    request = payload()
    first = (await client.post("/feedback", headers=owner, json=request)).json()
    second = (await client.post("/feedback", headers=other, json=request)).json()
    assert first["id"] != second["id"]
    for headers in ({}, owner, other):
        for method, path in [
            ("GET", "/feedback"),
            ("GET", f"/feedback/{first['id']}"),
            ("PATCH", f"/feedback/{first['id']}"),
            ("POST", "/feedback/list"),
        ]:
            assert (await client.request(method, path, headers=headers)).status_code in (404, 405)
    assert counts(database) == (2, 0)


@pytest.mark.anyio
async def test_authentication_validation_and_length(client, database):
    owner, headers = account(database)
    assert (await client.post("/feedback", json=payload())).status_code == 401
    assert (
        await client.post("/feedback", headers={"Authorization": "Bearer invalid"}, json=payload())
    ).status_code == 401
    for content in ["", "  \n", "字" * 501, "a\x00b", None, 1]:
        assert (
            await client.post("/feedback", headers=headers, json=payload(content))
        ).status_code == 422
    for field, value in [("user_id", str(owner)), ("status", "resolved"), ("device", "secret")]:
        assert (
            await client.post("/feedback", headers=headers, json={**payload(), field: value})
        ).status_code == 422
    assert (
        await client.post("/feedback", headers=headers, json={"content": "missing key"})
    ).status_code == 422
    assert (
        await client.post("/feedback", headers=headers, json=payload("😀" * 500))
    ).status_code == 201
    with database.session_factory() as session:
        record = session.scalar(select(UserSession).where(UserSession.user_id == owner))
        record.expires_at = utcnow() - timedelta(seconds=1)
        session.commit()
    assert (await client.post("/feedback", headers=headers, json=payload())).status_code == 401


@pytest.mark.anyio
async def test_durable_rate_limits_and_replay_bypass(client, database):
    owner, headers = account(database)
    original = payload()
    assert (await client.post("/feedback", headers=headers, json=original)).status_code == 201
    for _ in range(2):
        assert (await client.post("/feedback", headers=headers, json=payload())).status_code == 201
    limited = await client.post("/feedback", headers=headers, json=payload())
    assert limited.status_code == 429 and 1 <= int(limited.headers["retry-after"]) <= 60
    assert (await client.post("/feedback", headers=headers, json=original)).status_code == 200
    now = utcnow()
    with database.session_factory() as session:
        for row in session.scalars(select(UserFeedback)):
            row.submitted_at = now - timedelta(hours=1)
        for _ in range(17):
            session.add(
                UserFeedback(
                    id=uuid4(),
                    user_id=owner,
                    client_request_id=uuid4(),
                    content="测试额度",
                    submitted_at=now - timedelta(hours=2),
                    status="pending",
                    version=1,
                )
            )
        session.commit()
    limited = await client.post("/feedback", headers=headers, json=payload())
    assert limited.status_code == 429 and int(limited.headers["retry-after"]) > 3600
    assert counts(database)[0] == 20


@pytest.mark.anyio
async def test_failed_commit_never_returns_success_and_retry_recovers(
    client, database, monkeypatch
):
    _, headers = account(database)
    request = payload()
    factory = database.session_factory
    original = factory.class_.commit

    def fail(_):
        raise OperationalError("private statement", {"content": "sensitive"}, Exception())

    with monkeypatch.context() as patch:
        patch.setattr(factory.class_, "commit", fail)
        response = await client.post("/feedback", headers=headers, json=request)
    assert original is factory.class_.commit
    assert response.status_code == 503
    assert "sensitive" not in response.text and "private statement" not in response.text
    assert counts(database) == (0, 0)
    assert (await client.post("/feedback", headers=headers, json=request)).status_code == 201
    assert counts(database) == (1, 0)


@pytest.mark.anyio
async def test_database_failure_during_authentication_is_recoverable(client, database, monkeypatch):
    _, headers = account(database)

    def fail(*_):
        raise OperationalError("private query", {"token": "private credential"}, Exception())

    monkeypatch.setattr("app.api.accounts.router.authenticated_user", fail)
    response = await client.post("/feedback", headers=headers, json=payload())
    assert response.status_code == 503
    assert "private" not in response.text
    assert counts(database) == (0, 0)


@pytest.mark.anyio
async def test_maintenance_filters_audit_conflicts_and_deletion(client, database):
    owner, headers = account(database)
    _, other = account(database)
    receipt = (await client.post("/feedback", headers=headers, json=payload())).json()
    await client.post("/feedback", headers=other, json=payload())
    row_id = receipt["id"]

    def cli(*argv):
        return execute(parser().parse_args(argv), database)

    assert len(cli("list")["items"]) == 2
    summary = cli("list", "--user-id", str(owner))["items"]
    assert len(summary) == 1 and "content" not in summary[0]
    assert not cli("list", "--since", "2099-01-01T00:00:00Z")["items"]
    assert not cli("list", "--before", "2020-01-01T00:00:00Z")["items"]
    assert not cli("list", "--offset", "2")["items"]
    with pytest.raises(FeedbackError):
        cli("list", "--offset", "-1")
    assert cli(
        "set-status",
        row_id,
        "processing",
        "--version",
        "1",
        "--actor",
        "qa",
        "--reason",
        "正在排查",
    )["changed"]
    with pytest.raises(FeedbackError, match="changed"):
        cli("set-status", row_id, "closed", "--version", "1", "--actor", "qa", "--reason", "旧操作")
    assert not cli(
        "set-status",
        row_id,
        "processing",
        "--version",
        "2",
        "--actor",
        "qa",
        "--reason",
        "相同状态",
    )["changed"]
    assert not cli("list", "--status", "resolved")["items"]
    detail = cli("show", row_id)
    assert detail["status"] == "processing" and detail["version"] == 2
    assert detail["events"][0]["actor"] == "qa" and detail["events"][0]["reason"] == "正在排查"
    assert len(detail["events"]) == 1
    assert (
        await client.request("DELETE", "/auth/me", headers=headers, json={"password": "wrong"})
    ).status_code == 400
    assert counts(database) == (2, 1)
    assert (
        await client.request("DELETE", "/auth/me", headers=headers, json={"password": PASSWORD})
    ).status_code == 204
    assert counts(database) == (1, 0)
    assert (await client.post("/feedback", headers=headers, json=payload())).status_code == 401
    with pytest.raises(FeedbackError, match="not found"):
        cli("show", row_id)


def test_cli_configuration_and_invalid_audit(database, monkeypatch, capsys):
    monkeypatch.setattr(Database, "from_environment", lambda: Database(None))
    assert main(["list"]) == 1
    assert "Set DATABASE_URL" in capsys.readouterr().err
    owner, _ = account(database)
    with database.session_factory() as session:
        receipt, _ = submit_feedback(session, owner, FeedbackSubmission(**payload()))
        for actor, reason in [("", "reason"), ("qa", ""), ("a" * 101, "reason"), ("qa", "\x00")]:
            with pytest.raises(FeedbackError):
                change_status(
                    session, receipt.id, "resolved", actor=actor, reason=reason, version=1
                )
    assert counts(database) == (1, 0)


def test_upgrade_preserves_accounts_and_downgrade_only_removes_feedback(database):
    owner, _ = account(database)
    with database.session_factory() as session:
        receipt, _ = submit_feedback(session, owner, FeedbackSubmission(**payload()))
        change_status(session, receipt.id, "resolved", actor="qa", reason="已验证", version=1)
    migrate(database.engine)
    assert counts(database) == (1, 1)
    migrate(database.engine, "0010_processing_diagnostics", downgrade=True)
    assert not {"user_feedback", "feedback_events"} & set(
        inspect(database.engine).get_table_names()
    )
    with database.session_factory() as session:
        assert session.get(User, owner) is not None
    migrate(database.engine)
    assert counts(database) == (0, 0)


def test_postgres_concurrent_retries_limits_and_audit(tmp_path, request):
    if not request.config.getoption("--local-postgres"):
        pytest.skip("Enable --local-postgres for real feedback row-lock checks")
    from app.db.local import local_database

    with local_database(tmp_path / "postgres") as url:
        db = Database(url)
        try:
            owner, _ = account(db)
            submission = FeedbackSubmission(**payload())

            def save(value):
                with db.session_factory() as session:
                    try:
                        return submit_feedback(session, owner, value)[0].id
                    except FeedbackError as error:
                        return error.status

            with ThreadPoolExecutor(max_workers=4) as workers:
                ids = list(workers.map(save, [submission] * 8))
                assert len(set(ids)) == 1 and counts(db) == (1, 0)
                outcomes = list(
                    workers.map(save, [FeedbackSubmission(**payload()) for _ in range(8)])
                )
                assert outcomes.count(429) == 6 and counts(db) == (3, 0)

                def process(_):
                    with db.session_factory() as session:
                        try:
                            change_status(
                                session,
                                ids[0],
                                "resolved",
                                actor="qa",
                                reason="并发核对",
                                version=1,
                            )
                            return 200
                        except FeedbackError as error:
                            return error.status

                assert sorted(workers.map(process, range(2))) == [200, 409]
                assert counts(db) == (3, 1)
        finally:
            db.close()
