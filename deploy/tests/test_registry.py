import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tempfile
import threading
import unittest
import sqlite3

from livelife.registry import Registry

A, B, C = "a" * 40, "b" * 40, "c" * 40


class Runtime:
    def __init__(self):
        self.running = {}
        self.routes = {}
        self.fail_start = False
        self.fail_publish = False
        self.fail_remove = False
        self.removed = []

    def port_available(self, port):
        return port not in self.running.values()

    def ensure(self, ident, commit, port, bundle):
        if self.fail_start:
            raise RuntimeError("candidate failed hello")
        self.running[ident] = port

    def health(self, port):
        if port not in self.running.values():
            raise RuntimeError("tunnel unavailable")

    def publish(self, routes):
        if self.fail_publish:
            self.fail_publish = False
            raise RuntimeError("invalid candidate Nginx config")
        self.routes = routes

    def remove(self, ident, port):
        if self.fail_remove:
            raise RuntimeError("course unreachable")
        self.running.pop(ident, None)
        self.removed.append(ident)


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.runtime = Runtime()
        self.now = 1000
        self.registry = Registry(self.directory.name, self.runtime, "https://192.144.253.40",
                                 grace=10, lease=100, slots=3, clock=lambda: self.now)

    def deploy(self, key, commit=A, generation=1):
        return self.registry.deploy(key, commit, generation, b"validated-bundle")

    def test_main_and_two_previews_have_distinct_ports(self):
        self.deploy("main", A)
        self.deploy("pr:40", B)
        self.deploy("pr:41", C)
        self.assertEqual(set(self.runtime.running.values()), {18000, 18001, 18002})
        self.assertEqual(self.runtime.routes["/api/staging/"]["sha"], A)

    def test_startup_intent_is_committed_before_external_start(self):
        original = self.runtime.ensure
        def ensure(ident, commit, port, bundle):
            # A separate connection sees only committed records. The candidate
            # must be reserved but must not appear as an active instance yet.
            with sqlite3.connect(self.registry.root / "registry.sqlite3") as db:
                self.assertEqual(db.execute("SELECT id, port FROM retirements").fetchall(), [(ident, port)])
                self.assertEqual(db.execute("SELECT id FROM instances").fetchall(), [])
            original(ident, commit, port, bundle)
        self.runtime.ensure = ensure
        self.deploy("main", A)
        self.assertEqual(self.registry.snapshot()["retirements"], [])

    def test_cross_pr_binding_pins_old_sha_while_pr_moves(self):
        self.deploy("pr:40", A)
        first = self.registry.bind("frontend:41", "pr:40", 1, C)
        self.deploy("pr:40", B, 2)
        self.assertEqual(self.registry.lookup("frontend:41"), first)
        self.assertEqual(self.registry.lookup("pr:40")["backend_sha"], B)
        self.assertEqual(self.runtime.routes["/api/pr-40/"]["sha"], B)
        self.registry.release("pr:40", 3)
        self.now += 11
        self.registry.collect()
        self.assertIn(f"be-{A}", self.runtime.running)
        self.assertNotIn(f"be-{B}", self.runtime.running)
        self.registry.release("frontend:41", 4)
        self.now += 11
        self.registry.collect()
        self.assertEqual(self.runtime.running, {})

    def test_main_is_permanent_and_default_frontend_follows_shared_main(self):
        self.deploy("main", A)
        self.registry.bind("frontend:41", "staging", 2, C)
        self.deploy("main", B, 3)
        self.now += 11
        self.registry.collect()
        self.assertEqual(self.registry.lookup("frontend:41")["backend_sha"], B)
        self.assertEqual(self.registry.lookup("main")["api_path"], "/api/staging/")
        with self.assertRaises(ValueError):
            self.registry.release("main", 4)

    def test_backend_pr_alone_keeps_backend_alive(self):
        self.deploy("pr:40", A)
        self.now += 10000
        self.registry.collect()
        self.assertIn(f"be-{A}", self.runtime.running)

    def test_failed_candidate_keeps_previous_sha_routes_and_ref(self):
        self.deploy("pr:40", A)
        original_routes = self.runtime.routes.copy()
        self.runtime.fail_start = True
        with self.assertRaises(RuntimeError):
            self.deploy("pr:40", B, 2)
        self.assertEqual(self.registry.lookup("pr:40")["backend_sha"], A)
        self.assertEqual(self.runtime.routes, original_routes)

    def test_failed_gateway_reload_rolls_back_and_removes_candidate(self):
        self.deploy("main", A)
        original_routes = self.runtime.routes.copy()
        self.runtime.fail_publish = True
        with self.assertRaises(RuntimeError):
            self.deploy("main", B, 2)
        self.assertEqual(self.runtime.routes, original_routes)
        self.assertEqual(self.registry.lookup("main")["backend_sha"], A)
        self.assertNotIn(f"be-{B}", self.runtime.running)

    def test_failed_candidate_cleanup_keeps_retryable_port_reservation(self):
        self.deploy("main", A)
        self.runtime.fail_start = True
        self.runtime.fail_remove = True
        with self.assertRaises(RuntimeError):
            self.deploy("main", B, 2)
        self.assertEqual(self.registry.lookup("main")["backend_sha"], A)
        self.assertEqual(self.registry.snapshot()["retirements"][0]["id"], "be-" + B)
        self.runtime.fail_start = False
        self.runtime.fail_remove = False
        self.registry.collect()
        self.assertEqual(self.registry.snapshot()["retirements"], [])

    def test_close_tombstone_rejects_late_build_and_reopen_recovers(self):
        self.deploy("pr:40", A, 10)
        self.registry.release("pr:40", 12)
        self.assertEqual(self.deploy("pr:40", B, 11)["status"], "superseded")
        self.assertEqual(self.deploy("pr:40", A, 13)["status"], "ready")

    def test_bind_is_idempotent_and_does_not_accumulate_counts(self):
        self.deploy("pr:40", A)
        for _ in range(3):
            self.registry.bind("frontend:41", "pr:40", 2, C)
        self.assertEqual(len(self.registry.snapshot()["refs"]), 2)
        self.registry.release("frontend:41", 3)
        self.registry.release("frontend:41", 3)
        self.assertEqual(len(self.registry.snapshot()["refs"]), 1)

    def test_unavailable_bind_preserves_previous_binding_without_fallback(self):
        self.deploy("main", A)
        original = self.registry.bind("frontend:41", "staging", 2, C)
        with self.assertRaises(ValueError):
            self.registry.bind("frontend:41", "pr:999", 3, C)
        self.assertEqual(self.registry.lookup("frontend:41"), original)

    def test_unreferenced_versions_get_a_fresh_grace_period_after_last_release(self):
        self.deploy("pr:40", A)
        self.registry.bind("frontend:41", "pr:40", 1)
        self.registry.release("pr:40", 2)
        self.now += 1000
        self.registry.release("frontend:41", 3)
        self.registry.collect()
        self.assertIn(f"be-{A}", self.runtime.running)
        self.now += 11
        self.registry.collect()
        self.assertNotIn(f"be-{A}", self.runtime.running)

    def test_unassociated_branch_lease_expires(self):
        self.deploy("branch:" + "d" * 32, A)
        self.now += 101
        self.registry.collect()
        self.assertIn(f"be-{A}", self.runtime.running)
        self.now += 11
        self.registry.collect()
        self.assertNotIn(f"be-{A}", self.runtime.running)

    def test_same_sha_is_shared_by_two_owners(self):
        self.deploy("pr:40", A)
        self.deploy("pr:41", A)
        self.assertEqual(len(self.runtime.running), 1)
        self.registry.release("pr:40", 2)
        self.now += 11
        self.registry.collect()
        self.assertIn(f"be-{A}", self.runtime.running)

    def test_pending_cleanup_reserves_port_and_retries(self):
        self.deploy("pr:40", A)
        self.registry.release("pr:40", 2)
        self.now += 11
        self.runtime.fail_remove = True
        with self.assertRaises(RuntimeError):
            self.registry.collect()
        self.deploy("pr:41", B)
        self.assertEqual(self.runtime.running[f"be-{B}"], 18001)
        with self.assertRaises(ValueError):
            self.deploy("pr:40", A, 3)
        self.runtime.fail_remove = False
        self.registry.collect()
        self.assertNotIn(f"be-{A}", self.runtime.running)

    def test_port_pool_exhaustion_is_explicit(self):
        self.deploy("main", A)
        self.deploy("pr:40", B)
        self.deploy("pr:41", C)
        with self.assertRaises(RuntimeError):
            self.deploy("pr:42", "d" * 40)

    def test_state_survives_new_manager_process(self):
        self.deploy("pr:40", A)
        registry = Registry(self.directory.name, self.runtime, "https://192.144.253.40")
        self.assertEqual(registry.lookup("pr:40")["backend_sha"], A)

    def test_concurrent_managers_do_not_allocate_the_same_port(self):
        errors = []
        ready = threading.Barrier(2)
        def worker(key, commit):
            try:
                registry = Registry(self.directory.name, self.runtime, "https://192.144.253.40")
                ready.wait(timeout=3)
                registry.deploy(key, commit, 1, b"source")
            except Exception as error:
                errors.append(error)
        threads = [threading.Thread(target=worker, args=("pr:40", A)),
                   threading.Thread(target=worker, args=("pr:41", B))]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)
        self.assertEqual(errors, [])
        self.assertEqual(len(set(self.runtime.running.values())), 2)

    def test_old_deploy_cannot_replace_newer_reference(self):
        self.deploy("pr:40", B, 20)
        self.assertEqual(self.deploy("pr:40", A, 19)["status"], "superseded")
        self.assertEqual(self.registry.lookup("pr:40")["backend_sha"], B)

    def test_input_cannot_escape_control_directories(self):
        for invalid in ("../../other", "main;shutdown", "pr:0", "frontend:1\ncommand=x"):
            with self.assertRaises(ValueError):
                self.deploy(invalid)
        with self.assertRaises(ValueError):
            self.deploy("pr:40", "$(echo x)")


if __name__ == "__main__":
    unittest.main()
