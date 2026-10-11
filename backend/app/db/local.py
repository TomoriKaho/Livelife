"""Project-owned PostgreSQL for local development only."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url

BACKEND = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = BACKEND / ".local" / "postgres"
# Serialize migration and database creation across local launchers using this cluster.
MIGRATION_LOCK = 6020261011


def upgrade_local_database(url: URL) -> None:
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": MIGRATION_LOCK})
            connection.commit()
            try:
                config = Config(str(BACKEND / "alembic.ini"))
                config.attributes["connection"] = connection
                command.upgrade(config, "head")
                connection.commit()
            finally:
                connection.rollback()
                connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": MIGRATION_LOCK})
                connection.commit()
    finally:
        engine.dispose()


def create_local_database(server_url: URL) -> URL:
    engine = create_engine(server_url, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": MIGRATION_LOCK})
            try:
                exists = connection.scalar(
                    text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": "livelife"}
                )
                if not exists:
                    connection.execute(text('CREATE DATABASE "livelife"'))
            finally:
                connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": MIGRATION_LOCK})
    finally:
        engine.dispose()
    return server_url.set(database="livelife")


@contextmanager
def local_database(data_dir: Path = DEFAULT_DATA_DIR) -> Iterator[str]:
    # Import lazily: ordinary API startup and unit tests do not need local-db binaries.
    try:
        from pgembed import get_server
    except ImportError as exc:
        raise RuntimeError(
            "Local PostgreSQL is missing. Run: uv run --group local-db python -m app.dev"
        ) from exc

    data_dir = data_dir.expanduser().resolve()
    data_dir.parent.mkdir(parents=True, exist_ok=True)
    with get_server(data_dir, cleanup_mode="stop") as server:
        server_url = make_url(server.get_uri()).set(drivername="postgresql+psycopg")
        url = create_local_database(server_url)
        upgrade_local_database(url)
        yield url.render_as_string(hide_password=False)
