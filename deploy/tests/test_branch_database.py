"""Branch identity, upgrade provenance and opt-in real snapshot lifecycle."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from livelife import branch_database as databases
from livelife.registry import Registry
from livelife.backend_runtime import runtime_environment
from test_registry import Runtime, A, B, C


class BranchRuntime(Runtime):
    def __init__(self):
        super().__init__()
        self.databases = {}

    def ensure(self, ident, commit, port, bundle, database=None):
        self.databases[ident] = database
        super().ensure(ident, commit, port, bundle)


def published_web_configs():
    """Real registry publication output shared with the frontend contract test."""
    from test_web import artifact
    with tempfile.TemporaryDirectory() as root:
        runtime = BranchRuntime()
        registry = Registry(root, runtime, 'https://preview.test')
        registry.deploy('main', A, 1, b'package', database={'branch': 'main', 'source_branch': 'main'})
        branch = registry.deploy('pr:2', B, 1, b'package', database={'branch': 'topic', 'source_branch': 'main'})
        legacy = registry.deploy('pr:3', C, 1, b'package')
        results = []
        for index, (mode, target, expected) in enumerate([
            ('own', branch['instance'], B),
            ('fixed', branch['instance'], B),
            ('fixed', legacy['instance'], C),
            ('staging', 'staging', A),
        ]):
            pr = 40 + index
            environment = 'branch-' + str(index) * 32
            if mode == 'fixed':
                registry.bind('frontend:' + str(pr), target, 2)
            manifest, bundle = artifact(A, index + 1)
            result = registry.web.publish(dict(
                environment=environment, branch='web-' + str(index), pr=pr,
                source_sha=A, generation=3, target=target, mode='staging' if mode == 'staging' else 'own',
                manifest=manifest, bundle=bundle,
            ))
            config = runtime.routes[f'/preview/pr-{pr}/']['config']
            results.append({'status': result['status'], 'expected_sha': expected,
                            'target': target, 'mode': mode, 'config': config})
        return results


class BranchRegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.runtime = BranchRuntime()
        self.registry = Registry(self.temp.name, self.runtime, 'https://preview.test')

    def deploy(self, owner, branch, commit=A, generation=1, source='main'):
        return self.registry.deploy(owner, commit, generation, b'package', database={
            'branch': branch, 'source_branch': source})

    def test_web_publication_uses_registered_sha_for_branch_and_legacy_instances(self):
        for result in published_web_configs():
            with self.subTest(mode=result['mode'], target=result['target']):
                self.assertEqual(result['status'], 'ready')
                config = result['config']
                self.assertEqual(config['backend_sha'], result['expected_sha'])
                self.assertEqual(len(config['backend_sha']), 40)
                self.assertEqual(config['backend_mode'], result['mode'])
                path = '/api/staging/' if result['mode'] == 'staging' else f"/api/versions/{result['target']}/"
                self.assertEqual(config['api_base_url'], 'https://preview.test' + path)

    def test_same_commit_isolated_and_next_commit_reuses_branch_after_pr_open(self):
        main = self.deploy('main', 'main')
        one = self.deploy('branch:' + databases.branch_id('topic')[7:], 'topic')
        two = self.deploy('pr:2', 'other')
        self.assertEqual(len({main['instance'], one['instance'], two['instance']}), 3)
        latest = self.deploy('pr:1', 'topic', B, 2)
        self.assertEqual(self.runtime.databases[one['instance']], self.runtime.databases[latest['instance']])
        self.assertEqual(self.runtime.databases[two['instance']]['source'], databases.branch_id('main'))
        self.assertEqual(self.runtime.databases[two['instance']]['copy_mode'], 'public')
        self.assertEqual(latest['backend_sha'], B)
        self.assertIn(databases.release_id(B, 'topic'), latest['api_path'])

    def test_legacy_import_is_preferred_over_main_and_survives_close(self):
        legacy = self.registry.deploy('pr:88', A, 1, b'package')
        first = self.deploy('pr:88', 'events', B, 2)
        self.assertEqual(self.runtime.databases[first['instance']]['source'], legacy['instance'])
        self.assertEqual(self.runtime.databases[first['instance']]['copy_mode'], 'full')
        self.registry.release('pr:88', 3)
        new = self.deploy('pr:88', 'events', C, 4, source='different-base')
        self.assertEqual(self.runtime.databases[first['instance']], self.runtime.databases[new['instance']])

    def test_missing_source_fails_without_routes_or_empty_database(self):
        with self.assertRaisesRegex(ValueError, 'source branch'):
            self.deploy('pr:2', 'topic')
        self.assertEqual(self.registry.snapshot()['instances'], [])
        self.assertEqual(self.registry.snapshot()['branch_databases'], [])

    def test_failed_candidate_preserves_old_reference_and_database_assignment(self):
        self.deploy('main', 'main')
        old = self.deploy('pr:2', 'topic')
        self.runtime.fail_start = True
        with self.assertRaises(RuntimeError):
            self.deploy('pr:2', 'topic', B, 2)
        self.assertEqual(self.registry.lookup('pr:2')['instance'], old['instance'])
        self.assertEqual(len(self.registry.snapshot()['branch_databases']), 2)

    def test_stacked_branch_inherits_base_and_session_secret_is_branch_scoped(self):
        self.deploy('main', 'main')
        self.deploy('pr:1', 'base', B)
        child = self.deploy('pr:2', 'child', C, source='base')
        self.assertEqual(self.runtime.databases[child['instance']]['source'], databases.branch_id('base'))
        with tempfile.TemporaryDirectory() as path:
            env = runtime_environment('test', databases.release_id(A, 'child'), Path(path))
            later = runtime_environment('test', databases.release_id(B, 'child'), Path(path))
            self.assertEqual(env['LIVELIFE_BACKEND_SHA'], A)
            self.assertEqual(env['AGENT_SESSION_SECRET'], later['AGENT_SESSION_SECRET'])

    def test_missing_initialized_cluster_never_creates_an_empty_replacement(self):
        specification = {'id': databases.branch_id('main'), 'branch': 'main', 'source': None, 'source_branch': 'main'}
        state = databases.directory(self.temp.name, specification['id'])
        state.mkdir()
        (state / 'initialized.json').write_text(json.dumps(specification))
        with patch('livelife.branch_database.snapshot') as snapshot, patch('builtins.print'):
            def forbidden(*args, **kwargs):
                self.fail('must not create a new PostgreSQL')
            with self.assertRaisesRegex(ValueError, 'missing'):
                with databases.prepared_database(self.temp.name, specification, forbidden, forbidden):
                    self.fail('must not publish')
            snapshot.assert_not_called()

    def test_preview_cannot_claim_main_database(self):
        with self.assertRaisesRegex(ValueError, 'main deployment owner'):
            self.deploy('pr:2', 'main')

    def test_full_copy_cannot_be_requested_for_a_new_branch(self):
        with self.assertRaisesRegex(ValueError, 'invalid database request'):
            databases.validate_request({'branch': 'topic', 'source_branch': 'main', 'copy_mode': 'full'})
        with self.assertRaisesRegex(ValueError, 'same branch'):
            databases.validate_specification({'id': databases.branch_id('topic'), 'branch': 'topic',
                'source': 'be-' + A, 'source_branch': 'main', 'copy_mode': 'full'})

    def test_main_and_branch_lease_adoption_preserve_all_data(self):
        for key, branch in [('main', 'main'), ('branch:' + databases.branch_id('lease')[7:], 'lease')]:
            old = self.registry.deploy(key, A, 1, b'package')
            new = self.deploy(key, branch, B, 2)
            specification = self.runtime.databases[new['instance']]
            self.assertEqual(specification['copy_mode'], 'full')
            self.assertEqual(specification['source'], old['instance'])
            self.assertEqual(specification['source_branch'], branch)

    def test_course_recovery_preserves_branch_assignment_and_sha(self):
        from livelife.course import Course
        course = Course(self.temp.name)
        ident = databases.release_id(A, 'main')
        specification = {'id': databases.branch_id('main'), 'branch': 'main', 'source': None, 'source_branch': 'main'}
        release = course.releases / ident
        release.mkdir()
        metadata = release / 'release.json'
        metadata.write_text(json.dumps({'sha': A, 'port': 18000, 'runtime_mode': 'postgres-v1', 'database': specification}))
        with patch.object(course.supervisor, 'configure') as configure, patch('livelife.course.check_health') as health:
            course.handle({'op': 'ensure', 'instance': ident, 'sha': A, 'port': 18000})
            self.assertIn(ident, configure.call_args.args[1])
            self.assertEqual(configure.call_args.args[3], f'LIVELIFE_BACKEND_SHA="{A}"')
            health.assert_called_once_with(18000, timeout=600, require_database=True)
        different = {**specification, 'source': 'be-' + B}
        with self.assertRaisesRegex(ValueError, 'immutable database'):
            course.handle({'op': 'ensure', 'instance': ident, 'sha': A, 'port': 18000, 'database': different})
        self.assertEqual(json.loads(metadata.read_text())['database'], specification)



@unittest.skipUnless(os.environ.get('LIVELIFE_BRANCH_DB_INTEGRATION') == '1', 'opt-in real PostgreSQL')
class RealBranchDatabaseTests(unittest.TestCase):
    def setUp(self):
        import pgembed
        import psycopg
        self.server_factory = pgembed.get_server
        self.connect = psycopg.connect
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.main = {'id': databases.branch_id('main'), 'branch': 'main', 'source': None, 'source_branch': 'main'}
        self.child = {'id': databases.branch_id('topic'), 'branch': 'topic', 'source': self.main['id'], 'source_branch': 'main'}

    def migrate(self, server, state):
        with self.connect(server.get_uri(database='postgres')) as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS information_items (id integer primary key, content text)')
            conn.execute('CREATE TABLE IF NOT EXISTS users (id integer primary key, email text)')
            conn.execute('CREATE TABLE IF NOT EXISTS unknown_private_table (secret text)')
            conn.execute('CREATE TABLE IF NOT EXISTS alembic_version (version_num text primary key)')
            conn.execute("INSERT INTO alembic_version VALUES ('first') ON CONFLICT DO NOTHING")
        runtime_environment('test', databases.release_id(A, 'topic'), state)

    def prepared(self, specification, migrate=None):
        return databases.prepared_database(self.root, specification, self.server_factory, migrate or self.migrate)

    def test_snapshot_privacy_isolation_reuse_and_forward_schema_change(self):
        with self.prepared(self.main) as (main, _):
            with self.connect(main.get_uri(database='postgres')) as conn:
                conn.execute("INSERT INTO information_items VALUES (1, 'real event')")
                conn.execute("INSERT INTO users VALUES (1, 'private@example.test')")
                conn.execute("INSERT INTO unknown_private_table VALUES ('do not copy')")
            with self.prepared(self.child) as (child, state):
                with self.connect(child.get_uri(database='postgres')) as conn:
                    self.assertEqual(conn.execute('SELECT content FROM information_items').fetchone()[0], 'real event')
                    self.assertEqual(conn.execute('SELECT count(*) FROM users').fetchone()[0], 0)
                    self.assertEqual(conn.execute('SELECT count(*) FROM unknown_private_table').fetchone()[0], 0)
                    conn.execute("INSERT INTO information_items VALUES (2, 'branch event')")
                provenance = json.loads((state / 'initialized.json').read_text())
            def upgrade(server, state):
                self.migrate(server, state)
                with self.connect(server.get_uri(database='postgres')) as conn:
                    conn.execute('ALTER TABLE information_items ADD COLUMN IF NOT EXISTS place text')
            with patch('livelife.branch_database.snapshot', side_effect=AssertionError('must not recopy')):
                with self.prepared(self.child, upgrade) as (child, state):
                    with self.connect(child.get_uri(database='postgres')) as conn:
                        self.assertEqual(conn.execute('SELECT count(*) FROM information_items').fetchone()[0], 2)
                        conn.execute('SELECT place FROM information_items')
                    self.assertEqual(json.loads((state / 'initialized.json').read_text()), provenance)
            with self.connect(main.get_uri(database='postgres')) as conn:
                self.assertEqual(conn.execute('SELECT count(*) FROM information_items').fetchone()[0], 1)
                self.assertEqual(conn.execute('SELECT count(*) FROM users').fetchone()[0], 1)

    def test_same_branch_adoption_preserves_accounts_chats_unknown_tables_blobs_and_secret(self):
        legacy = databases.directory(self.root, 'be-' + A)
        legacy.mkdir()
        specification = {'id': databases.branch_id('topic'), 'branch': 'topic',
                         'source': 'be-' + A, 'source_branch': 'topic', 'copy_mode': 'full'}
        with self.server_factory(legacy / 'postgres', cleanup_mode='stop') as server:
            self.migrate(server, legacy)
            old_secret = json.loads((legacy / 'runtime.json').read_text())['agent_session_secret']
            with self.connect(server.get_uri(database='postgres')) as conn:
                conn.execute("INSERT INTO users VALUES (7, 'account@example.test')")
                conn.execute('CREATE TABLE user_sessions (token text, user_id integer REFERENCES users(id))')
                conn.execute("INSERT INTO user_sessions VALUES ('existing-token-hash', 7)")
                conn.execute('CREATE TABLE agent_sessions (user_id integer REFERENCES users(id), messages jsonb)')
                conn.execute('INSERT INTO agent_sessions VALUES (7, %s)', ('[{"role":"user","content":"saved chat"}]',))
                conn.execute("INSERT INTO unknown_private_table VALUES ('future private record')")
                conn.execute("SELECT lo_from_bytea(12345, convert_to('private attachment', 'UTF8'))")
        def verify(server, state):
            self.migrate(server, state)
            with self.connect(server.get_uri(database='postgres')) as conn:
                self.assertEqual(conn.execute('SELECT * FROM users').fetchall(), [(7, 'account@example.test')])
                self.assertEqual(conn.execute('SELECT * FROM user_sessions').fetchall(), [('existing-token-hash', 7)])
                self.assertEqual(conn.execute('SELECT messages FROM agent_sessions').fetchone()[0],
                                 [{'role': 'user', 'content': 'saved chat'}])
                self.assertEqual(conn.execute('SELECT * FROM unknown_private_table').fetchone()[0], 'future private record')
                self.assertEqual(conn.execute("SELECT convert_from(lo_get(12345), 'UTF8')").fetchone()[0], 'private attachment')
            self.assertEqual(json.loads((state / 'runtime.json').read_text())['agent_session_secret'], old_secret)
        for _ in range(2):
            with self.prepared(specification, verify) as (_, state):
                self.assertEqual(json.loads((state / 'initialized.json').read_text())['copy_mode'], 'full')
        self.assertTrue((legacy / 'postgres/PG_VERSION').exists())
        # Forking the adopted branch must still sanitize all private records.
        fork = {'id': databases.branch_id('new-topic'), 'branch': 'new-topic',
                'source': specification['id'], 'source_branch': 'topic', 'copy_mode': 'public'}
        with self.prepared(fork) as (server, state):
            with self.connect(server.get_uri(database='postgres')) as conn:
                for table in ('users', 'user_sessions', 'agent_sessions', 'unknown_private_table'):
                    self.assertEqual(conn.execute('SELECT count(*) FROM ' + table).fetchone()[0], 0)
                self.assertEqual(conn.execute('SELECT count(*) FROM pg_largeobject_metadata').fetchone()[0], 0)
            self.assertNotEqual(json.loads((state / 'runtime.json').read_text())['agent_session_secret'], old_secret)

    def test_adoption_without_original_secret_fails_without_publishing(self):
        legacy = databases.directory(self.root, 'be-' + A)
        legacy.mkdir()
        with self.server_factory(legacy / 'postgres', cleanup_mode='stop') as server:
            self.migrate(server, legacy)
        (legacy / 'runtime.json').unlink()
        specification = {'id': databases.branch_id('topic'), 'branch': 'topic',
                         'source': 'be-' + A, 'source_branch': 'topic', 'copy_mode': 'full'}
        with self.assertRaisesRegex(ValueError, 'original runtime settings'):
            with self.prepared(specification):
                self.fail('must not publish')
        self.assertFalse((databases.directory(self.root, specification['id']) / 'initialized.json').exists())

    def test_initialization_failure_can_retry_without_publishing_partial_database(self):
        with self.prepared(self.main):
            pass
        def broken(server, state):
            self.migrate(server, state)
            raise RuntimeError('migration failed')
        with self.assertRaisesRegex(RuntimeError, 'migration failed'):
            with self.prepared(self.child, broken):
                self.fail('must not publish')
        state = databases.directory(self.root, self.child['id'])
        self.assertFalse((state / 'initialized.json').exists())
        with self.prepared(self.child):
            pass
        self.assertTrue((state / 'initialized.json').exists())

    def test_real_repository_alembic_migrations_on_first_and_repeat_deploy(self):
        from livelife.backend_runtime import prepare_schema
        backend = Path(__file__).resolve().parents[2] / 'backend'
        def migrate(server, state):
            env = runtime_environment(server.get_uri(database='postgres').replace('postgresql://', 'postgresql+psycopg://'), 'be-' + A, state)
            prepare_schema(Path(sys.executable), backend, env)
        for specification in (self.main, self.child, self.child):
            with self.prepared(specification, migrate) as (server, _):
                with self.connect(server.get_uri(database='postgres')) as conn:
                    self.assertTrue(conn.execute('SELECT version_num FROM alembic_version').fetchone())

    def test_different_process_keeps_shared_postgres_alive_after_old_handle_closes(self):
        import subprocess
        script = """
import sys
from pathlib import Path
from pgembed import get_server
import psycopg
with get_server(Path(sys.argv[1]), cleanup_mode='stop') as server:
    print('ready', flush=True)
    sys.stdin.readline()
    with psycopg.connect(server.get_uri(database='postgres')) as connection:
        assert connection.execute('SELECT count(*) FROM information_items').fetchone()[0] == 0
    print('alive', flush=True)
"""
        with self.prepared(self.main) as (_, state):
            child = subprocess.Popen([sys.executable, '-c', script, str(state / 'postgres')],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                import select
                self.assertTrue(select.select([child.stdout], [], [], 20)[0], 'child did not start')
                self.assertEqual(child.stdout.readline().strip(), 'ready')
            except BaseException:
                child.kill()
                child.communicate()
                raise
        try:
            out, err = child.communicate('continue\n', timeout=20)
            self.assertEqual(child.returncode, 0, err)
            self.assertIn('alive', out)
        finally:
            if child.poll() is None:
                child.kill()
                child.communicate()
