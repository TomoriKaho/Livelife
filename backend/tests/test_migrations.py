from io import StringIO
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text

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


def test_place_upgrade_preserves_existing_ids_and_information_links():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    config = Config(str(BACKEND / "alembic.ini"))
    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))
        config.attributes["connection"] = connection
        command.upgrade(config, "0002_information_places")
        connection.execute(
            text(
                "INSERT INTO information_places(id,name,longitude,latitude) "
                "VALUES ('old-map-id','旧地点',116.30,39.99)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO information_items "
                "(id,platform,source_id,content,raw_content,raw_payload,place_id,"
                "fetched_at,first_fetched_at,processed_at) VALUES "
                "('12345678123456781234567812345678','manual','old','原文','原文','{}',"
                "'old-map-id','2026-11-11','2026-11-11','2026-11-11')"
            )
        )
        command.upgrade(config, "head")
        assert connection.execute(
            text("SELECT id, building_id, campus FROM information_places")
        ).one() == ("old-map-id", "old-map-id", "北京大学燕园")
        assert connection.execute(
            text("SELECT place_id, location_resolution FROM information_items")
        ).one() == ("old-map-id", None)
        command.downgrade(config, "0002_information_places")
        assert connection.scalar(text("SELECT place_id FROM information_items")) == "old-map-id"
    engine.dispose()
