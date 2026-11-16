"""Authenticated activity favorite operations; ownership never comes from client input."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from pydantic import AwareDatetime
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.accounts.router import get_current_user
from app.db.dependencies import get_session
from app.db.models.accounts import User
from app.db.models.favorite import ActivityFavorite
from app.schemas.favorite import (
    FavoriteIds,
    FavoriteItem,
    FavoriteMembership,
    FavoritePage,
    FavoriteStatus,
)
from app.services.favorites.service import (
    list_favorites,
    read_favorite,
    remove_favorite,
    save_favorite,
)

router = APIRouter(
    prefix="/favorites/activities",
    tags=["favorites"],
    responses={
        401: {"description": "登录凭证缺失、撤销或过期"},
        503: {"description": "数据库未配置"},
    },
)


@router.get("", response_model=FavoritePage)
def favorites(
    response: Response,
    status: FavoriteStatus | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    as_of: AwareDatetime | None = None,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    response.headers["Cache-Control"] = "no-store"
    return list_favorites(session, user.id, status, limit, offset, as_of or datetime.now(UTC))


@router.post("/status", response_model=FavoriteMembership)
def membership(
    payload: FavoriteIds,
    response: Response,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    response.headers["Cache-Control"] = "no-store"
    return FavoriteMembership(
        saved_ids=list(
            session.scalars(
                select(ActivityFavorite.information_id).where(
                    ActivityFavorite.user_id == user.id,
                    ActivityFavorite.information_id.in_(payload.ids),
                )
            )
        )
    )


@router.get(
    "/{target}", response_model=FavoriteItem, responses={404: {"description": "本人没有收藏该活动"}}
)
def read(
    target: UUID,
    response: Response,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    response.headers["Cache-Control"] = "no-store"
    return read_favorite(session, user.id, target)


@router.put(
    "/{target}",
    response_model=FavoriteItem,
    responses={404: {"description": "目标不存在、不是活动或是演示数据"}},
)
def save(
    target: UUID,
    response: Response,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    response.headers["Cache-Control"] = "no-store"
    return save_favorite(session, user.id, target)


@router.delete("/{target}", status_code=204)
def remove(
    target: UUID, user: User = Depends(get_current_user), session: Session = Depends(get_session)
):
    remove_favorite(session, user.id, target)
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
