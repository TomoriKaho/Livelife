import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import hashlib
import io
import json
import os
import signal
import sqlite3
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from livelife.registry import Registry
from livelife.web import unpack, build_id, environment
from test_registry import Runtime

A, B, C = 'a' * 40, 'b' * 40, 'c' * 40
ENV = 'branch-' + 'd' * 32


def artifact(commit=A, run=1, extra=None):
    ident = f'fe-{commit}-{run}-1'
    files = {'index.html': f'<script src="/__livelife/web-builds/{ident}/assets/index.js"></script>'.encode(),
             'assets/index.js': b'console.log("test")', 'assets/font-hash.ttf': b'same font',
             'assets/maps/LICENSE.md': b'OSM license'}
    files.update(extra or {})
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode='w:gz') as tar:
        for name, value in files.items():
            item = tarfile.TarInfo(name)
            item.size = len(value)
            tar.addfile(item, io.BytesIO(value))
    bundle = out.getvalue()
    return {'schema_version': 1, 'frontend_sha': commit, 'run_id': run, 'run_attempt': 1,
            'build_id': ident, 'digest': hashlib.sha256(bundle).hexdigest()}, bundle


class WebTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.runtime = Runtime()
        self.now = 1000
        self.registry = Registry(self.directory.name, self.runtime, 'https://192.144.253.40',
                                 grace=10, lease=100, clock=lambda: self.now)
        self.registry.deploy('main', A, 1, b'backend')

    def publish(self, key=ENV, commit=A, generation=10, target='staging', pr=40, **overrides):
        manifest, bundle = artifact(commit, generation)
        return self.registry.web.publish(dict(environment=key, branch='feature', pr=None if key == 'main' else pr,
            source_sha=commit, generation=generation, target=target,
            mode='staging' if target == 'staging' else 'own', manifest=manifest, bundle=bundle, **overrides))

    def test_independent_environments_stable_branch_and_pr_aliases(self):
        self.publish('main')
        first = self.publish()
        self.publish('branch-' + 'e' * 32, B, 11, pr=41)
        self.assertEqual(first['frontend_url'], 'https://192.144.253.40/preview/pr-40/')
        self.assertEqual(self.runtime.routes[f'/preview/{ENV}/']['deployment'], self.runtime.routes['/preview/pr-40/']['deployment'])
        self.assertEqual(self.runtime.routes['/staging/']['config']['frontend_sha'], A)
        self.assertEqual(self.runtime.routes['/preview/pr-41/']['config']['frontend_sha'], B)

    def test_staging_follows_main_and_fixed_selection_keeps_original_sha(self):
        self.publish()
        self.registry.deploy('pr:42', B, 2, b'backend')
        self.registry.bind('frontend:40', 'be-' + B, 15)
        self.publish(commit=C, generation=20)
        self.registry.deploy('main', C, 3, b'backend')
        self.assertEqual(self.registry.web.lookup(ENV)['backend_sha'], B)
        self.assertEqual(self.registry.web.lookup(ENV)['backend_mode'], 'fixed')

    def test_frontend_first_waits_then_backend_completion_publishes(self):
        first = self.publish(target=None)
        self.assertEqual(first['status'], 'waiting')
        self.assertNotIn('frontend_sha', first)
        self.registry.deploy('pr:40', B, 2, b'backend')
        ready = self.registry.web.publish(dict(environment=ENV, branch='feature', pr=40, source_sha=A,
            generation=9, build_id=first['desired_build'], target='be-' + B, mode='own'))
        self.assertEqual(ready['status'], 'ready')
        self.assertEqual(ready['backend_sha'], B)

    def test_backend_first_waits_for_frontend_and_branch_promotes_without_reupload(self):
        pending = self.registry.web.publish(dict(environment=ENV, branch='feature', pr=None, source_sha=A,
            generation=1, target='staging', mode='staging'))
        self.assertEqual(pending['status'], 'waiting')
        first = self.publish(pr=None)
        self.assertIsNotNone(first['expires'])
        promoted = self.registry.web.publish(dict(environment=ENV, branch='feature', pr=40, source_sha=A,
            generation=12, build_id=first['build_id'], target='staging', mode='staging'))
        self.assertEqual(promoted['expires'], None)
        self.assertEqual(len(self.registry.snapshot()['web_builds']), 1)

    def test_current_and_rollback_independently_pin_backend_and_rollback_works(self):
        self.registry.deploy('pr:40', B, 2, b'backend')
        self.publish(target='be-' + B)
        self.registry.deploy('pr:40', C, 3, b'backend')
        self.publish(commit=B, generation=11, target='be-' + C)
        self.registry.release('pr:40', 4)
        self.now += 1000
        self.registry.collect()
        self.assertIn('be-' + B, self.runtime.running)
        self.assertIn('be-' + C, self.runtime.running)
        result = self.registry.web.rollback(ENV, 20)
        self.assertEqual(result['backend_sha'], B)
        self.assertEqual(result['frontend_sha'], A)
        self.assertTrue(result['rolled_back'])
        self.registry.web.release(ENV, 21)
        self.now += 11
        self.registry.collect()
        self.assertNotIn('be-' + B, self.runtime.running)
        self.assertNotIn('be-' + C, self.runtime.running)
        self.assertIn('be-' + A, self.runtime.running)

    def test_branch_selection_moves_to_pr_and_survives_original_lease(self):
        self.registry.deploy('pr:42', B, 2, b'backend')
        self.publish(pr=None)
        self.registry.bind('frontend:' + ENV, 'be-' + B, 15)
        result = self.publish(pr=40, generation=20)
        self.now += 101
        self.registry.collect()
        self.assertEqual(result['backend_mode'], 'fixed')
        self.assertEqual(self.registry.web.lookup(ENV)['backend_sha'], B)
        owners = {r['owner'] for r in self.registry.snapshot()['refs']}
        self.assertIn('frontend:40', owners)
        self.assertNotIn('frontend:' + ENV, owners)
        self.assertEqual(self.registry.bind('frontend:40', 'staging', 14)['status'], 'superseded')
        self.assertEqual(self.registry.web.lookup(ENV)['backend_sha'], B)

    def test_old_backend_completion_cannot_replace_a_newer_source(self):
        self.publish(commit=B, generation=20)
        result = self.registry.web.publish(dict(environment=ENV, branch='feature', pr=40,
            source_sha=A, generation=19, build_id=f'fe-{B}-20-1', target='staging', mode='staging'))
        self.assertEqual(result['status'], 'superseded')
        self.assertEqual(self.registry.web.lookup(ENV)['source_sha'], B)

    def test_failure_of_gateway_keeps_previous_routes_and_references(self):
        self.publish()
        before = self.runtime.routes.copy()
        self.runtime.fail_publish = True
        with self.assertRaises(RuntimeError):
            self.publish(commit=B, generation=11)
        self.assertEqual(self.runtime.routes, before)
        self.assertEqual(self.registry.web.lookup(ENV)['frontend_sha'], A)
        self.assertEqual(len([r for r in self.registry.snapshot()['refs'] if r['owner'].startswith('web:')]), 1)

    def test_failed_current_check_never_calls_old_page_latest_success(self):
        self.publish()
        self.registry.web.note(dict(environment=ENV, component='frontend', source_sha=B,
                                    generation=11000, status='failure'))
        result = self.registry.web.publish(dict(environment=ENV, branch='feature', pr=40,
            source_sha=B, generation=11, build_id=f'fe-{A}-10-1', target='staging', mode='staging'))
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['frontend_sha'], A)
        self.assertIn('failure', result['error'])

    def test_unhealthy_pairing_reports_failure_and_keeps_current_page(self):
        self.publish()
        self.registry.deploy('pr:40', B, 2, b'backend')
        self.runtime.running.pop('be-' + B)
        with self.assertRaisesRegex(RuntimeError, 'unavailable'):
            self.publish(commit=B, generation=11, target='be-' + B)
        result = self.registry.web.lookup(ENV)
        self.assertEqual((result['status'], result['frontend_sha']), ('failed', A))
        self.assertEqual(self.runtime.routes['/preview/pr-40/']['config']['frontend_sha'], A)

    def test_close_blocks_late_upload_reopen_is_new_generation(self):
        self.publish()
        self.registry.web.release(ENV, 20)
        self.assertEqual(self.publish(commit=B, generation=19)['status'], 'superseded')
        self.assertNotIn('/preview/pr-40/', self.runtime.routes)
        self.assertEqual(self.publish(commit=A, generation=21)['status'], 'ready')
        with self.assertRaises(ValueError):
            self.registry.web.release('main', 30)

    def test_expiry_and_repeated_cleanup_do_not_remove_other_sites(self):
        self.publish('main')
        self.publish(pr=None)
        self.now += 101
        self.registry.collect()
        self.assertEqual(self.registry.web.lookup(ENV)['status'], 'released')
        self.registry.web.release(ENV, 20)
        self.registry.web.release(ENV, 20)
        self.assertEqual(self.registry.web.lookup('main')['status'], 'ready')

    def test_periodic_reconciliation_cannot_extend_branch_lease(self):
        result = self.publish(pr=None)
        self.now += 50
        reconciled = self.registry.web.publish(dict(environment=ENV, branch='feature', pr=None,
            source_sha=A, generation=20, build_id=result['build_id'], target='staging', mode='staging', renew=False))
        self.assertEqual(reconciled['expires'], result['expires'])
        self.now += 51
        self.registry.collect()
        self.assertEqual(self.registry.web.lookup(ENV)['status'], 'released')

    def test_assets_reuse_inodes_and_collision_is_rejected(self):
        self.publish()
        self.publish(commit=B, generation=11)
        root = self.registry.web.root
        first = root / f'builds/fe-{A}-10-1/assets/font-hash.ttf'
        second = root / f'builds/fe-{B}-11-1/assets/font-hash.ttf'
        self.assertEqual(first.stat().st_ino, second.stat().st_ino)
        manifest, bundle = artifact(C, 12, {'assets/font-hash.ttf': b'different font'})
        with self.assertRaisesRegex(ValueError, 'collision'):
            self.registry.web.publish(dict(environment=ENV, branch='feature', pr=40, source_sha=C,
                generation=12, target='staging', mode='staging', manifest=manifest, bundle=bundle))
        self.assertEqual(first.read_bytes(), b'same font')

    def test_quota_rejects_candidate_without_changing_published_site(self):
        self.publish()
        self.registry.web.quota = self.registry.web.physical_bytes()
        with self.assertRaisesRegex(ValueError, 'quota'):
            self.publish(commit=B, generation=11)
        self.assertEqual(self.registry.web.lookup(ENV)['frontend_sha'], A)

    def test_digest_and_paths_links_devices_duplicates_are_rejected(self):
        for name, kind in [('../escape.html', None), ('/escape.html', None), ('assets/../escape.js', None),
                           ('assets/link.js', tarfile.SYMTYPE), ('assets/link.js', tarfile.LNKTYPE),
                           ('assets/device.js', tarfile.CHRTYPE), ('control.py', None)]:
            out = io.BytesIO()
            with tarfile.open(fileobj=out, mode='w:gz') as archive:
                item = tarfile.TarInfo(name)
                item.type = kind or tarfile.REGTYPE
                item.linkname = '/tmp/escape'
                archive.addfile(item)
            with self.subTest(name=name), tempfile.TemporaryDirectory() as root:
                with self.assertRaises(ValueError):
                    unpack(out.getvalue(), Path(root))
        manifest, bundle = artifact()
        manifest['digest'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'digest'):
            self.registry.web.publish(dict(environment=ENV, branch='feature', pr=40, source_sha=A,
                generation=10, target='staging', mode='staging', manifest=manifest, bundle=bundle))

    def test_duplicate_paths_entry_count_and_expanded_size_limits(self):
        for count, duplicate in [(2, True), (10001, False)]:
            out = io.BytesIO()
            with tarfile.open(fileobj=out, mode='w:gz') as archive:
                for n in range(count):
                    archive.addfile(tarfile.TarInfo('same.js' if duplicate else f'{n}.js'))
            with tempfile.TemporaryDirectory() as root, self.assertRaises(ValueError):
                unpack(out.getvalue(), Path(root))
        _, bundle = artifact()
        with patch('livelife.web.MAX_EXPANDED', 1), tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError, 'expanded'):
                unpack(bundle, Path(root))
        for bad in ['../main', 'pr-40', 'branch-x', 'branch-' + 'g' * 32]:
            with self.assertRaises(ValueError):
                environment(bad)
        with self.assertRaises(ValueError):
            build_id('fe-' + A + '-0-1')

    def test_publish_collects_expired_unused_build_before_applying_quota(self):
        manifest, bundle = artifact()
        with self.registry.locked() as db:
            self.registry.web.store(db, manifest, bundle)
            db.execute('UPDATE web_builds SET unused=?', (self.now - 11,))
        old = self.registry.web.root / 'builds' / manifest['build_id']
        self.registry.web.quota = self.registry.web.physical_bytes() + 2048
        self.publish(commit=B, generation=11)
        self.assertFalse(old.exists())

    def test_durable_candidate_ref_exists_before_gateway_promotion(self):
        original = self.runtime.publish
        def publish(routes):
            if '/preview/pr-40/' in routes:
                with sqlite3.connect(self.registry.root / 'registry.sqlite3') as db:
                    self.assertEqual(db.execute("SELECT count(*) FROM refs WHERE owner LIKE 'web:%'").fetchone()[0], 1)
                    env = json.loads(db.execute('SELECT data FROM web_envs WHERE id=?', (ENV,)).fetchone()[0])
                    self.assertFalse(env.get('current'))
            original(routes)
        self.runtime.publish = publish
        self.publish()

    def test_sigkill_after_gateway_switch_recovers_committed_page_before_cleanup(self):
        self.publish()
        root = str(self.registry.root)
        script = '''
import json, os, signal, sys
from pathlib import Path
from livelife.registry import Registry
from test_web import artifact, Runtime, A, B, ENV
runtime = Runtime()
runtime.health = lambda port: None
def publish(routes):
    Path(sys.argv[1], 'external-routes.json').write_text(json.dumps(routes))
    if routes.get('/preview/pr-40/', {}).get('config', {}).get('frontend_sha') == B:
        os.kill(os.getpid(), signal.SIGKILL)
runtime.publish = publish
r = Registry(sys.argv[1], runtime, 'https://192.144.253.40')
manifest, bundle = artifact(B, 11)
r.web.publish(dict(environment=ENV, branch='feature', pr=40, source_sha=B, generation=11,
                   target='staging', mode='staging', manifest=manifest, bundle=bundle))
'''
        env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(Path(__file__).resolve().parents[1]), str(Path(__file__).parent)]))
        child = subprocess.run([sys.executable, '-c', script, root], env=env, timeout=10)
        self.assertEqual(child.returncode, -signal.SIGKILL)
        external = json.loads((Path(root) / 'external-routes.json').read_text())
        self.assertEqual(external['/preview/pr-40/']['config']['frontend_sha'], B)
        self.assertEqual(self.registry.web.lookup(ENV)['frontend_sha'], A)
        self.assertEqual(len([r for r in self.registry.snapshot()['refs'] if r['owner'].startswith('web:')]), 2)
        self.registry.recover()
        self.assertEqual(self.runtime.routes['/preview/pr-40/']['config']['frontend_sha'], A)
        self.assertEqual(len([r for r in self.registry.snapshot()['refs'] if r['owner'].startswith('web:')]), 1)


if __name__ == '__main__':
    unittest.main()
