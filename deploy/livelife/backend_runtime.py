"""Supervised preview API with a private, persistent PostgreSQL per source SHA."""

import argparse
import json
import os
import secrets
import signal
import subprocess
import sys
from pathlib import Path

from .common import atomic_json, instance
from .mail_config import load as mail_environment

# Run using the tested release interpreter, never import branch code into the
# control interpreter. Validate both the revision and actual mapped columns.
SCHEMA_CHECK = """
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, select
from app.core.config import get_database_url
from app.db.models import Base
engine = create_engine(get_database_url())
try:
    with engine.connect() as connection:
        expected = set(ScriptDirectory.from_config(Config('alembic.ini')).get_heads())
        actual = set(MigrationContext.configure(connection).get_current_heads())
        if not expected or actual != expected:
            raise RuntimeError('Database revision does not match this release')
        for table in Base.metadata.sorted_tables:
            connection.execute(select(table).limit(0))
finally:
    engine.dispose()
"""


def state_directory(root, ident):
    root = Path(root).resolve()
    ident = instance(ident)
    base = root / "databases"
    directory = base / ident
    if (
        base.is_symlink()
        or directory.is_symlink()
        or (directory / "postgres").is_symlink()
    ):
        raise ValueError("preview database directory must not be a symlink")
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    base.chmod(0o700)
    directory.chmod(0o700)
    return directory


def runtime_environment(url, ident, state):
    # A stable per-version test secret allows Agent session recovery. No inherited
    # SMTP, provider, deployment, or DATABASE_URL credentials reach a branch.
    settings = state / "runtime.json"
    if not settings.exists():
        atomic_json(settings, {"agent_session_secret": secrets.token_hex(32)})
    if settings.is_symlink():
        raise ValueError("preview runtime settings must not be a symlink")
    secret = json.loads(settings.read_text())["agent_session_secret"]
    if not isinstance(secret, str) or len(secret) < 32:
        raise ValueError("invalid preview session secret")
    settings.chmod(0o600)
    allowed = (
        "PATH",
        "HOME",
        "LANG",
        "LC_ALL",
        "LD_LIBRARY_PATH",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "TMPDIR",
    )
    env = {key: os.environ[key] for key in allowed if key in os.environ}
    env.update(
        DATABASE_URL=url,
        AGENT_SESSION_SECRET=secret,
        LIVELIFE_BACKEND_SHA=ident[3:],
        PYTHONUNBUFFERED="1",
        AUTH_TEST_LOGIN_ENABLED="false",
    )
    return env


def prepare_schema(python, backend, env):
    if not (backend / "alembic.ini").is_file():
        raise RuntimeError("preview backend requires Alembic migrations")
    subprocess.run(
        [str(python), "-m", "alembic", "upgrade", "head"],
        cwd=backend,
        env=env,
        check=True,
        timeout=120,
    )
    subprocess.run(
        [str(python), "-c", SCHEMA_CHECK], cwd=backend, env=env, check=True, timeout=30
    )


def run(root, ident, port, *, server_factory=None):
    root = Path(root).resolve()
    ident = instance(ident)
    if not isinstance(port, int) or not 18000 <= port < 18064:
        raise ValueError("preview port is outside 18000..18063")
    release = root / "releases" / ident
    backend = release / "backend"
    python = (
        release / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    )
    if not python.is_file() or not (backend / "app/main.py").is_file():
        raise RuntimeError("tested preview backend is missing")
    mail = mail_environment(root)
    if server_factory is None:
        if os.name != "posix" or os.geteuid() == 0:
            raise RuntimeError("preview PostgreSQL requires an ordinary Linux user")
        from pgembed import get_server

        server_factory = get_server
    state = state_directory(root, ident)
    process = None
    previous_handlers = {}

    def terminate(_signal, _frame):
        # Raising also cancels a migration wait. The finally block stops its
        # child before leaving the PostgreSQL context and retaining the data.
        raise KeyboardInterrupt

    try:
        for number in (signal.SIGTERM, signal.SIGINT):
            previous_handlers[number] = signal.signal(number, terminate)
        with server_factory(state / "postgres", cleanup_mode="stop") as server:
            url = server.get_uri(database="postgres").replace(
                "postgresql://", "postgresql+psycopg://", 1
            )
            env = runtime_environment(url, ident, state)
            prepare_schema(python, backend, env)
            process = subprocess.Popen(
                [
                    str(python),
                    "-m",
                    "uvicorn",
                    "app.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                    "--root-path",
                    f"/api/versions/{ident}",
                ],
                cwd=backend,
                # SMTP is explicitly opted in on the server, only for the API.
                # Migration/schema subprocesses keep the credential-free env.
                env={**env, **mail},
            )
            try:
                return process.wait()
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
    except KeyboardInterrupt:
        return 0
    finally:
        for number, handler in previous_handlers.items():
            signal.signal(number, handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--instance", required=True)
    parser.add_argument("--port", required=True, type=int)
    args = parser.parse_args()
    try:
        return run(args.root, args.instance, args.port)
    except ImportError:
        print(
            "Preview dependencies missing; install pgembed==0.2.0 in control-venv.",
            file=sys.stderr,
        )
        return 1
    except (
        RuntimeError,
        ValueError,
        KeyError,
        OSError,
        subprocess.SubprocessError,
    ):
        # Detailed migration failures are already in this instance's log; don't
        # print environment dictionaries or connection strings via RPC errors.
        print(
            "Preview backend preparation failed; inspect the instance log.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
