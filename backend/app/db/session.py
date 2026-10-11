from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_database_url


class Database:
    def __init__(self, database_url: str | None) -> None:
        self.engine: Engine | None = (
            create_engine(database_url, pool_pre_ping=True) if database_url else None
        )
        self.session_factory: sessionmaker[Session] | None = (
            sessionmaker(bind=self.engine, autoflush=False, expire_on_commit=False)
            if self.engine
            else None
        )

    @classmethod
    def from_environment(cls) -> "Database":
        return cls(get_database_url())

    @property
    def configured(self) -> bool:
        return self.engine is not None

    def check_connection(self) -> None:
        if self.engine is None:
            raise RuntimeError("Database is not configured")
        with self.engine.connect() as connection:
            connection.execute(text("SELECT 1"))

    def close(self) -> None:
        if self.engine is not None:
            self.engine.dispose()
