from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.models.accounts import EmailVerificationCode, UserSession
from app.db.session import Database
from app.main import app
from app.services.accounts.auth import code_digest, token_digest, utcnow

BACKEND = Path(__file__).resolve().parents[1]
TEST_CODE = "123456"


@pytest.fixture
def database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Database]:
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'accounts.db').as_posix()}")
    config = Config(str(BACKEND / "alembic.ini"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    database = Database.__new__(Database)
    database.engine = engine
    database.session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(app.state, "database", database)
    yield database
    database.close()


@pytest.fixture
async def client(database: Database) -> Iterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as value:
        yield value


@pytest.mark.anyio
async def test_email_code_register_login_me_and_logout(
    client: httpx.AsyncClient, database: Database
) -> None:
    assert (await client.get("/auth/me")).status_code == 401
    with patch("app.services.accounts.auth.send_verification_email") as send:
        response = await client.post("/auth/email-codes", json={"email": "Student@stu.pku.edu.cn"})
    assert response.status_code == 202
    assert "123456" not in response.text
    send.assert_called_once()

    with database.session_factory() as session:
        code = session.scalar(select(EmailVerificationCode))
        assert code is not None
        code.code_hash = code_digest(TEST_CODE, code.salt)
        session.commit()

    registered = await client.post(
        "/auth/register",
        json={
            "email": "student@stu.pku.edu.cn",
            "code": TEST_CODE,
            "password": "StrongPassword123",
        },
    )
    assert registered.status_code == 201
    payload = registered.json()
    assert payload["expires_in"] == 86400
    token = payload["access_token"]
    assert token
    assert "password_hash" not in payload
    assert (
        await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    ).json() == payload["user"]
    assert (
        await client.post(
            "/auth/register",
            json={
                "email": "student@stu.pku.edu.cn",
                "code": TEST_CODE,
                "password": "StrongPassword123",
            },
        )
    ).status_code == 409

    with database.session_factory() as session:
        record = session.scalar(select(UserSession))
        assert record is not None
        assert record.token_hash == token_digest(token)
        assert record.token_hash != token

    assert (
        await client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
    ).status_code == 204
    assert (
        await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    ).status_code == 401

    logged_in = await client.post(
        "/auth/login",
        json={"email": "student@stu.pku.edu.cn", "password": "StrongPassword123", "remember": True},
    )
    assert logged_in.status_code == 200
    assert logged_in.json()["expires_in"] == 30 * 86400


@pytest.mark.anyio
async def test_auth_rejects_invalid_domain_bad_code_and_password(
    client: httpx.AsyncClient,
) -> None:
    bad_domain = await client.post("/auth/email-codes", json={"email": "person@example.com"})
    assert bad_domain.status_code == 422
    weak_password = await client.post(
        "/auth/register",
        json={"email": "person@pku.edu.cn", "code": "123456", "password": "short"},
    )
    assert weak_password.status_code == 422
    assert all("input" not in error for error in weak_password.json()["detail"])
    malformed_code = await client.post(
        "/auth/register",
        json={"email": "person@pku.edu.cn", "code": "private-code", "password": "short"},
    )
    assert malformed_code.status_code == 422
    assert "private-code" not in malformed_code.text
    with patch("app.services.accounts.auth.send_verification_email"):
        assert (
            await client.post("/auth/email-codes", json={"email": "person@pku.edu.cn"})
        ).status_code == 202
    bad_code = await client.post(
        "/auth/register",
        json={"email": "person@pku.edu.cn", "code": "000000", "password": "StrongPassword123"},
    )
    assert bad_code.status_code == 400
    assert (
        await client.post("/auth/login", json={"email": "person@pku.edu.cn", "password": "wrong"})
    ).status_code == 401


@pytest.mark.anyio
async def test_verification_code_attempt_limit_and_expired_session(
    client: httpx.AsyncClient, database: Database
) -> None:
    with patch("app.services.accounts.auth.send_verification_email"):
        await client.post("/auth/email-codes", json={"email": "person@pku.edu.cn"})
    with database.session_factory() as session:
        record = session.scalar(select(EmailVerificationCode))
        assert record is not None
        record.code_hash = code_digest(TEST_CODE, record.salt)
        session.commit()

    wrong_payload = {
        "email": "person@pku.edu.cn",
        "code": "000000",
        "password": "StrongPassword123",
    }
    for _ in range(5):
        assert (await client.post("/auth/register", json=wrong_payload)).status_code == 400
    correct_payload = {**wrong_payload, "code": TEST_CODE}
    assert (await client.post("/auth/register", json=correct_payload)).status_code == 400

    with patch("app.services.accounts.auth.send_verification_email"):
        await client.post("/auth/email-codes", json={"email": "second@pku.edu.cn"})
    with database.session_factory() as session:
        code = session.scalar(
            select(EmailVerificationCode)
            .where(EmailVerificationCode.consumed_at.is_(None))
            .order_by(EmailVerificationCode.created_at.desc())
        )
        assert code is not None
        code.code_hash = code_digest(TEST_CODE, code.salt)
        session.commit()
    registered = await client.post(
        "/auth/register",
        json={**correct_payload, "email": "second@pku.edu.cn"},
    )
    assert registered.status_code == 201
    token = registered.json()["access_token"]
    token_hash = token_digest(token)
    with database.session_factory() as session:
        active_session = session.scalar(
            select(UserSession).where(UserSession.token_hash == token_hash)
        )
        assert active_session is not None
        active_session.expires_at = utcnow() - timedelta(seconds=1)
        session.commit()
    assert (
        await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    ).status_code == 401


@pytest.mark.anyio
async def test_email_codes_are_rate_limited_and_expire(
    client: httpx.AsyncClient, database: Database
) -> None:
    with patch("app.services.accounts.auth.send_verification_email") as send:
        first = await client.post("/auth/email-codes", json={"email": "person@pku.edu.cn"})
        second = await client.post("/auth/email-codes", json={"email": "person@pku.edu.cn"})
    assert first.status_code == second.status_code == 202
    sent_count = send.call_count
    for _ in range(4):
        with database.session_factory() as session:
            latest = session.scalar(
                select(EmailVerificationCode)
                .where(EmailVerificationCode.email == "person@pku.edu.cn")
                .order_by(EmailVerificationCode.created_at.desc())
            )
            assert latest is not None
            latest.created_at = utcnow() - timedelta(seconds=61)
            session.commit()
        with patch("app.services.accounts.auth.send_verification_email") as send_again:
            assert (
                await client.post("/auth/email-codes", json={"email": "person@pku.edu.cn"})
            ).status_code == 202
            send_again.assert_called_once()
            sent_count += send_again.call_count
    assert sent_count == 5
    with patch("app.services.accounts.auth.send_verification_email") as blocked_send:
        assert (
            await client.post("/auth/email-codes", json={"email": "person@pku.edu.cn"})
        ).status_code == 202
    blocked_send.assert_not_called()
    with database.session_factory() as session:
        record = session.scalar(
            select(EmailVerificationCode)
            .where(EmailVerificationCode.email == "person@pku.edu.cn")
            .order_by(EmailVerificationCode.created_at.desc())
        )
        assert record is not None
        record.expires_at = utcnow() - timedelta(seconds=1)
        session.commit()
    expired = await client.post(
        "/auth/register",
        json={"email": "person@pku.edu.cn", "code": TEST_CODE, "password": "StrongPassword123"},
    )
    assert expired.status_code == 400


@pytest.mark.anyio
async def test_accounts_need_database_and_me_requires_authentication(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = Database(None)
    monkeypatch.setattr(app.state, "database", database)
    response = await client.get("/auth/me")
    assert response.status_code == 503


@pytest.mark.anyio
async def test_auth_cors_allows_authorized_browser_requests(client: httpx.AsyncClient) -> None:
    response = await client.options(
        "/auth/login",
        headers={
            "Origin": "http://localhost:8765",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert response.status_code == 200
    assert "POST" in response.headers["access-control-allow-methods"]
    allowed_headers = response.headers["access-control-allow-headers"].lower()
    assert "authorization" in allowed_headers
    assert "content-type" in allowed_headers
