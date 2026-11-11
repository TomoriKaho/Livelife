import hashlib
import hmac
import secrets
import smtplib
import ssl
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from os import environ
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models.accounts import EmailVerificationCode, User, UserSession

CODE_TTL = timedelta(minutes=10)
CODE_RESEND_DELAY = timedelta(seconds=60)
CODE_RATE_WINDOW = timedelta(minutes=15)
CODE_RATE_LIMIT = 5
CODE_MAX_ATTEMPTS = 5
SESSION_SHORT_TTL = timedelta(days=1)
SESSION_REMEMBER_TTL = timedelta(days=30)
TEST_USER_ID = UUID("82054870-6c9c-4a64-9439-5204f8ede144")
TEST_USER_EMAIL = "builtin-test@livelife.invalid"


def test_login_enabled() -> bool:
    return environ.get("AUTH_TEST_LOGIN_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def get_test_user(session: Session) -> User:
    user = session.get(User, TEST_USER_ID)
    if user is None:
        try:
            with session.begin_nested():
                user = User(
                    id=TEST_USER_ID,
                    email=TEST_USER_EMAIL,
                    password_hash="!test-account-no-password",
                    created_at=utcnow(),
                )
                session.add(user)
                session.flush()
        except IntegrityError:
            # Concurrent first logins must share the same account. Only the
            # savepoint is rolled back; create_session commits the final login.
            user = session.get(User, TEST_USER_ID)
            if user is None:
                raise
    return user


def utcnow() -> datetime:
    return datetime.now(UTC)


def password_hash(password: str, *, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, salt_hex, expected = encoded.split("$", 2)
        if algorithm != "scrypt":
            return False
        actual = password_hash(password, salt=bytes.fromhex(salt_hex)).split("$")[-1]
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def code_digest(code: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", code.encode(), bytes.fromhex(salt), 200_000).hex()


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _smtp_settings() -> tuple[str, int, str, str, str]:
    host = environ.get("SMTP_HOST", "").strip()
    username = environ.get("SMTP_USERNAME", "").strip()
    password = environ.get("SMTP_PASSWORD", "")
    sender = environ.get("SMTP_FROM", "").strip()
    port = int(environ.get("SMTP_PORT", "587"))
    if not host or not sender:
        raise RuntimeError("SMTP_HOST and SMTP_FROM must be configured")
    return host, port, username, password, sender


def send_verification_email(email: str, code: str) -> None:
    host, port, username, password, sender = _smtp_settings()
    message = EmailMessage()
    message["Subject"] = "Livelife 注册验证码"
    message["From"] = sender
    message["To"] = email
    message.set_content(f"你的 Livelife 注册验证码是：{code}\n验证码 10 分钟内有效，请勿转发。")
    context = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=context, timeout=10) as client:
            if username:
                client.login(username, password)
            client.send_message(message)
    else:
        with smtplib.SMTP(host, port, timeout=10) as client:
            client.ehlo()
            client.starttls(context=context)
            client.ehlo()
            if username:
                client.login(username, password)
            client.send_message(message)


def issue_code(session: Session, email: str) -> bool:
    now = utcnow()
    session.execute(
        delete(EmailVerificationCode).where(
            EmailVerificationCode.created_at < now - timedelta(days=1)
        )
    )
    recent = session.scalars(
        select(EmailVerificationCode)
        .where(
            EmailVerificationCode.email == email,
            EmailVerificationCode.created_at >= now - CODE_RATE_WINDOW,
        )
        .order_by(EmailVerificationCode.created_at.desc())
    ).all()
    if recent and now - recent[0].created_at < CODE_RESEND_DELAY:
        return False
    if len(recent) >= CODE_RATE_LIMIT:
        return False
    code = f"{secrets.randbelow(1_000_000):06d}"
    salt = secrets.token_hex(16)
    session.add(
        EmailVerificationCode(
            id=uuid4(),
            email=email,
            code_hash=code_digest(code, salt),
            salt=salt,
            created_at=now,
            expires_at=now + CODE_TTL,
            attempts=0,
        )
    )
    session.commit()
    try:
        send_verification_email(email, code)
    except Exception:
        record = session.scalar(
            select(EmailVerificationCode)
            .where(EmailVerificationCode.email == email)
            .order_by(EmailVerificationCode.created_at.desc())
        )
        if record:
            record.consumed_at = utcnow()
            session.commit()
        raise
    return True


def create_session(session: Session, user: User, remember: bool) -> tuple[str, int]:
    now = utcnow()
    lifetime = SESSION_REMEMBER_TTL if remember else SESSION_SHORT_TTL
    session.execute(delete(UserSession).where(UserSession.expires_at <= now))
    token = secrets.token_urlsafe(32)
    session.add(
        UserSession(
            id=uuid4(),
            user_id=user.id,
            token_hash=token_digest(token),
            created_at=now,
            expires_at=now + lifetime,
        )
    )
    session.commit()
    return token, int(lifetime.total_seconds())


def authenticated_user(session: Session, token: str) -> User | None:
    """Resolve a current account credential; callers never supply the user ID."""
    record = session.scalar(
        select(UserSession).where(
            UserSession.token_hash == token_digest(token),
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > utcnow(),
        )
    )
    user = session.get(User, record.user_id) if record else None
    if user is not None and user.id == TEST_USER_ID and not test_login_enabled():
        return None
    return user
