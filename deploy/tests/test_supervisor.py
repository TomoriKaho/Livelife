import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import importlib.util
import os
import shlex
import signal
import tempfile
import time
import unittest

from livelife.supervisor import Supervisor


@unittest.skipUnless(importlib.util.find_spec("supervisor"), "requires supervisor==4.3.0 for process integration")
class SupervisorTests(unittest.TestCase):
    def test_restart_after_crash_and_idempotent_removal(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as root:
            supervisor = Supervisor(root, sys.executable)
            supervisor.ensure()
            try:
                command = shlex.join([sys.executable, "-c", "import time; time.sleep(300)"])
                supervisor.configure("test", command, root)
                first = int(supervisor.ctl("pid", "test").stdout.strip())
                self.assertGreater(first, 1)
                os.kill(first, signal.SIGKILL)
                deadline = time.monotonic() + 10
                second = first
                while time.monotonic() < deadline:
                    status = supervisor.ctl("pid", "test", check=False)
                    second = int(status.stdout.strip()) if status.stdout.strip().isdigit() else 0
                    if second > 1 and second != first:
                        break
                    time.sleep(0.2)
                self.assertGreater(second, 1)
                self.assertNotEqual(first, second)
                supervisor.remove("test")
                supervisor.remove("test")
                self.assertFalse((Path(root) / "programs/test.conf").exists())
            finally:
                supervisor.ctl("shutdown", check=False)
