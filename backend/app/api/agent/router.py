import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import aclosing
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials

from app.api.accounts.router import bearer, get_current_user
from app.core.config import get_agent_settings
from app.db.models.accounts import User
from app.db.session import Database
from app.services.accounts.auth import TEST_USER_ID, authenticated_user
from app.services.agent.llm import AgentModelError, estimate_input_tokens, stream_completion
from app.services.agent.schemas import (
    AgentRatingRequest,
    CreateSessionResponse,
    SendMessageRequest,
    SessionResponse,
)
from app.services.agent.service import (
    AgentError,
    begin_request,
    close_session,
    create_session,
    finish_request,
    get_history,
    rate_message,
)


def _agent_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> User:
    # Do not keep the auth dependency's read transaction/connection for the
    # lifetime of SSE; each subsequent stream check opens a short transaction.
    with _factory(request)() as session:
        user = get_current_user(request, credentials, session)
        if user.id == TEST_USER_ID:
            raise HTTPException(status_code=403, detail={"code": "verified_account_required"})
        return user


router = APIRouter(prefix="/agent", tags=["agent"])


def _factory(request: Request):
    database: Database = request.app.state.database
    if database.session_factory is None:
        raise HTTPException(status_code=503, detail={"code": "database_not_configured"})
    return database.session_factory


def _token(request: Request) -> str:
    token = request.headers.get("x-agent-session", "")
    if not token.strip():
        raise HTTPException(status_code=401, detail={"code": "session_token_required"})
    return token.strip()


def _raise_agent_error(error: AgentError) -> None:
    headers = {"Retry-After": str(error.retry_after)} if error.retry_after is not None else None
    raise HTTPException(
        status_code=error.status_code,
        detail={"code": error.code},
        headers=headers,
    ) from error


def _sse(event: str, data: dict) -> str:
    return (
        f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, separators=(',', ':'))}\n\n"
    )


def _public_message(message: dict) -> dict:
    return {
        "id": message["id"],
        "role": message["role"],
        "content": message["content"],
        "status": message["status"],
        "citations": message.get("citations", []),
        "rating": message.get("rating"),
        "created_at": message["created_at"],
    }


@router.post("/sessions", response_model=CreateSessionResponse, status_code=status.HTTP_201_CREATED)
def new_session(request: Request, user: User = Depends(_agent_user)):
    try:
        return create_session(
            _factory(request), get_agent_settings(), _client_ip(request), user_id=user.id
        )
    except AgentError as error:
        _raise_agent_error(error)


@router.get("/sessions/current", response_model=SessionResponse)
def current_session(request: Request, user: User = Depends(_agent_user)):
    try:
        result = get_history(
            _factory(request), get_agent_settings(), _token(request), user_id=user.id
        )
        result["messages"] = [_public_message(message) for message in result["messages"]]
        return result
    except AgentError as error:
        _raise_agent_error(error)


@router.post("/sessions/close", status_code=status.HTTP_204_NO_CONTENT)
def end_session(request: Request, user: User = Depends(_agent_user)):
    try:
        close_session(_factory(request), get_agent_settings(), _token(request), user_id=user.id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except AgentError as error:
        _raise_agent_error(error)


@router.post("/messages/{message_id}/rating", status_code=status.HTTP_204_NO_CONTENT)
def submit_rating(
    message_id: UUID,
    payload: AgentRatingRequest,
    request: Request,
    user: User = Depends(_agent_user),
):
    if payload.rating not in {None, "like", "dislike"}:
        raise HTTPException(status_code=422, detail={"code": "invalid_rating"})
    try:
        rate_message(
            _factory(request),
            get_agent_settings(),
            token=_token(request),
            user_id=user.id,
            message_id=message_id,
            rating=payload.rating,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except AgentError as error:
        _raise_agent_error(error)


def _client_ip(request: Request) -> str:
    # Uvicorn's ProxyHeadersMiddleware only trusts forwarded headers from its
    # configured proxy addresses. Never parse X-Forwarded-For directly here.
    return request.client.host if request.client else "unknown"


@router.post("/messages/stream")
async def send_message(
    request: Request, payload: SendMessageRequest, user: User = Depends(_agent_user)
):
    factory = _factory(request)
    settings = get_agent_settings()
    token = _token(request)
    try:
        state = begin_request(
            factory,
            settings,
            token=token,
            user_id=user.id,
            content=payload.content,
            client_request_id=payload.client_request_id,
            ip=_client_ip(request),
        )
    except AgentError as error:
        _raise_agent_error(error)

    timed_out = False

    async def events() -> AsyncIterator[str]:
        if state["duplicate"]:
            _, assistant = state["messages"]
            yield _sse(
                "message_start",
                {"message_id": assistant["id"], "request_id": assistant.get("request_id")},
            )
            for citation in assistant.get("citations", []):
                yield _sse("citation", citation)
            if assistant.get("content"):
                yield _sse("delta", {"text": assistant["content"]})
            if assistant.get("input_tokens") is not None:
                yield _sse(
                    "usage",
                    {
                        "input_tokens": assistant.get("input_tokens", 0),
                        "output_tokens": assistant.get("output_tokens", 0),
                        "estimated": assistant.get("estimated_usage", True),
                    },
                )
            yield _sse("done", {"message_id": assistant["id"], "status": "completed"})
            return

        assistant = state["assistant_message"]
        request_id = assistant["request_id"]
        answer = ""
        input_tokens = 0
        output_tokens = 0
        estimated = True
        finalized = False
        yield _sse("message_start", {"message_id": assistant["id"], "request_id": request_id})
        for citation in assistant["citations"]:
            yield _sse("citation", citation)

        try:
            if not state["sources"] and not settings.llm_configured:
                answer = "我目前没有找到足够的公开资料来回答这个问题。"
                yield _sse("delta", {"text": answer})
            elif not settings.llm_configured:
                raise AgentModelError("model_not_configured")
            else:
                async with aclosing(
                    stream_completion(settings, history=state["history"], sources=state["sources"])
                ) as completion:
                    async for text, usage in completion:
                        if text:
                            answer += text
                            yield _sse("delta", {"text": text})
                        if usage:
                            input_tokens = usage["input_tokens"]
                            output_tokens = usage["output_tokens"]
                            estimated = False
                if not answer.strip():
                    raise AgentModelError("model_empty_response")
                if estimated:
                    input_tokens = estimate_input_tokens(
                        settings, history=state["history"], sources=state["sources"]
                    )
                    output_tokens = len(answer) // 4

            finish_request(
                factory,
                settings,
                token=token,
                user_id=user.id,
                request_id=request_id,
                answer=answer,
                status="completed",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                estimated_usage=estimated,
            )
            finalized = True
            yield _sse(
                "usage",
                {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "estimated": estimated,
                },
            )
            yield _sse("done", {"message_id": assistant["id"], "status": "completed"})
        except AgentModelError as error:
            finish_request(
                factory,
                settings,
                token=token,
                user_id=user.id,
                request_id=request_id,
                answer=answer,
                status="failed",
                input_tokens=0,
                output_tokens=0,
                estimated_usage=True,
            )
            finalized = True
            yield _sse("error", {"code": str(error), "retryable": True})
        except asyncio.CancelledError:
            raise
        except Exception:
            finish_request(
                factory,
                settings,
                token=token,
                user_id=user.id,
                request_id=request_id,
                answer=answer,
                status="failed",
                input_tokens=0,
                output_tokens=0,
                estimated_usage=True,
            )
            finalized = True
            yield _sse("error", {"code": "agent_internal_error", "retryable": True})
        finally:
            if not finalized:
                try:
                    finish_request(
                        factory,
                        settings,
                        token=token,
                        user_id=user.id,
                        request_id=request_id,
                        answer=answer,
                        status="failed" if timed_out else "cancelled",
                        input_tokens=0,
                        output_tokens=0,
                        estimated_usage=True,
                    )
                except Exception:
                    pass

    account_token = request.headers.get("authorization", "").partition(" ")[2].strip()

    def still_authenticated() -> bool:
        with factory() as db:
            current = authenticated_user(db, account_token)
            return current is not None and current.id == user.id and current.id != TEST_USER_ID

    async def guarded_events() -> AsyncIterator[str]:
        nonlocal timed_out
        deadline = asyncio.get_running_loop().time() + settings.llm_timeout_seconds
        stream = events()
        pending = None

        def settle_cancelled() -> None:
            if not state["duplicate"]:
                finish_request(
                    factory,
                    settings,
                    token=token,
                    user_id=user.id,
                    request_id=state["assistant_message"]["request_id"],
                    answer="",
                    status="failed" if timed_out else "cancelled",
                    input_tokens=0,
                    output_tokens=0,
                    estimated_usage=True,
                )

        async def deadline_watchdog() -> None:
            nonlocal timed_out
            await asyncio.sleep(settings.llm_timeout_seconds)
            timed_out = True
            # Independent of downstream reads: a stalled client must not keep
            # the provider connection alive beyond the concurrency lease.
            if pending is not None:
                pending.cancel()
                await asyncio.gather(pending, return_exceptions=True)
            await stream.aclose()
            settle_cancelled()

        watchdog = asyncio.create_task(deadline_watchdog())
        try:
            while True:
                remaining = deadline - asyncio.get_running_loop().time()
                if timed_out or remaining <= 0:
                    timed_out = True
                    yield _sse("error", {"code": "model_timeout", "retryable": True})
                    return
                if not still_authenticated():
                    yield _sse("error", {"code": "authentication_required", "retryable": False})
                    return
                if pending is None:
                    pending = asyncio.create_task(anext(stream))
                done, _ = await asyncio.wait({pending}, timeout=min(1, remaining))
                if not done or timed_out:
                    continue
                if not still_authenticated():
                    yield _sse("error", {"code": "authentication_required", "retryable": False})
                    return
                try:
                    event = pending.result()
                except StopAsyncIteration:
                    return
                pending = None
                if event.startswith(("event: done\n", "event: error\n")):
                    watchdog.cancel()
                yield event
        finally:
            if not timed_out:
                watchdog.cancel()
            await asyncio.gather(watchdog, return_exceptions=True)
            if pending is not None:
                pending.cancel()
                await asyncio.gather(pending, return_exceptions=True)
            await stream.aclose()
            # Covers revocation/disconnect before the generator entered its try.
            settle_cancelled()

    return StreamingResponse(
        guarded_events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
