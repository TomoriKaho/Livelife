import hashlib
import hmac
import secrets
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import case, delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import AgentSettings
from app.db.models import AgentIpWindow, AgentSession, AgentUserUsage, User
from app.services.agent.llm import estimate_input_tokens
from app.services.agent.retrieval import RetrievedInformation, search_information

SESSION_TTL = timedelta(hours=24)
REQUEST_WINDOW = timedelta(minutes=1)
IP_WINDOW = timedelta(hours=1)
ACTIVE_LEASE = timedelta(minutes=3)
_FOLLOW_UP_MARKERS = (
    "这个课",
    "这门课",
    "这节课",
    "这个老师",
    "这位老师",
    "他是谁",
    "她是谁",
    "它的",
    "这个活动",
    "这个地点",
    "这个呢",
    "那它",
    "那这个",
)


def _is_contextual_follow_up(content: str) -> bool:
    return any(marker in content for marker in _FOLLOW_UP_MARKERS)


class AgentError(RuntimeError):
    def __init__(self, code: str, status_code: int, *, retry_after: int | None = None):
        super().__init__(code)
        self.code = code
        self.status_code = status_code
        self.retry_after = retry_after


def _digest(secret: str, label: str, value: str) -> str:
    return hmac.new(secret.encode(), f"{label}:{value}".encode(), hashlib.sha256).hexdigest()


def _token_hash(settings: AgentSettings, token: str) -> str:
    return _digest(settings.session_secret, "session", token)


def _ip_hash(settings: AgentSettings, ip: str) -> str:
    return _digest(settings.session_secret, "ip", ip)


def create_session(
    factory: sessionmaker[Session], settings: AgentSettings, ip: str, *, user_id: UUID
) -> dict:
    if not settings.session_secret:
        raise AgentError("agent_not_configured", 503)
    now = datetime.now(UTC)
    token = secrets.token_urlsafe(32)
    row = AgentSession(
        id=uuid4(),
        user_id=user_id,
        token_hash=_token_hash(settings, token),
        messages=[],
        created_at=now,
        last_seen_at=now,
        expires_at=now + SESSION_TTL,
        request_window_start=_window_start(now, REQUEST_WINDOW),
        request_count=0,
        active_request_id=None,
        active_request_expires_at=None,
        usage_day=now.date(),
        tokens_used=0,
        tokens_reserved=0,
    )
    with factory() as session, session.begin():
        if not _hit_ip_window(session, _ip_hash(settings, ip), now, settings.ip_requests_per_hour):
            raise AgentError("ip_rate_limited", 429, retry_after=3600)
        session.add(row)
        _prune_expired(session, now)
    return {"session_id": row.id, "session_token": token, "expires_at": row.expires_at}


def _window_start(now: datetime, duration: timedelta) -> datetime:
    epoch = int(now.timestamp())
    size = int(duration.total_seconds())
    return datetime.fromtimestamp(epoch - epoch % size, UTC)


def _prune_expired(session: Session, now: datetime) -> None:
    expired = select(AgentSession.id).where(AgentSession.expires_at <= now).limit(100)
    session.execute(delete(AgentSession).where(AgentSession.id.in_(expired)))
    session.execute(delete(AgentIpWindow).where(AgentIpWindow.window_start < now - IP_WINDOW * 2))


def _session(
    session: Session, settings: AgentSettings, token: str, now: datetime, user_id: UUID
) -> AgentSession:
    if not settings.session_secret:
        raise AgentError("agent_not_configured", 503)
    row = session.scalar(
        select(AgentSession)
        .where(
            AgentSession.token_hash == _token_hash(settings, token),
            AgentSession.user_id == user_id,
        )
        .with_for_update()
    )
    if row is None:
        raise AgentError("invalid_session", 401)
    if row.expires_at <= now:
        error = AgentError("session_expired", 404)
        error.expired_token_hash = row.token_hash
        raise error
    return row


def get_history(
    factory: sessionmaker[Session], settings: AgentSettings, token: str, *, user_id: UUID
) -> dict:
    now = datetime.now(UTC)
    with factory() as session, session.begin():
        row = _session(session, settings, token, now, user_id)
        row.last_seen_at = now
        return {"session_id": row.id, "expires_at": row.expires_at, "messages": row.messages or []}


def _hit_ip_window(session: Session, ip_hash: str, now: datetime, limit: int) -> bool:
    dialect = session.get_bind().dialect.name
    insert = pg_insert if dialect == "postgresql" else sqlite_insert
    start = _window_start(now, IP_WINDOW)
    statement = insert(AgentIpWindow).values(ip_hash=ip_hash, window_start=start, request_count=1)
    statement = statement.on_conflict_do_update(
        index_elements=["ip_hash"],
        set_={
            "window_start": case(
                (AgentIpWindow.window_start < start, start), else_=AgentIpWindow.window_start
            ),
            "request_count": case(
                (AgentIpWindow.window_start < start, 1), else_=AgentIpWindow.request_count + 1
            ),
        },
    ).returning(AgentIpWindow.request_count)
    return session.scalar(statement) <= limit


def _safe_message(message: dict[str, Any]) -> dict:
    result = dict(message)
    result["id"] = str(result["id"])
    return result


def _usage(session: Session, user_id: UUID, now: datetime) -> AgentUserUsage:
    # Serialize first-use quota creation against account deletion too: there may
    # not yet be a usage row for DELETE/SELECT FOR UPDATE to lock.
    if session.scalar(select(User.id).where(User.id == user_id).with_for_update()) is None:
        raise AgentError("authentication_required", 401)
    insert = pg_insert if session.get_bind().dialect.name == "postgresql" else sqlite_insert
    session.execute(
        insert(AgentUserUsage)
        .values(
            user_id=user_id,
            request_window_start=_window_start(now, REQUEST_WINDOW),
            request_count=0,
            usage_day=now.date(),
            tokens_used=0,
            tokens_reserved=0,
        )
        .on_conflict_do_nothing(index_elements=["user_id"])
    )
    return session.scalar(
        select(AgentUserUsage).where(AgentUserUsage.user_id == user_id).with_for_update()
    )


def begin_request(
    factory: sessionmaker[Session],
    settings: AgentSettings,
    *,
    token: str,
    user_id: UUID,
    content: str,
    client_request_id: UUID,
    ip: str,
) -> dict:
    content = content.strip()
    if not content:
        raise AgentError("empty_message", 422)
    if len(content) > settings.max_message_chars:
        raise AgentError("message_too_long", 413)

    now = datetime.now(UTC)
    with factory() as session, session.begin():
        usage = _usage(session, user_id, now)
        row = _session(session, settings, token, now, user_id)
        if not _hit_ip_window(session, _ip_hash(settings, ip), now, settings.ip_requests_per_hour):
            raise AgentError("ip_rate_limited", 429, retry_after=3600)

        messages = list(row.messages or [])
        previous = next(
            (
                message
                for message in messages
                if message.get("client_request_id") == str(client_request_id)
            ),
            None,
        )
        if previous is not None:
            assistant = next(
                (
                    message
                    for message in messages
                    if message.get("request_id") == previous.get("request_id")
                    and message.get("role") == "assistant"
                ),
                None,
            )
            if assistant and assistant.get("status") == "completed":
                return {"duplicate": True, "messages": [previous, assistant]}
            raise AgentError("request_in_progress", 409)

        if usage.usage_day != now.date():
            usage.usage_day = now.date()
            usage.tokens_used = 0
        # A crashed/cancelled upstream may have billed its reservation. Never let
        # a fresh conversation or expired lease silently restore that budget.
        if usage.active_request_expires_at and usage.active_request_expires_at <= now:
            usage.tokens_used += usage.tokens_reserved
            usage.tokens_reserved = 0
            usage.active_request_id = None
            usage.active_request_expires_at = None
        minute = _window_start(now, REQUEST_WINDOW)
        if usage.request_window_start < minute:
            usage.request_window_start = minute
            usage.request_count = 0
        if (
            usage.active_request_id
            and usage.active_request_expires_at
            and usage.active_request_expires_at > now
        ):
            raise AgentError("user_request_in_progress", 429, retry_after=10)
        if usage.request_count >= settings.requests_per_minute:
            raise AgentError("user_rate_limited", 429, retry_after=60)

        # Use prior dialogue only as a retrieval hint for explicit follow-ups. The
        # model still receives this turn's newly retrieved public records as evidence.
        completed = [
            message
            for message in messages
            if message.get("status") == "completed" and message.get("role") in {"user", "assistant"}
        ]
        retrieval_query = content
        if completed and _is_contextual_follow_up(content):
            prior_context = " ".join(message.get("content", "") for message in completed[-2:])
            retrieval_query = f"{prior_context} {content}"
        # Retrieval uses only public information records. A capped scan keeps the
        # synchronous repository query bounded until a dedicated search index exists.
        sources = search_information(session, retrieval_query)
        context_chars = sum(len(source.content) for source in sources)
        if context_chars > settings.max_context_chars:
            sources = _limit_sources(sources, settings.max_context_chars)
            context_chars = sum(len(source.content) for source in sources)

        request_id = str(uuid4())
        user_message_id = str(uuid4())
        assistant_id = str(uuid4())
        history = [
            {"role": message["role"], "content": message["content"]} for message in completed
        ] + [{"role": "user", "content": content}]
        estimate = (
            estimate_input_tokens(settings, history=history, sources=sources)
            + settings.max_output_tokens
            if settings.llm_configured
            else 0
        )
        if usage.tokens_used + usage.tokens_reserved + estimate > settings.daily_token_quota:
            raise AgentError("token_quota_exceeded", 429, retry_after=86400)

        usage.request_count += 1
        usage.active_request_id = request_id
        usage.active_request_expires_at = now + timedelta(
            seconds=max(int(ACTIVE_LEASE.total_seconds()), settings.llm_timeout_seconds + 30)
        )
        usage.tokens_reserved += estimate
        row.active_request_id = request_id
        row.active_request_expires_at = usage.active_request_expires_at
        row.last_seen_at = now
        row.expires_at = now + SESSION_TTL
        user_message = {
            "id": user_message_id,
            "role": "user",
            "content": content,
            "status": "completed",
            "client_request_id": str(client_request_id),
            "request_id": request_id,
            "citations": [],
            "created_at": now.isoformat(),
        }
        assistant_message = {
            "id": assistant_id,
            "role": "assistant",
            "content": "",
            "status": "pending",
            "request_id": request_id,
            "citations": [source.citation(index) for index, source in enumerate(sources, start=1)],
            "created_at": now.isoformat(),
            "input_tokens": 0,
            "output_tokens": 0,
            "estimated_usage": True,
            "reserved_tokens": estimate,
        }
        messages.extend([user_message, assistant_message])
        row.messages = messages
        return {
            "duplicate": False,
            "session_id": row.id,
            "user_id": user_id,
            "user_message": _safe_message(user_message),
            "assistant_message": _safe_message(assistant_message),
            "sources": sources,
            "history": history,
            "estimate": estimate,
        }


def _limit_sources(sources: tuple[RetrievedInformation, ...], max_chars: int):
    selected: list[RetrievedInformation] = []
    remaining = max_chars
    for source in sources:
        if remaining <= 0:
            break
        content = source.content[:remaining]
        selected.append(
            RetrievedInformation(
                id=source.id,
                title=source.title,
                source_url=source.source_url,
                platform=source.platform,
                source_id=source.source_id,
                published_at=source.published_at,
                activity_location=source.activity_location,
                activity_start_at=source.activity_start_at,
                activity_end_at=source.activity_end_at,
                registration_deadline_at=source.registration_deadline_at,
                content=content,
                score=source.score,
            )
        )
        remaining -= len(content)
    return tuple(selected)


def finish_request(
    factory: sessionmaker[Session],
    settings: AgentSettings,
    *,
    token: str,
    user_id: UUID,
    request_id: str,
    answer: str,
    status: str,
    input_tokens: int,
    output_tokens: int,
    estimated_usage: bool,
) -> None:
    now = datetime.now(UTC)
    with factory() as session, session.begin():
        # This is internal finalization, not an HTTP authorization path. It must
        # still settle a request after the login credential has been revoked.
        usage = session.scalar(
            select(AgentUserUsage).where(AgentUserUsage.user_id == user_id).with_for_update()
        )
        row = session.scalar(
            select(AgentSession)
            .where(
                AgentSession.token_hash == _token_hash(settings, token),
                AgentSession.user_id == user_id,
            )
            .with_for_update()
        )
        if usage is None or row is None:
            return  # Account deletion already removed both records.
        messages = deepcopy(row.messages or [])
        for message in messages:
            if message.get("request_id") == request_id and message.get("role") == "assistant":
                if message.get("status") != "pending":
                    return  # Duplicate cleanup must never debit twice.
                message.update(
                    content=answer,
                    status=status,
                    completed_at=now.isoformat(),
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    estimated_usage=estimated_usage,
                )
                reserved = int(message.pop("reserved_tokens", 0))
                if usage.active_request_id == request_id:
                    if usage.usage_day != now.date():
                        usage.usage_day = now.date()
                        usage.tokens_used = 0
                    usage.tokens_reserved = max(0, usage.tokens_reserved - reserved)
                    usage.tokens_used += (
                        input_tokens + output_tokens
                        if status == "completed"
                        else max(reserved, input_tokens + output_tokens)
                    )
                    usage.active_request_id = None
                    usage.active_request_expires_at = None
                break
        row.messages = messages
        if row.active_request_id == request_id:
            row.active_request_id = None
            row.active_request_expires_at = None


def rate_message(
    factory: sessionmaker[Session],
    settings: AgentSettings,
    *,
    token: str,
    user_id: UUID,
    message_id: UUID,
    rating: str | None,
) -> None:
    now = datetime.now(UTC)
    with factory() as session, session.begin():
        row = _session(session, settings, token, now, user_id)
        messages = deepcopy(row.messages or [])
        message = next(
            (
                item
                for item in messages
                if item.get("id") == str(message_id) and item.get("role") == "assistant"
            ),
            None,
        )
        if message is None or message.get("status") != "completed":
            raise AgentError("message_not_found", 404)
        message["rating"] = rating
        row.messages = messages


def close_session(
    factory: sessionmaker[Session], settings: AgentSettings, token: str, *, user_id: UUID
) -> None:
    now = datetime.now(UTC)
    with factory() as session, session.begin():
        row = _session(session, settings, token, now, user_id)
        if row.active_request_expires_at and row.active_request_expires_at > now:
            raise AgentError("user_request_in_progress", 429, retry_after=10)
        session.delete(row)
