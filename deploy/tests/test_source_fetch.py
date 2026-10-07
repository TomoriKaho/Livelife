"""Real Git-like child processes exercise timeout cleanup without network."""

from pathlib import Path
import sys
import subprocess
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from livelife.build_runner import run_fetch, anchor_cached_commits


class FetchTests(unittest.TestCase):
    def test_unreferenced_cached_commit_gets_negotiation_ref(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", directory], check=True)
            (root / "fixture").write_text("cached source")
            subprocess.run(["git", "-C", directory, "add", "fixture"], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    directory,
                    "-c",
                    "user.name=Fixture",
                    "-c",
                    "user.email=fixture@example.invalid",
                    "commit",
                    "-qm",
                    "fixture",
                ],
                check=True,
            )
            commit = subprocess.check_output(
                ["git", "-C", directory, "rev-parse", "HEAD"], text=True
            ).strip()
            branch = subprocess.check_output(
                ["git", "-C", directory, "symbolic-ref", "HEAD"], text=True
            ).strip()
            source = root / ".git"
            subprocess.run(
                ["git", "--git-dir", str(source), "update-ref", "-d", branch],
                check=True,
            )
            (source / "shallow").write_text(commit + "\n")
            anchor_cached_commits(source)
            anchored = subprocess.check_output(
                [
                    "git",
                    "--git-dir",
                    str(source),
                    "rev-parse",
                    "refs/livelife/source/" + commit,
                ],
                text=True,
            ).strip()
            self.assertEqual(anchored, commit)

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
