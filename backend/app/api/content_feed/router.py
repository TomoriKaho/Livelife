from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.db.dependencies import get_session
from app.schemas.content_feed import ContentPage, ContentQuery
from app.services.content.feed import list_articles

router = APIRouter(prefix="/content", tags=["content"])


@router.get(
    "/articles", response_model=ContentPage, responses={503: {"description": "数据库未配置"}}
)
def articles(
    response: Response,
    session: Annotated[Session, Depends(get_session)],
    query: Annotated[ContentQuery, Query()],
) -> ContentPage:
    response.headers["Cache-Control"] = "no-store"
    return list_articles(session, query)
