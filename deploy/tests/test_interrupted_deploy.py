import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import importlib.util
import json
import os
import shlex
import signal
import subprocess
import tempfile
import unittest

from livelife.common import atomic_json
from livelife.registry import Registry
from livelife.supervisor import Supervisor

A, B, C = "a" * 40, "b" * 40, "c" * 40


class ProcessRuntime:
    """Real supervised child processes and a file-backed simulated gateway."""
    def __init__(self, root, crash_stage=None):
        self.root = Path(root)
        self.supervisor = Supervisor(self.root / "supervisor", sys.executable)
        self.crash_stage = crash_stage

    def port_available(self, port):
        # Sleepers don't bind sockets: allocation must use durable DB records.
        return True

    def ensure(self, ident, commit, port, bundle):
        command = shlex.join([sys.executable, "-c", "import time; time.sleep(300)"])
        self.supervisor.configure(ident, command, self.root)
        if commit == B and self.crash_stage == "start":
            os.kill(os.getpid(), signal.SIGKILL)

    def publish(self, routes):
        atomic_json(self.root / "routes.json", routes)
        if self.crash_stage == "publish" and any(row["sha"] == B for row in routes.values()):
            os.kill(os.getpid(), signal.SIGKILL)

    def remove(self, ident, port):
        self.supervisor.remove(ident)


@unittest.skipUnless(importlib.util.find_spec("supervisor"), "requires supervisor==4.3.0 for crash integration")
class InterruptedDeployTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(dir="/tmp", prefix="livelife-crash-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.runtime = ProcessRuntime(self.root)
        self.runtime.supervisor.ensure()
        self.addCleanup(self.runtime.supervisor.ctl, "shutdown", check=False)
        self.registry = Registry(self.root / "state", self.runtime, "https://example.test")
        self.registry.deploy("main", A, 1, b"source")

    def exercise_crash(self, stage):
        original_pid = int(self.runtime.supervisor.ctl("pid", "be-" + A).stdout)
        worker = subprocess.run([sys.executable, str(Path(__file__).resolve()),
                                 "--crash", str(self.root), stage],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(worker.returncode, -signal.SIGKILL, worker.stderr)
        candidate_pid = int(self.runtime.supervisor.ctl("pid", "be-" + B).stdout)
        self.assertGreater(candidate_pid, 0)
        snapshot = self.registry.snapshot()
        self.assertEqual(snapshot["retirements"], [{"id": "be-" + B, "port": 18001}])
        self.assertEqual(self.registry.lookup("main")["backend_sha"], A)
        self.assertEqual([row["sha"] for row in snapshot["instances"]], [A])
        if stage == "publish":
            self.assertEqual(json.loads((self.root / "routes.json").read_text())["/api/staging/"]["sha"], B)

        # A different candidate cannot reuse the interrupted candidate's port,
        # even though port_available() says all sockets are available.
        self.registry.deploy("pr:41", C, 1, b"source")
        self.assertEqual(next(row["port"] for row in self.registry.snapshot()["instances"] if row["sha"] == C), 18002)
        self.registry.recover()
        self.registry.collect()
        self.assertEqual(self.registry.snapshot()["retirements"], [])
        self.assertEqual(json.loads((self.root / "routes.json").read_text())["/api/staging/"]["sha"], A)
        self.assertEqual(int(self.runtime.supervisor.ctl("pid", "be-" + A).stdout), original_pid)
        with self.assertRaises(ProcessLookupError):
            os.kill(candidate_pid, 0)
        self.assertFalse((self.runtime.supervisor.programs / ("be-" + B + ".conf")).exists())
        self.registry.collect()  # Repeat cleanup is safe for the retained main.
        self.assertEqual(self.registry.lookup("main")["backend_sha"], A)

    def test_sigkill_after_start_is_recoverable_without_losing_main(self):
        self.exercise_crash("start")

    def test_sigkill_after_publish_before_commit_restores_old_main(self):
        self.exercise_crash("publish")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--crash"]:
        root = Path(sys.argv[2])
        runtime = ProcessRuntime(root, sys.argv[3])
        Registry(root / "state", runtime, "https://example.test").deploy("main", B, 2, b"source")
    else:
        unittest.main()
