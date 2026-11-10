import hmac
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.dependencies import get_session
from app.db.models.accounts import EmailVerificationCode, User, UserSession
from app.db.models.profile import UserInterest, UserProfile
from app.schemas.accounts import (
    AccountDeletionRequest,
    EmailRequest,
    LoginRequest,
    RegistrationRequest,
    SessionResponse,
    UserResponse,
)
from app.services.accounts.auth import (
    CODE_MAX_ATTEMPTS,
    code_digest,
    create_session,
    get_test_user,
    issue_code,
    password_hash,
    test_login_enabled,
    token_digest,
    utcnow,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["accounts"])
bearer = HTTPBearer(auto_error=False)
GENERIC_CODE_MESSAGE = "If the address can be registered, a verification code will be sent."


@router.post("/email-codes", status_code=status.HTTP_202_ACCEPTED)
def send_email_code(
    payload: EmailRequest, session: Session = Depends(get_session)
) -> dict[str, str]:
    if session.scalar(select(User.id).where(User.email == payload.email)) is not None:
        return {"message": GENERIC_CODE_MESSAGE}
    try:
        if not issue_code(session, payload.email):
            return {"message": GENERIC_CODE_MESSAGE}
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=503, detail="Email delivery is unavailable") from exc
    return {"message": GENERIC_CODE_MESSAGE}


@router.post("/register", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegistrationRequest,
    response: Response,
    session: Session = Depends(get_session),
) -> SessionResponse:
    if session.scalar(select(User.id).where(User.email == payload.email)) is not None:
        raise HTTPException(status_code=409, detail="Email is already registered")
    code_record = session.scalar(
        select(EmailVerificationCode)
        .where(
            EmailVerificationCode.email == payload.email,
            EmailVerificationCode.consumed_at.is_(None),
            EmailVerificationCode.expires_at > utcnow(),
            EmailVerificationCode.attempts < CODE_MAX_ATTEMPTS,
        )
        .order_by(EmailVerificationCode.created_at.desc())
    )
    if code_record is None:
        raise HTTPException(status_code=400, detail="Verification code is invalid or expired")
    if not hmac.compare_digest(code_record.code_hash, code_digest(payload.code, code_record.salt)):
        code_record.attempts += 1
        session.commit()
        raise HTTPException(status_code=400, detail="Verification code is invalid or expired")

    now = utcnow()
    code_record.consumed_at = now
    user = User(
        id=uuid4(),
        email=payload.email,
        password_hash=password_hash(payload.password),
        created_at=now,
    )
    session.add(user)
    try:
        session.flush()
        token, expires_in = create_session(session, user, remember=False)
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Email is already registered") from exc
    response.headers["Cache-Control"] = "no-store"
    return SessionResponse(
        access_token=token, expires_in=expires_in, user=UserResponse.model_validate(user)
    )


@router.post("/login", response_model=SessionResponse)
def login(
    payload: LoginRequest,
    response: Response,
    session: Session = Depends(get_session),
) -> SessionResponse:
    if not payload.email and not payload.password:
        if not test_login_enabled():
            raise HTTPException(status_code=403, detail="Test login is disabled")
        user = get_test_user(session)
    else:
        user = session.scalar(select(User).where(User.email == payload.email))
        valid = (
            verify_password(payload.password, user.password_hash)
            if user
            else verify_password(
                payload.password, "scrypt$00000000000000000000000000000000$" + "00" * 64
            )
        )
        if user is None or not valid:
            raise HTTPException(status_code=401, detail="Email or password is incorrect")
    token, expires_in = create_session(session, user, payload.remember)
    response.headers["Cache-Control"] = "no-store"
    return SessionResponse(
        access_token=token, expires_in=expires_in, user=UserResponse.model_validate(user)
    )


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    session: Session = Depends(get_session),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_session = session.scalar(
        select(UserSession).where(
            UserSession.token_hash == token_digest(credentials.credentials),
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > datetime.now(UTC),
        )
    )
    user = session.get(User, user_session.user_id) if user_session else None
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Session is invalid or expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    request.state.user = user
    return user


@router.get("/me", response_model=UserResponse)
def me(response: Response, user: User = Depends(get_current_user)) -> UserResponse:
    response.headers["Cache-Control"] = "no-store"
    return UserResponse.model_validate(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    session: Session = Depends(get_session),
    _user: User = Depends(get_current_user),
) -> Response:
    if credentials is not None:
        record = session.scalar(
            select(UserSession).where(
                UserSession.token_hash == token_digest(credentials.credentials)
            )
        )
        if record is not None:
            record.revoked_at = datetime.now(UTC)
            session.commit()
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    payload: AccountDeletionRequest,
    response: Response,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> Response:
    """注销账号：密码二次确认后删除账户及其会话、资料与验证码。"""

    if not user.password_hash.startswith("scrypt$") or not verify_password(
        payload.password, user.password_hash
    ):
        raise HTTPException(status_code=400, detail="Password is incorrect")
    session.execute(delete(UserSession).where(UserSession.user_id == user.id))
    session.execute(delete(UserInterest).where(UserInterest.user_id == user.id))
    session.execute(delete(UserProfile).where(UserProfile.user_id == user.id))
    session.execute(delete(EmailVerificationCode).where(EmailVerificationCode.email == user.email))
    session.delete(user)
    session.commit()
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
