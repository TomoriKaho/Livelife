import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import importlib.util
import unittest

spec = importlib.util.spec_from_file_location("actions_control", Path(__file__).resolve().parents[1] / "actions-control.py")
control = importlib.util.module_from_spec(spec)
spec.loader.exec_module(control)

A, B = "a" * 40, "b" * 40
REPO = "TomoriKaho/Livelife"


class GitHub:
    def __init__(self):
        self.latest = A
        self.state = "open"
        self.manifest = {"sha": A, "available": True}
        self.artifact_calls = 0
        self.comments = []

    def artifact(self, run_id):
        self.artifact_calls += 1
        return self.manifest, b"source"

    def call(self, path):
        if "/commits/" in path:
            return {"sha": self.latest}
        if "/pulls?" in path:
            return [{"number": 40, "state": self.state, "head": {"repo": {"full_name": REPO}}}]
        raise AssertionError(path)

    def comment(self, number, text):
        self.comments.append((number, text))


class ActionsTests(unittest.TestCase):
    def setUp(self):
        self.controller = control.Controller.__new__(control.Controller)
        self.controller.repo = REPO
        self.controller.github = GitHub()
        self.controller.generation = 120001
        self.results = []
        self.requests = []
        self.controller.summary = self.results.append
        def rpc(request):
            self.requests.append(request)
            return {"status": "superseded"}
        self.controller.rpc = rpc
        self.run = {"id": 10, "run_attempt": 1, "conclusion": "success", "head_sha": A,
                    "head_branch": "40-backend", "head_repository": {"full_name": REPO}}

    def test_fork_run_does_not_download_or_deploy(self):
        self.run["head_repository"]["full_name"] = "fork/Livelife"
        self.controller.build_completed(self.run)
        self.assertEqual(self.controller.github.artifact_calls, 0)
        self.assertEqual(self.requests, [])

    def test_closed_pr_does_not_gain_a_branch_lease(self):
        self.controller.github.state = "closed"
        self.controller.build_completed(self.run)
        self.assertEqual(self.requests, [])

    def test_artifact_sha_must_match_workflow_run(self):
        self.controller.github.manifest["sha"] = B
        with self.assertRaises(ValueError):
            self.controller.build_completed(self.run)
        self.assertEqual(self.requests, [])

    def test_moved_branch_does_not_publish_old_build(self):
        self.controller.github.latest = B
        self.controller.build_completed(self.run)
        self.assertEqual(self.requests, [])

    def test_deploy_uses_original_build_generation(self):
        self.controller.build_completed(self.run)
        self.assertEqual(self.requests[0]["owner"], "pr:40")
        self.assertEqual(self.requests[0]["generation"], 10001)
        self.assertNotIn('bundle', self.requests[0])

    def test_missing_version_uploads_only_after_server_requests_bundle(self):
        def rpc(request):
            self.requests.append(dict(request))
            return {'status': 'superseded'} if 'bundle' in request else {'status': 'upload_required'}
        self.controller.rpc = rpc
        self.controller.build_completed(self.run)
        self.assertEqual(len(self.requests), 2)
        self.assertNotIn('bundle', self.requests[0])
        self.assertIn('bundle', self.requests[1])
        self.assertEqual(self.requests[0]['generation'], self.requests[1]['generation'])

    def test_backend_not_initialized_does_not_advertise_a_link(self):
        self.controller.github.manifest["available"] = False
        self.controller.build_completed(self.run)
        self.assertEqual(self.requests, [])
        self.assertEqual(self.controller.github.comments, [])

    def test_manual_pr_binding_uses_resolved_immutable_instance(self):
        self.controller.pr = lambda number: {"state": "open", "head": {"repo": {"full_name": REPO}, "sha": A}}
        def rpc(request):
            self.requests.append(request)
            return {"status": "ready", "instance": "be-" + A, "backend_sha": A,
                    "api_base_url": "https://192.144.253.40/api/versions/be-" + A + "/"}
        self.controller.rpc = rpc
        self.controller.manual({"operation": "bind", "frontend_pr": "41", "backend_target": "pr-40"})
        self.assertEqual(self.requests[-1]["op"], "bind")
        self.assertEqual(self.requests[-1]["target"], "be-" + A)
        # A late manual run must not report a successful replacement or index
        # missing URL fields after the registry rejects its generation.
        self.controller.rpc = lambda request: {"status": "superseded"}
        self.controller.manual({"operation": "bind", "frontend_pr": "41", "backend_target": "staging"})
        self.assertEqual(len(self.controller.github.comments), 1)
        self.assertEqual(self.results[-1]["status"], "superseded")

    def test_undeployed_latest_sha_keeps_previous_binding(self):
        self.controller.pr = lambda number: {"state": "open", "head": {"repo": {"full_name": REPO}, "sha": B}}
        def rpc(request):
            self.requests.append(request)
            return {"backend_sha": A, "instance": "be-" + A}
        self.controller.rpc = rpc
        with self.assertRaises(ValueError):
            self.controller.manual({"operation": "bind", "frontend_pr": "41", "backend_target": "pr-40"})
        self.assertEqual([r["op"] for r in self.requests], ["lookup"])


if __name__ == "__main__":
    unittest.main()
