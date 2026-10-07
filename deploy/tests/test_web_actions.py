"""Join GitHub-verified heads with actual registry operations, without servers."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import unquote

from livelife.manager import dispatch
from livelife.registry import Registry
from test_web import artifact, Runtime, A, B, C
from livelife.web_actions import web_environment

spec = importlib.util.spec_from_file_location('web_control', Path(__file__).resolve().parents[1] / 'actions-control.py')
control = importlib.util.module_from_spec(spec)
spec.loader.exec_module(control)
REPO = 'TomoriKaho/Livelife'
D = 'd' * 40


class Metadata:
    def __init__(self):
        self.heads = {'main': A, 'feature': B}
        self.trees = {A: {'frontend': 'fa', 'backend': 'ba'}, B: {'frontend': 'fb', 'backend': 'ba'},
                      C: {'frontend': 'fb', 'backend': 'bc'}, D: {'frontend': 'fa', 'backend': 'bc'}}
        self.comments = []
        self.number = 40
        self.downloads = 0

    def call(self, path):
        if '/commits/' in path:
            ref = unquote(path.split('/commits/')[1])
            commit = self.heads.get(ref, ref)
            return {'sha': commit, 'commit': {'tree': {'sha': commit}}}
        if '/git/trees/' in path:
            return {'tree': [{'path': k, 'sha': v} for k, v in self.trees[path.split('/')[-1]].items()]}
        if '/compare/' in path:
            return {'merge_base_commit': {'sha': A}}
        if '/pulls?' in path:
            return [] if 'main' in path or self.number is None else [
                {'state': 'open', 'number': self.number, 'head': {'repo': {'full_name': REPO}}}]
        raise AssertionError(path)

    def artifact(self, run, name):
        self.downloads += 1
        return artifact(self.heads['feature'], run)

    def comment(self, number, text):
        self.comments.append((number, text))


class WebActionsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        env = patch.dict(os.environ, LIVELIFE_FRONTEND_ENABLED='true')
        env.start()
        self.addCleanup(env.stop)
        self.registry = Registry(self.directory.name, Runtime(), 'https://192.144.253.40')
        self.registry.deploy('main', A, 1, b'backend')
        self.controller = control.Controller.__new__(control.Controller)
        self.controller.github = Metadata()
        self.controller.repo = REPO
        self.controller.generation = 50000
        self.requests = []
        def rpc(request):
            self.requests.append(request)
            return dispatch(self.registry, request)
        self.controller.rpc = rpc
        self.controller.summary = lambda result: None
        self.run = {'id': 10, 'run_attempt': 1, 'head_sha': B, 'head_branch': 'feature',
                    'head_repository': {'full_name': REPO}, 'conclusion': 'success', 'name': 'Frontend checks'}

    def main_frontend(self):
        manifest, bundle = artifact(A, 1)
        self.controller.sync_web('main', A, manifest, bundle, 1001)

    def test_frontend_only_uses_staging_and_own_backend_unchanged_tree_can_be_reused(self):
        result = self.controller.frontend_completed(self.run)
        self.assertEqual(result['backend_mode'], 'staging')
        self.controller.github.heads['feature'] = C
        self.registry.deploy('pr:40', D, 2, b'backend')
        self.run['head_sha'] = C
        self.run['id'] = 11
        result = self.controller.frontend_completed(self.run)
        self.assertEqual(result['backend_mode'], 'own')
        self.assertEqual(result['backend_sha'], D)  # Same backend tree despite a different front-end commit.

    def test_frontend_completes_first_waits_for_matching_backend(self):
        self.controller.github.heads['feature'] = C
        self.run['head_sha'] = C
        result = self.controller.frontend_completed(self.run)
        self.assertEqual(result['status'], 'waiting')
        self.registry.deploy('pr:40', C, 2, b'backend')
        self.controller.backend_web_completed({**self.run, 'name': 'Backend checks', 'id': 9})
        result = self.registry.web.lookup(web_environment('feature'))
        self.assertEqual((result['status'], result['frontend_sha'], result['backend_sha']), ('ready', C, C))

    def test_backend_only_pr_waits_for_main_artifact_then_reuses_it(self):
        self.controller.github.heads['feature'] = D
        self.registry.deploy('pr:40', D, 2, b'backend')
        result = self.controller.sync_web('feature')
        self.assertEqual(result['status'], 'waiting')
        self.main_frontend()
        result = self.controller.sync_web('feature')
        self.assertEqual((result['frontend_sha'], result['backend_sha']), (A, D))
        self.assertEqual(self.controller.github.downloads, 0)

    def test_new_main_frontend_waits_for_matching_main_backend_tree(self):
        self.controller.github.heads['main'] = D
        manifest, bundle = artifact(D, 11)
        result = self.controller.sync_web('main', D, manifest, bundle, 11001)
        self.assertEqual(result['status'], 'waiting')

    def test_explicit_fixed_pairing_survives_another_pr_update(self):
        self.controller.frontend_completed(self.run)
        self.registry.deploy('pr:42', D, 2, b'backend')
        self.registry.bind('frontend:40', 'be-' + D, 12)
        self.controller.sync_web('feature')
        self.registry.deploy('pr:42', C, 3, b'backend')
        result = self.controller.sync_web('feature')
        self.assertEqual((result['backend_mode'], result['backend_sha']), ('fixed', D))

    def test_fork_and_superseded_builds_do_not_download_or_publish(self):
        self.controller.frontend_completed({**self.run, 'head_repository': {'full_name': 'fork/Livelife'}})
        self.controller.github.heads['feature'] = C
        self.controller.frontend_completed(self.run)
        self.assertEqual(self.requests, [])
        self.assertEqual(self.controller.github.downloads, 0)

    def test_reopen_reuses_existing_artifact_without_a_new_download(self):
        first = self.controller.frontend_completed(self.run)
        self.registry.web.release(web_environment('feature'), 20000)
        restored = self.controller.sync_web('feature')
        self.assertEqual(restored['status'], 'ready')
        self.assertEqual(restored['build_id'], first['build_id'])
        self.assertEqual(self.controller.github.downloads, 1)

    def test_failed_build_reports_previous_page_as_historical(self):
        self.controller.frontend_completed(self.run)
        self.controller.github.heads['feature'] = C
        self.controller.frontend_completed({**self.run, 'id': 11, 'head_sha': C, 'conclusion': 'failure'})
        self.assertEqual(self.registry.web.lookup(web_environment('feature'))['status'], 'failed')
        self.assertIn('不代表最新提交', self.controller.github.comments[-1][1])


if __name__ == '__main__':
    unittest.main()
