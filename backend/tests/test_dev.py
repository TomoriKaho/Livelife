import os
import sys
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from app import dev
from app.db import local


def test_launcher_rejects_external_database_before_starting_local_server(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://example@localhost/external")

    def unexpected_start(*args):
        pytest.fail("Must not start or migrate a local database with external configuration")

    monkeypatch.setattr(dev, "local_database", unexpected_start)
    with pytest.raises(RuntimeError, match="DATABASE_URL is already set"):
        with dev.development_database(tmp_path):
            pass
    assert os.environ["DATABASE_URL"].endswith("/external")


@pytest.mark.parametrize("existing", [None, "  "])
def test_launcher_sets_database_before_api_and_restores_environment(
    monkeypatch, tmp_path, existing
):
    if existing is None:
        monkeypatch.delenv("DATABASE_URL", raising=False)
    else:
        monkeypatch.setenv("DATABASE_URL", existing)
    events = []

    @contextmanager
    def fake_database(path):
        assert path == tmp_path
        events.append("database_ready")
        try:
            yield "postgresql+psycopg://postgres@127.0.0.1:12345/livelife"
        finally:
            events.append("database_stopped")

    def fake_uvicorn(app, **options):
        assert app == "app.main:app"
        assert options["port"] == 18000
        assert options["host"] == "127.0.0.1"
        assert options["reload"] is True
        assert os.environ["DATABASE_URL"].endswith("/livelife")
        events.append("api_started")
        raise KeyboardInterrupt

    monkeypatch.setattr(dev, "local_database", fake_database)
    monkeypatch.setattr(dev.uvicorn, "run", fake_uvicorn)
    dev.main(["--data-dir", str(tmp_path), "--port", "18000", "--reload"])
    assert events == ["database_ready", "api_started", "database_stopped"]
    assert os.environ.get("DATABASE_URL") == existing


def test_failed_migration_stops_database_before_api_can_start(monkeypatch, tmp_path):
    events = []

    @contextmanager
    def fake_server(path, *, cleanup_mode):
        assert path == tmp_path
        assert cleanup_mode == "stop"
        events.append("start")
        try:
            yield SimpleNamespace(get_uri=lambda: "postgresql://postgres@localhost:12345/postgres")
        finally:
            events.append("stop")

    def fail_migration(url):
        assert url.drivername == "postgresql+psycopg"
        events.append("migration_failed")
        raise RuntimeError("migration failed")

    monkeypatch.setitem(sys.modules, "pgembed", SimpleNamespace(get_server=fake_server))
    monkeypatch.setattr(local, "create_local_database", lambda url: url.set(database="livelife"))
    monkeypatch.setattr(local, "upgrade_local_database", fail_migration)
    with pytest.raises(RuntimeError, match="migration failed"):
        with local.local_database(tmp_path):
            pytest.fail("Must not hand out a database before migrations succeed")
    assert events == ["start", "migration_failed", "stop"]


def test_missing_optional_binaries_explain_required_command(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "pgembed", None)
    with pytest.raises(RuntimeError, match="uv run --group local-db"):
        with local.local_database(tmp_path):
            pass


def test_real_local_postgresql_migrates_persists_and_stops(request, tmp_path):
    if not request.config.getoption("--local-postgres"):
        pytest.skip("Use --local-postgres with the local-db dependency group")
    import psutil
    from sqlalchemy import text

    from app.db.session import Database
    from app.schemas.information import InformationInput
    from app.services.content import InformationAggregator, InformationProvider

    data_dir = tmp_path / "postgres"
    with local.local_database(data_dir) as url:
        database = Database(url)
        try:
            database.check_connection()
            with database.engine.connect() as connection:
                assert connection.scalar(text("SELECT version()")).startswith("PostgreSQL")
                assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
                    "0001_information"
                )
            with database.session_factory() as session:
                saved = InformationAggregator(session).ingest(
                    [
                        InformationInput(
                            platform="manual",
                            source_id="restart",
                            content="重启测试",
                            fetched_at="2026-10-11T12:00:00+08:00",
                        )
                    ]
                )[0]
            pid = int((data_dir / "postmaster.pid").read_text().splitlines()[0])
        finally:
            database.close()
    assert not psutil.pid_exists(pid)
    assert (data_dir / "PG_VERSION").exists()

    with local.local_database(data_dir) as url:
        database = Database(url)
        try:
            with database.session_factory() as session:
                record = InformationProvider(session).get(saved.id)
                assert record is not None
                assert record.content == "重启测试"
            pid = int((data_dir / "postmaster.pid").read_text().splitlines()[0])
        finally:
            database.close()
    assert not psutil.pid_exists(pid)
