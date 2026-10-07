"""Real Git-like child processes exercise timeout cleanup without network."""

from pathlib import Path
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from livelife.build_runner import run_fetch


class FetchTests(unittest.TestCase):
    def test_timeout_stops_child_and_removes_only_new_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = """import os,signal,subprocess,sys,time
from pathlib import Path
root=Path(sys.argv[1])
(root/'shallow.lock').write_text('incomplete fetch')
child=subprocess.Popen([sys.executable,'-c',"import os,time; from pathlib import Path; p=Path(__import__('sys').argv[1]); [(p.write_text(str(time.time())),time.sleep(.03)) for _ in range(10000)]",str(root/'heartbeat')])
print('fetch stalled',file=sys.stderr,flush=True)
time.sleep(60)
"""
            with self.assertRaisesRegex(RuntimeError, "timed out.*fetch stalled"):
                run_fetch([sys.executable, "-c", script, directory], root, timeout=0.5)
            self.assertFalse((root / "shallow.lock").exists())
            first = (root / "heartbeat").read_text()
            time.sleep(0.15)
            self.assertEqual((root / "heartbeat").read_text(), first)
            run_fetch([sys.executable, "-c", "pass"], root)

    def test_preexisting_lock_is_not_deleted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "shallow.lock").write_text("other operation")
            with self.assertRaisesRegex(RuntimeError, "timed out"):
                run_fetch(
                    [sys.executable, "-c", "import time; time.sleep(60)"],
                    root,
                    timeout=0.2,
                )
            self.assertEqual((root / "shallow.lock").read_text(), "other operation")

    def test_error_includes_git_stderr(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "failed \\(128\\).*shallow.lock"):
                run_fetch(
                    [
                        sys.executable,
                        "-c",
                        "import sys; print('fatal: shallow.lock exists',file=sys.stderr); sys.exit(128)",
                    ],
                    directory,
                )


if __name__ == "__main__":
    unittest.main()
