import concurrent.futures
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from livelife.build_queue import BuildQueue
from livelife.build_runner import extract_source, rewrite_mirrors, sandbox_command
from livelife.course import Course
from unittest.mock import patch

A, B = "a" * 40, "b" * 40


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.queue = BuildQueue(Path(self.temp.name))

    def submit(
        self, run, commit=A, branch="27-preview", component="frontend", attempt=1
    ):
        return self.queue.submit(
            {
                "component": component,
                "sha": commit,
                "branch": branch,
                "run_id": run,
                "attempt": attempt,
            }
        )

    def test_push_and_pr_share_one_build_but_components_are_separate(self):
        first = self.submit(10)
        self.assertEqual(self.submit(11)["id"], first["id"])
        self.assertNotEqual(self.submit(12, component="backend")["id"], first["id"])

    def test_global_concurrency_is_enforced_across_queue_instances(self):
        for run in range(1, 7):
            self.submit(run, commit=f"{run:040x}", branch=f"branch-{run}")

        def claim(_):
            return BuildQueue(Path(self.temp.name)).claim()

        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            claimed = [j for j in pool.map(claim, range(6)) if j]
        self.assertEqual(len(claimed), 2)
        self.queue.finish(claimed[0]["id"], {"ok": True})
        self.assertIsNotNone(self.queue.claim())

    def test_queued_older_sha_is_cancelled_and_late_request_rejected(self):
        old = self.submit(10)
        new = self.submit(20, commit=B)
        self.assertEqual(self.queue.lookup(old["id"])["status"], "cancelled")
        self.assertEqual(self.submit(15)["status"], "cancelled")
        self.assertEqual(self.queue.claim()["id"], new["id"])

    def test_running_job_is_kept_and_failure_can_be_rerun(self):
        old = self.submit(10)
        self.queue.claim()
        self.submit(20, commit=B)
        self.assertEqual(self.queue.lookup(old["id"])["status"], "running")
        self.queue.finish(old["id"], error="failed")
        retry = self.submit(21, attempt=2)
        self.assertNotEqual(retry["id"], old["id"])

    def test_restart_does_not_report_unfinished_job_as_success(self):
        job = self.submit(10)
        self.queue.claim()
        self.queue.recover()
        self.assertEqual(self.queue.lookup(job["id"])["status"], "failure")
        with self.assertRaises(ValueError):
            self.queue.completed(job["id"])

    def test_log_chunks_and_artifact_identity(self):
        job = self.submit(10)
        directory = self.queue.jobs / job["id"]
        directory.mkdir()
        (directory / "build.log").write_bytes(b"x" * 40000)
        result = self.queue.lookup(job["id"])
        self.assertEqual(result["log_offset"], 32768)
        self.assertEqual(
            len(self.queue.lookup(job["id"], result["log_offset"])["log"]), 7232
        )
        self.queue.claim()
        self.queue.finish(job["id"], {"frontend_sha": A})
        self.queue.completed(job["id"], "frontend", A)
        for component, commit in [("backend", A), ("frontend", B)]:
            with self.assertRaises(ValueError):
                self.queue.completed(job["id"], component, commit)
        for bad in ["../escape", "x" * 32]:
            with self.assertRaises(ValueError):
                self.queue.lookup(bad)
        with self.assertRaises(ValueError):
            self.queue.lookup(job["id"], -1)

    def test_invalid_metadata_and_slot_limits_rejected(self):
        for slot in [0, 3, True]:
            with self.assertRaises(ValueError):
                BuildQueue(Path(self.temp.name), slots=slot)
        for extra in [
            {"component": "shell"},
            {"sha": "main"},
            {"branch": "bad\nbranch"},
            {"attempt": 1000},
        ]:
            with self.assertRaises(ValueError):
                self.queue.submit(
                    {
                        "component": "frontend",
                        "sha": A,
                        "branch": "branch",
                        "run_id": 1,
                        **extra,
                    }
                )

    def test_collection_preserves_venv_referenced_by_a_release(self):
        now = [1.0]
        self.queue.clock = lambda: now[0]
        kept = self.submit(10, component="backend")
        self.queue.claim()
        self.queue.finish(kept["id"], {"available": True})
        expired = self.submit(11, commit=B)
        self.queue.claim()
        self.queue.finish(expired["id"], error="failed")
        for job in (kept, expired):
            (self.queue.jobs / job["id"]).mkdir()
        releases = Path(self.temp.name) / "releases"
        record = releases / ("be-" + A) / "release.json"
        record.parent.mkdir(parents=True)
        record.write_text(json.dumps({"job": kept["id"]}))
        now[0] = 9 * 86400
        self.assertEqual(self.queue.collect(releases), [expired["id"]])
        self.assertTrue((self.queue.jobs / kept["id"]).is_dir())
        record.unlink()
        self.assertEqual(self.queue.collect(releases), [kept["id"]])

    def test_corrupt_release_record_stops_collection(self):
        releases = Path(self.temp.name) / "releases/be-bad"
        releases.mkdir(parents=True)
        (releases / "release.json").write_text("invalid JSON")
        self.assertEqual(self.queue.collect(releases.parent, grace=-1), [])


class RunnerBoundaryTests(unittest.TestCase):
    def test_release_reuses_tested_venv_and_original_git_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            queue = BuildQueue(root / "builds")
            job = queue.submit(
                {"component": "backend", "sha": A, "branch": "test", "run_id": 1}
            )
            queue.claim()
            queue.finish(job["id"], {"available": True})
            venv = queue.jobs / job["id"] / "repo/backend/.venv"
            (venv / "bin").mkdir(parents=True)
            (venv / "bin/python").symlink_to(sys.executable)
            (venv / "pyvenv.cfg").write_text("test")
            source = io.BytesIO()
            with tarfile.open(fileobj=source, mode="w") as archive:
                item = tarfile.TarInfo("backend/app/main.py")
                item.size = 5
                archive.addfile(item, io.BytesIO(b"hello"))
            course = Course(root)
            release = course.releases / ("be-" + A)
            with patch(
                "livelife.course.subprocess.check_output",
                return_value=source.getvalue(),
            ):
                course.install_built(job["id"], A, 18000, release)
            self.assertEqual((release / ".venv").resolve(), venv)
            self.assertEqual((release / "backend/app/main.py").read_text(), "hello")
            self.assertEqual(
                json.loads((release / "release.json").read_text())["job"], job["id"]
            )
            with self.assertRaises(ValueError):
                course.install_built(job["id"], B, 18001, release)

    def test_only_transient_lock_urls_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            (workspace / "backend").mkdir()
            (workspace / "frontend").mkdir()
            (workspace / "backend/uv.lock").write_text(
                'source="https://pypi.org/simple"\nurl="https://files.pythonhosted.org/wheel"\nhash="sha256:keep"'
            )
            (workspace / "frontend/package-lock.json").write_text(
                '{"resolved":"https://registry.npmjs.org/package","integrity":"sha512-keep"}'
            )
            rewrite_mirrors(workspace)
            self.assertIn("sha256:keep", (workspace / "backend/uv.lock").read_text())
            self.assertIn("mirrors.aliyun", (workspace / "backend/uv.lock").read_text())
            self.assertIn(
                "sha512-keep", (workspace / "frontend/package-lock.json").read_text()
            )

    def test_sandbox_exposes_workspace_but_not_course_home_or_keys(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            command = sandbox_command(
                root, root / "builds/jobs/job/repo", ["python", "test.py"]
            )
            self.assertIn("--unshare-all", command)
            self.assertIn("--die-with-parent", command)
            self.assertNotIn("/home/group5", command)
            self.assertNotIn(str(root / "credentials"), command)
            self.assertIn("/runner", command)
            self.assertIn("--ro-bind", command)

    def test_git_source_archive_cannot_extract_links_or_traversal(self):
        for name, kind in [
            ("../escape", tarfile.REGTYPE),
            ("backend/link", tarfile.SYMTYPE),
        ]:
            out = io.BytesIO()
            with tarfile.open(fileobj=out, mode="w") as archive:
                item = tarfile.TarInfo(name)
                item.type = kind
                item.linkname = "/etc/passwd"
                archive.addfile(item)
            with (
                tempfile.TemporaryDirectory() as temporary,
                self.assertRaises(ValueError),
            ):
                extract_source(out.getvalue(), Path(temporary))

    def test_static_packaging_rejects_symlinks_and_authenticates_bytes(self):
        path = Path(__file__).resolve().parents[1] / "prepare-frontend.py"
        spec = importlib.util.spec_from_file_location("prepare_frontend_test", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temporary:
            dist = Path(temporary) / "dist"
            dist.mkdir()
            (dist / "index.html").write_text("hello")
            output = Path(temporary) / "out"
            manifest = module.package_frontend(dist, output, A, 10, 1)
            self.assertEqual(
                manifest["digest"],
                hashlib.sha256((output / "frontend.tgz").read_bytes()).hexdigest(),
            )
            (dist / "bad").symlink_to("/etc/passwd")
            with self.assertRaises(ValueError):
                module.package_frontend(dist, output, A, 10, 1)
