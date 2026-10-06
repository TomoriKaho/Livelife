import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import fcntl
import importlib.util
import tempfile
import threading
import unittest

from livelife.registry import Registry

spec = importlib.util.spec_from_file_location("smoke", Path(__file__).resolve().parents[1] / "smoke-servers.py")
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)

A, B = "a" * 40, "b" * 40


class Runtime:
    def __init__(self):
        self.running = {}
        self.routes = {}
        self.restore_probe = None

    def port_available(self, port):
        return port not in self.running.values()

    def ensure(self, ident, commit, port, bundle):
        self.running[ident] = port

    def publish(self, routes):
        if not routes and self.restore_probe:
            self.restore_probe()
        self.routes = routes

    def remove(self, ident, port):
        self.running.pop(ident, None)


class SmokeTests(unittest.TestCase):
    def exercise_concurrent_main(self, fail):
        with tempfile.TemporaryDirectory() as root:
            runtime = Runtime()
            actual = Registry(Path(root) / "actual", runtime, "https://example.test")
            started, done = threading.Event(), threading.Event()
            errors = []
            def deploy():
                started.set()
                try:
                    peer = Registry(actual.root, runtime, "https://example.test")
                    peer.deploy("main", B, 1, b"source")
                except Exception as error:
                    errors.append(error)
                finally:
                    done.set()
            def check_lock():
                # Check the kernel lock deterministically, including when the
                # real route restoration is published by the guard's finally.
                with (actual.root / "manager.lock").open("a") as probe:
                    with self.assertRaises(BlockingIOError):
                        fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
            thread = threading.Thread(target=deploy)
            caught = False
            try:
                with smoke.exclusive_gateway(actual):
                    runtime.restore_probe = check_lock
                    isolated = Registry(Path(root) / "smoke", runtime, "https://example.test", grace=0)
                    isolated.deploy("branch:" + "1" * 32, A, 1, b"source")
                    thread.start()
                    self.assertTrue(started.wait(timeout=3))
                    check_lock()
                    self.assertFalse(done.wait(timeout=0.1))
                    try:
                        if fail:
                            raise RuntimeError("smoke assertion failed")
                    finally:
                        isolated.release("branch:" + "1" * 32, 2)
                        isolated.collect()
            except RuntimeError as error:
                self.assertEqual(str(error), "smoke assertion failed")
                caught = True
            finally:
                if thread.ident is not None:
                    thread.join(timeout=5)
            self.assertEqual(caught, fail)
            self.assertFalse(thread.is_alive())
            self.assertEqual(errors, [])
            self.assertEqual(actual.lookup("main")["backend_sha"], B)
            self.assertEqual(runtime.routes["/api/staging/"]["sha"], B)
            self.assertEqual(runtime.running, {"be-" + B: 18000})

    def test_concurrent_deployment_waits_until_smoke_cleanup_and_restore(self):
        self.exercise_concurrent_main(False)

    def test_failed_smoke_also_preserves_the_waiting_main_deployment(self):
        self.exercise_concurrent_main(True)

    def test_smoke_refuses_existing_instances_or_pending_cleanup(self):
        for pending in (False, True):
            with self.subTest(pending=pending), tempfile.TemporaryDirectory() as root:
                runtime = Runtime()
                actual = Registry(root, runtime, "https://example.test")
                if pending:
                    with actual.locked() as db:
                        db.execute("INSERT INTO retirements VALUES (?, ?)", ("be-" + A, 18000))
                else:
                    actual.deploy("main", A, 1, b"source")
                original = runtime.routes.copy()
                with self.assertRaisesRegex(RuntimeError, "no real instances or pending cleanup"):
                    with smoke.exclusive_gateway(actual):
                        self.fail("occupied gateway should not enter smoke")
                self.assertEqual(runtime.routes, original)


if __name__ == "__main__":
    unittest.main()
