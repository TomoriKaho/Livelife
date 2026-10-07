import os
import unittest
from unittest.mock import patch
from livelife.android_actions import AndroidActions
from test_android_build import config


class Controller(AndroidActions):
    generation = 10001

    def __init__(self):
        self.calls = []
        self.results = []
        self.comments = []
        self.statuses = []
        self.pr = lambda n: {"state": "open"}
        self.preview_comment = self.comments.append
        self.summary = self.results.append
        self.commit = lambda ref: {"sha": "a" * 40}
        self.check_status = lambda *args: self.statuses.append(args)
        self.wait_build = lambda request: {"status": "success", "id": "c" * 32}

    def rpc(self, request):
        self.calls.append(request)
        if request["op"] == "apk_reserve":
            return {**config(), "status": "pending", "generation": 10001}
        if request["op"] == "apk_publish_built":
            return {**config(), "status": "ready"}
        return {"status": "released"}


class AndroidActionsTests(unittest.TestCase):
    def test_manual_android_reuses_backend_only_when_its_git_tree_is_unchanged(self):
        from test_actions import control, A, B, REPO

        c = control.Controller.__new__(control.Controller)
        c.repo = REPO
        c.pr = lambda number: {
            "state": "open",
            "head": {"repo": {"full_name": REPO}, "sha": B},
        }
        c.rpc = lambda request: {"backend_sha": A, "instance": "be-" + A}
        c.tree = lambda commit: {"backend": "same-backend-tree"}
        with patch.dict(os.environ, LIVELIFE_ANDROID_ENABLED="true"):
            self.assertEqual(c.manual_target("pr-42"), "be-" + A)
            c.tree = lambda commit: {"backend": commit}
            with self.assertRaises(ValueError):
                c.manual_target("pr-42")
            c.pr = lambda number: {
                "state": "open",
                "head": {"repo": {"full_name": "fork/Livelife"}, "sha": A},
            }
            with self.assertRaises(ValueError):
                c.manual_target("pr-42")

    def test_only_backend_branch_has_no_automatic_apk(self):
        c = Controller()
        c.context = lambda *args: {
            "environment": "branch-" + "b" * 32,
            "pr": 42,
            "frontend_changed": False,
        }
        with patch.dict(os.environ, LIVELIFE_ANDROID_ENABLED="true"):
            c.sync_android("backend-only", "a" * 40)
        self.assertEqual(c.calls, [])

    def test_failed_build_never_signs_and_updates_same_comment(self):
        c = Controller()
        c.wait_build = lambda request: {"status": "failure", "error": "Gradle failed"}
        context = {
            "environment": "branch-" + "b" * 32,
            "pr": 42,
            "branch": "feature",
            "source_sha": "a" * 40,
        }
        with self.assertRaises(RuntimeError):
            c.run_android(context, "be-" + "c" * 40, "fixed", 10001, 10)
        self.assertNotIn("apk_publish_built", [r["op"] for r in c.calls])
        self.assertIn("apk_fail", [r["op"] for r in c.calls])
        self.assertEqual(c.comments, [42, 42])
        self.assertEqual(c.statuses[-1][2], "failure")

    def test_branch_moved_before_signing_is_not_published(self):
        c = Controller()
        c.commit = lambda ref: {"sha": "b" * 40}
        context = {
            "environment": "branch-" + "b" * 32,
            "pr": 42,
            "branch": "feature",
            "source_sha": "a" * 40,
        }
        result = c.run_android(context, "be-" + "c" * 40, "fixed", 10001, 10)
        self.assertEqual(result["status"], "superseded")
        self.assertNotIn("apk_publish_built", [r["op"] for r in c.calls])

    def test_successful_build_has_independent_apk_publication(self):
        c = Controller()
        context = {
            "environment": "branch-" + "b" * 32,
            "pr": 42,
            "branch": "feature",
            "source_sha": "a" * 40,
        }
        result = c.run_android(context, "be-" + "c" * 40, "fixed", 10001, 10)
        self.assertEqual(result["status"], "ready")
        self.assertEqual(c.statuses[-1][2], "success")
        self.assertNotIn("web_publish", [r["op"] for r in c.calls])
