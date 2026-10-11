from collections.abc import Generator

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db.session import Database


def get_session(request: Request) -> Generator[Session, None, None]:
    database: Database = request.app.state.database
    if database.session_factory is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not configured",
        )

    with database.session_factory() as session:
        yield session
