"""Preview database startup, failure gates and optional real PostgreSQL checks."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from livelife import backend_runtime as runtime
from livelife import mail_config
from livelife.course import Course, check_health

A, B = "be-" + "a" * 40, "be-" + "b" * 40
REPO = Path(__file__).resolve().parents[2]


class PreviewRuntimeTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "posix", "requires Unix symlinks")
    def test_database_symlink_cannot_reuse_an_external_cluster(self):
        with (
            tempfile.TemporaryDirectory() as root,
            tempfile.TemporaryDirectory() as external,
        ):
            state = runtime.state_directory(root, A)
            marker = Path(external) / "keep"
            marker.write_text("external data")
            (state / "postgres").symlink_to(external, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink"):
                runtime.state_directory(root, A)
            self.assertEqual(marker.read_text(), "external data")

    def test_state_and_session_secret_survive_restart_but_are_isolated_by_sha(self):
        with tempfile.TemporaryDirectory() as root:
            first = runtime.state_directory(root, A)
            (first / "keep").write_text("persisted")
            other = runtime.state_directory(root, B)
            with patch.dict(
                os.environ,
                {
                    "DATABASE_URL": "private",
                    "SMTP_PASSWORD": "private",
                    "GH_TOKEN": "private",
                    "AGENT_LLM_API_KEY": "private",
                    "AUTH_TEST_LOGIN_ENABLED": "true",
                },
            ):
                env = runtime.runtime_environment("preview-url", A, first)
            again = runtime.runtime_environment("preview-url", A, first)
            self.assertEqual(env["AGENT_SESSION_SECRET"], again["AGENT_SESSION_SECRET"])
            self.assertNotEqual(
                env["AGENT_SESSION_SECRET"],
                runtime.runtime_environment("other", B, other)["AGENT_SESSION_SECRET"],
            )
            self.assertEqual(env["DATABASE_URL"], "preview-url")
            self.assertEqual(env["AUTH_TEST_LOGIN_ENABLED"], "false")
            for key in ("SMTP_PASSWORD", "GH_TOKEN", "AGENT_LLM_API_KEY"):
                self.assertNotIn(key, env)
            self.assertEqual((first / "keep").read_text(), "persisted")
            with self.assertRaises(ValueError):
                runtime.state_directory(root, "../../shared")

    def test_migration_and_schema_validation_both_gate_startup(self):
        with tempfile.TemporaryDirectory() as directory:
            backend = Path(directory)
            (backend / "alembic.ini").touch()
            with patch.object(runtime.subprocess, "run") as run:
                runtime.prepare_schema("python", backend, {"DATABASE_URL": "test"})
                self.assertEqual(
                    run.call_args_list[0].args[0],
                    ["python", "-m", "alembic", "upgrade", "head"],
                )
                self.assertIn("MigrationContext", run.call_args_list[1].args[0][-1])
                self.assertTrue(
                    all(call.kwargs["check"] for call in run.call_args_list)
                )
            with patch.object(
                runtime.subprocess,
                "run",
                side_effect=subprocess.CalledProcessError(1, "alembic"),
            ) as run:
                with self.assertRaises(subprocess.CalledProcessError):
                    runtime.prepare_schema("python", backend, {})
                self.assertEqual(run.call_count, 1)

    def exercise_runtime(self, failure=None, interrupted=False, mail=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            release = root / "releases" / A
            (release / "backend/app").mkdir(parents=True)
            (release / "backend/app/main.py").touch()
            python = (
                release
                / ".venv"
                / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            )
            python.parent.mkdir(parents=True)
            python.touch()
            if mail is not None:
                mail_config.save(root, mail)
            events = []

            @contextmanager
            def server_factory(path, cleanup_mode):
                self.assertEqual(cleanup_mode, "stop")
                self.assertEqual(path, root / "databases" / A / "postgres")
                events.append("database_start")
                try:
                    yield MagicMock(
                        get_uri=lambda **_: "postgresql://postgres@/postgres"
                    )
                finally:
                    events.append("database_stop")

            child = MagicMock()
            child.wait.side_effect = [KeyboardInterrupt(), 0] if interrupted else [9]
            child.poll.return_value = None if interrupted else 9
            with (
                patch.object(runtime, "prepare_schema", side_effect=failure) as schema,
                patch.object(runtime.subprocess, "Popen", return_value=child) as launch,
            ):
                if failure:
                    with self.assertRaises(RuntimeError):
                        runtime.run(root, A, 18000, server_factory=server_factory)
                    launch.assert_not_called()
                else:
                    self.assertEqual(
                        runtime.run(root, A, 18000, server_factory=server_factory),
                        0 if interrupted else 9,
                    )
                    self.assertEqual(
                        launch.call_args.kwargs["env"]["DATABASE_URL"],
                        "postgresql+psycopg://postgres@/postgres",
                    )
                    schema.assert_called_once()
                    for key in mail_config.FIELDS:
                        self.assertNotIn(key, schema.call_args.args[2])
                        if mail and key in mail:
                            self.assertEqual(
                                launch.call_args.kwargs["env"][key], mail[key]
                            )
                        else:
                            self.assertNotIn(key, launch.call_args.kwargs["env"])
                self.assertEqual(events, ["database_start", "database_stop"])
                self.assertTrue((root / "databases" / A / "runtime.json").exists())
                if interrupted:
                    child.terminate.assert_called_once()

    def test_failed_migration_stops_database_without_launching_api(self):
        self.exercise_runtime(failure=RuntimeError("migration failed"))

    def test_api_exit_stops_database_and_propagates_failure(self):
        self.exercise_runtime()

    def test_signal_stops_api_before_database_cleanup(self):
        self.exercise_runtime(interrupted=True)

    def test_server_mail_configuration_reaches_api_but_not_migrations(self):
        self.exercise_runtime(
            mail={
                "SMTP_HOST": "smtp.example.invalid",
                "SMTP_PORT": "465",
                "SMTP_FROM": "sender@example.invalid",
                "SMTP_USERNAME": "test-user",
                "SMTP_PASSWORD": "test-only-password",
            }
        )

    def test_hello_success_cannot_hide_unconfigured_database(self):
        hello = MagicMock()
        hello.__enter__.return_value = hello
        hello.status = 200
        hello.read.return_value = b'{"message":"hello world"}'
        with (
            patch(
                "livelife.course.urllib.request.urlopen",
                side_effect=[
                    hello,
                    urllib.error.HTTPError("ready", 503, "unconfigured", {}, None),
                ],
            ),
            patch("livelife.course.time.sleep"),
            patch("livelife.course.time.monotonic", side_effect=[0, 0, 2]),
            self.assertRaisesRegex(RuntimeError, "health check failed"),
        ):
            check_health(18000, timeout=1, require_database=True)

    def test_course_uses_trusted_launcher_and_recycling_preserves_database(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            course = Course(root)
            release = course.releases / A
            release.mkdir()
            (release / "release.json").write_text(
                json.dumps({"sha": A[3:], "port": 18000, "runtime_mode": "postgres-v1"})
            )
            state = runtime.state_directory(root, A)
            (state / "keep").write_text("data")
            course.supervisor = MagicMock()
            with patch("livelife.course.check_health") as health:
                course.handle(
                    {"op": "ensure", "instance": A, "sha": A[3:], "port": 18000}
                )
                health.assert_called_once_with(
                    18000, timeout=180, require_database=True
                )
            self.assertIn(
                "control-venv/bin/python -m livelife.backend_runtime",
                course.supervisor.configure.call_args.args[1],
            )
            course.handle({"op": "remove", "instance": A})
            self.assertFalse(release.exists())
            self.assertEqual((state / "keep").read_text(), "data")


@unittest.skipUnless(
    os.environ.get("LIVELIFE_PREVIEW_DB_INTEGRATION") == "1" and os.name == "posix",
    "requires opt-in Linux environment with pgembed and backend dependencies",
)
class RealPreviewDatabaseTests(unittest.TestCase):
    def test_login_persists_across_runtime_restart_and_schema_failure_blocks_api(self):
        import psutil

        if os.geteuid() == 0:
            self.skipTest(
                "run as an ordinary user; tests must not create system accounts"
            )
        with tempfile.TemporaryDirectory(prefix="livelife-db-") as directory:
            root = Path(directory).resolve()
            release = root / "releases" / A
            backend = release / "backend"
            backend.mkdir(parents=True)
            for name in ("app", "migrations"):
                shutil.copytree(
                    REPO / "backend" / name,
                    backend / name,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
                )
            shutil.copy(REPO / "backend/alembic.ini", backend)
            (release / ".venv").symlink_to(sys.prefix, target_is_directory=True)
            port = next(p for p in range(18000, 18064) if self.port_available(p))
            env = dict(os.environ, PYTHONPATH=str(REPO / "deploy"))
            command = [
                sys.executable,
                "-m",
                "livelife.backend_runtime",
                "--root",
                str(root),
                "--instance",
                A,
                "--port",
                str(port),
            ]
            token = None
            for turn in range(2):
                with tempfile.TemporaryFile() as log:
                    process = subprocess.Popen(command, env=env, stdout=log, stderr=log)
                    try:
                        check_health(port, timeout=60, require_database=True)
                        if token is None:
                            # Seed a real isolated account; public previews must
                            # never depend on the removed blank-login shortcut.
                            api = next(
                                child
                                for child in psutil.Process(process.pid).children()
                                if "uvicorn" in child.cmdline()
                            )
                            subprocess.run(
                                [
                                    sys.executable,
                                    "-c",
                                    """
from uuid import uuid4
from app.db.session import Database
from app.db.models.accounts import User
from app.services.accounts.auth import password_hash, utcnow
db = Database.from_environment()
with db.session_factory() as session, session.begin():
    session.add(User(id=uuid4(), email='preview-test@stu.pku.edu.cn',
                    password_hash=password_hash('isolated-test-password'), created_at=utcnow()))
db.close()
""",
                                ],
                                cwd=backend,
                                env=api.environ(),
                                check=True,
                            )
                            blank = urllib.request.Request(
                                f"http://127.0.0.1:{port}/auth/login",
                                data=b'{"email":"","password":""}',
                                headers={"Content-Type": "application/json"},
                            )
                            with self.assertRaises(urllib.error.HTTPError) as rejected:
                                urllib.request.urlopen(blank, timeout=5)
                            self.assertEqual(rejected.exception.code, 403)
                            req = urllib.request.Request(
                                f"http://127.0.0.1:{port}/auth/login",
                                data=b'{"email":"preview-test@stu.pku.edu.cn","password":"isolated-test-password"}',
                                headers={"Content-Type": "application/json"},
                            )
                            with urllib.request.urlopen(req, timeout=5) as response:
                                token = json.load(response)["access_token"]
                        req = urllib.request.Request(
                            f"http://127.0.0.1:{port}/auth/me",
                            headers={"Authorization": f"Bearer {token}"},
                        )
                        with urllib.request.urlopen(req, timeout=5) as response:
                            self.assertEqual(
                                json.load(response)["email"],
                                "preview-test@stu.pku.edu.cn",
                            )
                        pid = int(
                            (root / "databases" / A / "postgres/postmaster.pid")
                            .read_text()
                            .splitlines()[0]
                        )
                    except Exception:
                        log.seek(0)
                        print(log.read().decode(errors="replace")[-4000:])
                        raise
                    finally:
                        process.terminate()
                        process.wait(timeout=20)
                    self.assertFalse(psutil.pid_exists(pid))
                self.assertTrue(
                    (root / "databases" / A / "postgres/PG_VERSION").exists()
                )
                # After the first migration, add a required mapped column without
                # a migration: SQL connectivity alone must not promote this API.
                if turn == 1:
                    model = backend / "app/db/models/accounts.py"
                    model.write_text(
                        model.read_text().replace(
                            '__tablename__ = "users"',
                            '__tablename__ = "users"\n    missing: Mapped[str] = mapped_column(String(32))',
                        )
                    )
            with tempfile.TemporaryFile() as log:
                failed = subprocess.Popen(command, env=env, stdout=log, stderr=log)
                self.assertNotEqual(failed.wait(timeout=45), 0)
                log.seek(0)
                self.assertIn("users.missing", log.read().decode(errors="replace"))
            # A closed server may leave TIME_WAIT sockets: check that the API
            # cannot accept connections, rather than requiring immediate bind.
            with self.assertRaises(urllib.error.URLError):
                urllib.request.urlopen(f"http://127.0.0.1:{port}/test/hello", timeout=1)

    @staticmethod
    def port_available(port):
        import socket

        with socket.socket() as sock:
            try:
                sock.bind(("127.0.0.1", port))
                return True
            except OSError:
                return False
