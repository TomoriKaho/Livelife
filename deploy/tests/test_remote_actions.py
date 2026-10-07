import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
spec = importlib.util.spec_from_file_location(
    "remote_control_test", Path(__file__).resolve().parents[1] / "actions-control.py"
)
control = importlib.util.module_from_spec(spec)
spec.loader.exec_module(control)
A = "a" * 40
REPO = "TomoriKaho/Livelife"


class GitHub:
    def __init__(self, run):
        self.run, self.statuses = run, []

    def call(self, path, data=None, method=None):
        if "/actions/runs/" in path:
            return self.run
        if "/statuses/" in path:
            self.statuses.append(data)
            return {}
        raise AssertionError(path)


class RemoteActionsTests(unittest.TestCase):
    def setUp(self):
        self.run = {
            "id": 10,
            "run_attempt": 1,
            "name": "Frontend build request",
            "path": ".github/workflows/frontend-checks.yml",
            "conclusion": "success",
            "head_repository": {"full_name": REPO},
            "head_sha": A,
            "head_branch": "27-preview",
            "event": "push",
        }
        self.c = control.Controller.__new__(control.Controller)
        self.c.repo = REPO
        self.c.github = GitHub(self.run)
        self.context = {"environment": "branch-" + "b" * 32, "pr": 37, "source_sha": A}
        self.c.context = lambda branch, sha: self.context
        self.summaries = []
        self.c.summary = self.summaries.append
        self.requests = []
        self.c.rpc = lambda request: self.requests.append(request)
        self.c.emit_log = lambda *args: None
        self.notes = []
        self.c.record_check = lambda run, component: self.notes.append(
            (run["conclusion"], component)
        )
        self.published = []
        self.c.sync_web = lambda *args, **kwargs: self.published.append(kwargs)
        self.c.wait_build = lambda request: {
            "id": "c" * 32,
            "status": "success",
            "result": {"frontend_sha": A},
        }

    def test_fork_and_wrong_workflow_path_never_submit(self):
        for changed in [
            {"head_repository": {"full_name": "fork/repo"}},
            {"path": ".github/workflows/evil.yml"},
            {"event": "schedule"},
        ]:
            original = dict(self.run)
            self.run.update(changed)
            self.c.remote_completed({"id": 10})
            self.assertEqual(self.c.github.statuses, [])
            self.assertEqual(self.requests, [])
            self.run.clear()
            self.run.update(original)

    def test_only_checked_frontend_is_published_without_runner_bundle(self):
        with patch.dict("os.environ", {"LIVELIFE_FRONTEND_ENABLED": "true"}):
            self.c.remote_completed({"id": 10})
        self.assertEqual(
            [s["state"] for s in self.c.github.statuses], ["pending", "success"]
        )
        self.assertEqual(self.notes, [("success", "frontend")])
        self.assertEqual(self.published[0]["job"], "c" * 32)
        self.assertNotIn("bundle", self.published[0])

    def test_failed_build_marks_commit_failure_and_never_publishes_candidate(self):
        self.c.wait_build = lambda request: {
            "status": "failure",
            "error": "test failed",
        }
        with (
            patch.dict("os.environ", {"LIVELIFE_FRONTEND_ENABLED": "false"}),
            self.assertRaises(RuntimeError),
        ):
            self.c.remote_completed({"id": 10})
        self.assertEqual(
            [s["state"] for s in self.c.github.statuses], ["pending", "failure"]
        )
        self.assertEqual(self.published, [])

    def test_head_moved_during_checks_keeps_success_status_but_skips_deployment(self):
        values = iter([self.context, None])
        self.c.context = lambda *args: next(values)
        with patch.dict("os.environ", {"LIVELIFE_FRONTEND_ENABLED": "true"}):
            self.c.remote_completed({"id": 10})
        self.assertEqual(self.published, [])
        self.assertEqual(self.summaries[-1]["status"], "superseded")

    def test_wait_drains_logs_and_rejects_wrong_course_sha(self):
        results = iter(
            [
                {"id": "c" * 32, "status": "queued"},
                {
                    "id": "c" * 32,
                    "sha": A,
                    "component": "frontend",
                    "status": "success",
                    "log": "test log",
                    "log_offset": 8,
                },
                {
                    "id": "c" * 32,
                    "sha": A,
                    "component": "frontend",
                    "status": "success",
                    "log": "",
                    "log_offset": 8,
                },
            ]
        )
        self.c.rpc = lambda request: next(results)
        result = control.Controller.wait_build(
            self.c, {"component": "frontend", "sha": A}
        )
        self.assertEqual(result["status"], "success")
        results = iter(
            [
                {"id": "c" * 32, "status": "queued"},
                {"sha": "b" * 40, "component": "frontend", "status": "success"},
            ]
        )
        self.c.rpc = lambda request: next(results)
        with self.assertRaises(ValueError):
            control.Controller.wait_build(self.c, {"component": "frontend", "sha": A})
