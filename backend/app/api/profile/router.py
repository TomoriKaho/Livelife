"""个人资料与兴趣标签路由。"""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.profile.deps import get_current_user_id
from app.db.dependencies import get_session
from app.db.models.profile import UserInterest, UserProfile
from app.schemas.profile import INTEREST_CATALOG, InterestTag, ProfileResponse, ProfileUpdate

router = APIRouter(prefix="/profile", tags=["profile"])

PROTECTED_RESPONSES = {
    401: {"description": "缺少、失效或过期的登录凭证"},
    503: {"description": "数据库未配置"},
}


def _profile_tags(session: Session, user_id: UUID) -> list[str]:
    selected = set(
        session.scalars(select(UserInterest.tag).where(UserInterest.user_id == user_id)).all()
    )
    return [tag for tag in INTEREST_CATALOG if tag in selected]


def _get_or_create_profile(session: Session, user_id: UUID) -> UserProfile:
    profile = session.get(UserProfile, user_id)
    if profile is not None:
        return profile

    profile = UserProfile(user_id=user_id, display_name="", bio="", updated_at=datetime.now(UTC))
    session.add(profile)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = session.get(UserProfile, user_id)
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Profile is unavailable",
            ) from None
        return existing
    return profile


def _to_response(session: Session, profile: UserProfile) -> ProfileResponse:
    return ProfileResponse(
        display_name=profile.display_name,
        bio=profile.bio,
        interests=_profile_tags(session, profile.user_id),
    )


@router.get("/interests", response_model=list[InterestTag])
def list_interests() -> list[InterestTag]:
    """公开的兴趣标签目录，供页面勾选。"""

    return [InterestTag(tag=tag, label=label) for tag, label in INTEREST_CATALOG.items()]


@router.get("/me", response_model=ProfileResponse, responses=PROTECTED_RESPONSES)
def read_profile(
    response: Response,
    session: Session = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
) -> ProfileResponse:
    response.headers["Cache-Control"] = "no-store"
    return _to_response(session, _get_or_create_profile(session, user_id))


@router.patch("/me", response_model=ProfileResponse, responses=PROTECTED_RESPONSES)
def update_profile(
    payload: ProfileUpdate,
    response: Response,
    session: Session = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
) -> ProfileResponse:
    tags = payload.interests
    if tags is not None:
        if len(set(tags)) != len(tags):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Duplicate interest tags",
            )
        if any(tag not in INTEREST_CATALOG for tag in tags):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unknown interest tag",
            )

    profile = _get_or_create_profile(session, user_id)
    if payload.display_name is not None:
        profile.display_name = payload.display_name
    if payload.bio is not None:
        profile.bio = payload.bio
    if tags is not None:
        session.execute(delete(UserInterest).where(UserInterest.user_id == user_id))
        session.add_all([UserInterest(user_id=user_id, tag=tag) for tag in tags])
    profile.updated_at = datetime.now(UTC)
    session.commit()
    response.headers["Cache-Control"] = "no-store"
    return _to_response(session, profile)
