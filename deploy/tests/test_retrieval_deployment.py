"""RAG opt-in, publication gate, worker cleanup and real snapshot recovery."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "deploy"))
from livelife import retrieval_config as config, retrieval_runtime as runtime
from livelife.embedding_runtime import environment
from livelife.build_runner import backend_check_groups
from livelife.common import atomic_json

SERVICE = "embedding-" + "a" * 16
SETTINGS = {"source_sha": "b" * 40, "model": config.MODEL, "revision": config.REVISION,
            "dimensions": 1024, "port": 19073, "threads": 4, "key": "c" * 64}


def configure(root, *, branches=None):
    service = root / "embedding" / SERVICE
    service.mkdir(parents=True, mode=0o700)
    atomic_json(service / "service.json", SETTINGS)
    (service / "service.json").chmod(0o600)
    credentials = root / "credentials"
    credentials.mkdir(mode=0o700)
    path = credentials / "retrieval.json"
    atomic_json(path, {"branches": branches or ["topic"], "service": SERVICE})
    path.chmod(0o600)
    return path


class RetrievalDeploymentTests(unittest.TestCase):
    def test_server_branch_opt_in_and_secret_separation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.assertEqual(config.load(root, "topic"), {})
            configure(root)
            self.assertEqual(config.load(root, "other"), {})
            env = config.load(root, "topic")
            self.assertEqual(env["RETRIEVAL_MODE"], "hybrid")
            self.assertEqual(env["EMBEDDING_API_KEY"], SETTINGS["key"])
            with patch.dict(os.environ, {"AGENT_LLM_API_KEY": "private", "SMTP_PASSWORD": "private",
                                         "DATABASE_URL": "private", "HF_TOKEN": "private"}):
                model_env = environment(root, SERVICE, SETTINGS)
            for key in ("AGENT_LLM_API_KEY", "SMTP_PASSWORD", "DATABASE_URL", "HF_TOKEN"):
                self.assertNotIn(key, model_env)
            self.assertEqual(model_env["HF_HUB_OFFLINE"], "1")

    def test_invalid_private_configuration_is_not_silently_disabled(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = configure(root)
            for invalid in ({"branches": "topic", "service": SERVICE},
                            {"branches": ["topic"], "service": "../../secrets"},
                            {"branches": ["topic"], "service": SERVICE, "unexpected": "secret"}):
                path.write_text(json.dumps(invalid))
                with self.assertRaisesRegex(ValueError, "invalid retrieval configuration"):
                    config.load(root, "topic")
            path.unlink()
            path.symlink_to(root / "embedding" / SERVICE / "service.json")
            with self.assertRaises(ValueError):
                config.load(root, "topic")

    def test_full_index_gate_failure_and_profile_change(self):
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp)
            def reply(python, backend, env, operation, **kwargs):
                return {"profile": "one"} if operation == "status" else {"ready": True}
            with patch.object(runtime, "command", side_effect=reply) as call:
                runtime.prepare("python", state, {}, state)
                self.assertEqual([c.args[3] for c in call.call_args_list],
                                 ["status", "reconcile", "sync", "check"])
            with patch.object(runtime, "command", return_value={"profile": "two"}) as call:
                with self.assertRaisesRegex(RuntimeError, "profile changed"):
                    runtime.prepare("python", state, {}, state)
                self.assertEqual(call.call_count, 1)
            with patch.object(runtime, "command", side_effect=[
                {"profile": "one"}, {}, subprocess.CalledProcessError(1, "sync")
            ]):
                with self.assertRaises(subprocess.CalledProcessError):
                    runtime.prepare("python", state, {}, state)

    def test_worker_crash_and_exception_cleanup(self):
        process = MagicMock()
        process.poll.return_value = None
        with patch.object(runtime.subprocess, "Popen", return_value=process):
            with self.assertRaisesRegex(RuntimeError, "API failed"):
                with runtime.worker("python", Path("/backend"), {}, Path("/state")):
                    raise RuntimeError("API failed")
        process.terminate.assert_called_once()
        api, worker = MagicMock(), MagicMock()
        api.poll.return_value = None
        worker.poll.return_value = 1
        with self.assertRaisesRegex(RuntimeError, "worker exited"):
            runtime.wait(api, worker)

    def test_postgres_ci_opt_in_preserves_old_release_checks(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.assertEqual(backend_check_groups(root), [])
            (root / "backend").mkdir()
            atomic_json(root / "backend/preview-runtime.json", {"retrieval_checks": True})
            self.assertEqual(backend_check_groups(root), ["--group", "local-db"])

    def test_installer_does_not_publish_config_on_failed_model_probe(self):
        spec = importlib.util.spec_from_file_location("install_retrieval", REPO / "deploy/install-retrieval.py")
        installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(installer)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with (patch.object(installer.subprocess, "check_output", return_value="b" * 40),
                  patch.object(installer, "extract_source") as extract,
                  patch.object(installer.subprocess, "run"),
                  patch.object(installer, "Supervisor"),
                  patch.object(installer.socket, "socket"),
                  patch.object(installer, "probe", side_effect=RuntimeError("offline")),
                  patch.object(installer.time, "monotonic", side_effect=[0, 999])):
                def source(_archive, destination):
                    (destination / "backend/app").mkdir(parents=True)
                    (destination / "backend/app/embedding_server.py").touch()
                extract.side_effect = source
                with self.assertRaisesRegex(RuntimeError, "startup failed"):
                    installer.install(root, REPO, "b" * 40, 19073, ["topic"])
            self.assertFalse((root / "credentials/retrieval.json").exists())

    def test_installer_reuses_immutable_model_and_publishes_only_after_probe(self):
        spec = importlib.util.spec_from_file_location("install_retrieval", REPO / "deploy/install-retrieval.py")
        installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(installer)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            def source(_archive, destination):
                (destination / "backend/app").mkdir(parents=True)
                (destination / "backend/app/embedding_server.py").touch()
            def probe(settings):
                self.assertFalse((root / "credentials/retrieval.json").exists())
            with (patch.object(installer.subprocess, "check_output", return_value="b" * 40),
                  patch.object(installer, "extract_source", side_effect=source),
                  patch.object(installer.subprocess, "run") as run,
                  patch.object(installer, "Supervisor"),
                  patch.object(installer.socket, "socket"),
                  patch.object(installer, "probe", side_effect=probe) as check,
                  patch.dict(os.environ, {"AGENT_LLM_API_KEY": "private", "DATABASE_URL": "private"})):
                first = installer.install(root, REPO, "b" * 40, 19073, ["topic"])
                self.assertEqual(run.call_count, 2)
                for call in run.call_args_list:
                    self.assertNotIn("AGENT_LLM_API_KEY", call.kwargs["env"])
                    self.assertNotIn("DATABASE_URL", call.kwargs["env"])
                key = config.load(root, "topic")["EMBEDDING_API_KEY"]
                check.side_effect = None
                second = installer.install(root, REPO, "b" * 40, 19073, ["main", "topic"])
                self.assertEqual(first["service"], second["service"])
                self.assertEqual(run.call_count, 2)
                self.assertEqual(config.load(root, "main")["EMBEDDING_API_KEY"], key)


@unittest.skipUnless(os.environ.get("LIVELIFE_RAG_INTEGRATION") == "1", "opt-in real RAG PostgreSQL")
class RealRetrievalDeploymentTests(unittest.TestCase):
    def test_public_snapshot_backfill_index_gate_and_worker_takeover(self):
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        from pgembed import get_server
        import psycopg
        from livelife import branch_database as databases
        from livelife.backend_runtime import prepare_schema, runtime_environment

        class Encoder(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                if self.path != "/v1/embeddings":
                    self.send_error(404)
                    return
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                payload = {"data": [{"index": i, "embedding": [1., 0., 0.]}
                                    for i in range(len(body["input"]))]}
                data = json.dumps(payload).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Encoder)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        with tempfile.TemporaryDirectory(prefix="rag-deploy-") as temp:
            root = Path(temp)
            main = {"id": databases.branch_id("main"), "branch": "main", "source": None,
                    "source_branch": "main"}
            child = {"id": databases.branch_id("topic"), "branch": "topic", "source": main["id"],
                     "source_branch": "main"}
            backend, python = REPO / "backend", Path(sys.executable)

            def env_for(pg, state):
                env = runtime_environment(pg.get_uri(database="postgres").replace(
                    "postgresql://", "postgresql+psycopg://", 1), "be-" + "a" * 40, state)
                return {**env, "RETRIEVAL_MODE": "hybrid", "EMBEDDING_DIMENSIONS": "3",
                        "EMBEDDING_MODEL_REVISION": "fixture", "EMBEDDING_BASE_URL":
                        f"http://127.0.0.1:{server.server_port}/v1"}

            def migrate(pg, state):
                prepare_schema(python, backend, env_for(pg, state))

            with databases.prepared_database(root, main, get_server, migrate) as (pg, state):
                with psycopg.connect(pg.get_uri(database="postgres")) as conn:
                    conn.execute("""INSERT INTO information_items
                        (id, platform, source_id, content, raw_content, raw_payload,
                         fetched_at, first_fetched_at, processed_at)
                        VALUES ('00000000-0000-0000-0000-000000000001', 'manual', 'rag-test',
                                '图书馆续借办理指引', '图书馆续借办理指引', '{}',
                                now(), now(), now())""")
                runtime.prepare(python, backend, env_for(pg, state), state)
                with databases.prepared_database(root, child, get_server, migrate) as (fork, fork_state):
                    env = env_for(fork, fork_state)
                    before = runtime.command(python, backend, env, "status")
                    self.assertEqual(before["records"], 1)
                    self.assertEqual(before["missing_states"], 1)
                    runtime.prepare(python, backend, env, fork_state)
                    self.assertTrue(runtime.command(python, backend, env, "check")["ready"])
                    # Run the actual launcher and API. The model endpoint is a
                    # test fixture; no chat/SMTP service or credentials are used.
                    import socket
                    import psutil
                    from livelife.course import check_health
                    ident = databases.release_id("a" * 40, "topic")
                    release = root / "releases" / ident
                    release.mkdir(parents=True)
                    (release / "backend").symlink_to(backend, target_is_directory=True)
                    (release / ".venv").symlink_to(sys.prefix, target_is_directory=True)
                    atomic_json(release / "release.json", {"database": child})
                    for port in range(18000, 18064):
                        try:
                            with socket.socket() as sock:
                                sock.bind(("127.0.0.1", port))
                            break
                        except OSError:
                            continue
                    else:
                        self.fail("no isolated preview API test port available")
                    script = """
import json, sys
from pathlib import Path
from pgembed import get_server
from livelife import backend_runtime
backend_runtime.retrieval_environment = lambda *_: json.loads(sys.argv[4])
sys.exit(backend_runtime.run(Path(sys.argv[1]), sys.argv[2], int(sys.argv[3]), server_factory=get_server))
"""
                    rag_env = {k: v for k, v in env.items() if k.startswith(("EMBEDDING_", "RETRIEVAL_"))}
                    with (root / "runtime-test.log").open("w") as log:
                        process = subprocess.Popen(
                            [str(python), "-c", script, str(root), ident, str(port), json.dumps(rag_env)],
                            cwd=REPO, env={"PATH": os.environ["PATH"], "HOME": str(root),
                                          "PYTHONPATH": str(REPO / "deploy")}, stdout=log, stderr=log,
                        )
                        try:
                            check_health(port, timeout=30, require_database=True)
                            children = psutil.Process(process.pid).children()
                            indexer = next(p for p in children if "app.retrieval" in p.cmdline())
                            api = next(p for p in children if "app.main:app" in p.cmdline())
                            indexer.terminate()
                            self.assertNotEqual(process.wait(timeout=20), 0)
                            _, alive = psutil.wait_procs([api, indexer], timeout=5)
                            self.assertEqual(alive, [])
                        finally:
                            runtime.stop(process)
                    # An invalid model endpoint blocks publishing even with a complete index.
                    with self.assertRaises(subprocess.CalledProcessError):
                        runtime.command(python, backend, {**env, "EMBEDDING_BASE_URL":
                                                         f"http://127.0.0.1:{server.server_port}/wrong"}, "check")
                    import fcntl
                    import time
                    lock_path = fork_state / "retrieval/worker.lock"
                    with runtime.worker(python, backend, env, fork_state) as first:
                        end = time.monotonic() + 10
                        with lock_path.open("a") as lock:
                            while True:
                                try:
                                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                                    fcntl.flock(lock, fcntl.LOCK_UN)
                                except BlockingIOError:
                                    break
                                self.assertLess(time.monotonic(), end)
                                time.sleep(0.1)
                        with runtime.worker(python, backend, env, fork_state) as second:
                            runtime.stop(first)
                            with psycopg.connect(fork.get_uri(database="postgres")) as conn:
                                conn.execute("UPDATE information_items SET content='更新后的图书借阅办法'")
                            end = time.monotonic() + 15
                            while runtime.command(python, backend, env, "status")["pending"]:
                                self.assertIsNone(second.poll())
                                self.assertLess(time.monotonic(), end)
                                time.sleep(0.2)
                    self.assertTrue(runtime.command(python, backend, env, "check")["ready"])
