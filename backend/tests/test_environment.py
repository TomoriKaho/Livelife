"""Configuration loading must be fixed-path, early and safe for injected settings."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from app.core import environment

BACKEND = Path(__file__).resolve().parents[1]


def test_missing_file_does_not_search_working_directory(tmp_path, monkeypatch):
    monkeypatch.delenv("PYTHON_DOTENV_DISABLED", raising=False)
    monkeypatch.delenv("SMTP_HOST", raising=False)
    (tmp_path / ".env").write_text("SMTP_HOST=wrong-working-directory\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(environment, "BACKEND_ENV", tmp_path / "missing" / ".env")
    environment.load_backend_environment()
    assert "SMTP_HOST" not in os.environ


def test_bom_file_loads_values_but_keeps_process_environment(tmp_path, monkeypatch):
    monkeypatch.delenv("PYTHON_DOTENV_DISABLED", raising=False)
    path = tmp_path / ".env"
    path.write_text(
        'SMTP_HOST=smtp.example.test\nSMTP_PORT=587\nSMTP_PASSWORD="fake # value"\n',
        encoding="utf-8-sig",
    )
    monkeypatch.setattr(environment, "BACKEND_ENV", path)
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    monkeypatch.setenv("SMTP_PORT", "465")
    environment.load_backend_environment()
    assert os.environ["SMTP_HOST"] == "smtp.example.test"
    assert os.environ["SMTP_PASSWORD"] == "fake # value"
    assert os.environ["SMTP_PORT"] == "465"


def test_injected_database_and_empty_environment_values_are_preserved(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text("DATABASE_URL=file-database\nSMTP_HOST=file-host\n", encoding="utf-8")
    monkeypatch.setattr(environment, "BACKEND_ENV", path)
    monkeypatch.delenv("PYTHON_DOTENV_DISABLED", raising=False)
    monkeypatch.setenv("DATABASE_URL", "injected-database")
    monkeypatch.setenv("SMTP_HOST", "")
    environment.load_backend_environment()
    assert os.environ["DATABASE_URL"] == "injected-database"
    assert os.environ["SMTP_HOST"] == ""


def test_api_dev_and_alembic_read_same_backend_file_from_another_cwd(tmp_path):
    checkout = tmp_path / "backend"
    shutil.copytree(BACKEND / "app", checkout / "app", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(
        BACKEND / "migrations",
        checkout / "migrations",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    shutil.copy(BACKEND / "alembic.ini", checkout)
    database = tmp_path / "isolated.db"
    (checkout / ".env").write_text(
        f"SMTP_HOST=smtp.example.test\nSMTP_PASSWORD=test-only-not-logged\n"
        f"DATABASE_URL=sqlite+pysqlite:///{database.as_posix()}\n",
        encoding="utf-8",
    )
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / ".env").write_text("SMTP_HOST=wrong-working-directory\n", encoding="utf-8")
    # Never pass developer/provider credentials into a test child or a failure
    # traceback. Only OS/runtime essentials are needed by these local checks.
    allowed = (
        "PATH",
        "SYSTEMROOT",
        "WINDIR",
        "TEMP",
        "TMP",
        "HOME",
        "LANG",
        "LC_ALL",
        "LD_LIBRARY_PATH",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
    )
    env = {key: os.environ[key] for key in allowed if key in os.environ}
    env["PYTHONPATH"] = str(checkout)
    script = """
import json, os
from app import dev
from app.main import create_app
from sqlalchemy.engine import make_url
app = create_app()
assert make_url(dev.get_database_url()) == app.state.database.engine.url
print(json.dumps({'smtp_host': os.environ['SMTP_HOST'],
                  'configured': app.state.database.configured}))
app.state.database.close()
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=elsewhere,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout) == {"smtp_host": "smtp.example.test", "configured": True}
    assert "test-only-not-logged" not in result.stdout + result.stderr
    migration = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(checkout / "alembic.ini"), "upgrade", "head"],
        cwd=elsewhere,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert database.exists()
    assert "test-only-not-logged" not in migration.stdout + migration.stderr
