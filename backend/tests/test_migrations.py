from io import StringIO
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from app.db.models import Base

BACKEND = Path(__file__).resolve().parents[1]


def test_migration_upgrade_matches_models_and_downgrade_removes_table():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    config = Config(str(BACKEND / "alembic.ini"))
    try:
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            context = MigrationContext.configure(connection)
            assert compare_metadata(context, Base.metadata) == []
            command.downgrade(config, "base")
            assert not (
                {
                    "information_items",
                    "users",
                    "email_verification_codes",
                    "user_sessions",
                    "agent_sessions",
                    "agent_ip_windows",
                }
                & set(inspect(connection).get_table_names())
            )
            command.upgrade(config, "head")
            assert {
                "information_items",
                "users",
                "email_verification_codes",
                "user_sessions",
                "agent_sessions",
                "agent_ip_windows",
            } <= set(inspect(connection).get_table_names())
    finally:
        engine.dispose()


def test_postgresql_migration_can_be_generated_offline(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://example@localhost/example")
    output = StringIO()
    config = Config(str(BACKEND / "alembic.ini"), output_buffer=output)
    command.upgrade(config, "head", sql=True)
    sql = output.getvalue()
    assert "CREATE TABLE information_items" in sql
    assert "CREATE TABLE users" in sql
    assert "CREATE TABLE email_verification_codes" in sql
    assert "CREATE TABLE user_sessions" in sql
    assert "CREATE TABLE agent_sessions" in sql
    assert "CREATE TABLE agent_ip_windows" in sql
    assert "TIMESTAMP WITH TIME ZONE" in sql
    assert "UNIQUE (platform, source_id)" in sql
    assert "id UUID NOT NULL" in sql


def test_migration_requires_explicit_database_configuration(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    config = Config(str(BACKEND / "alembic.ini"))
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        command.upgrade(config, "head")
