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


class BranchRegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.runtime = BranchRuntime()
        self.registry = Registry(self.temp.name, self.runtime, 'https://preview.test')

    def deploy(self, owner, branch, commit=A, generation=1, source='main'):
        return self.registry.deploy(owner, commit, generation, b'package', database={
            'branch': branch, 'source_branch': source})

    def test_same_commit_isolated_and_next_commit_reuses_branch_after_pr_open(self):
        main = self.deploy('main', 'main')
        one = self.deploy('branch:' + databases.branch_id('topic')[7:], 'topic')
        two = self.deploy('pr:2', 'other')
        self.assertEqual(len({main['instance'], one['instance'], two['instance']}), 3)
        latest = self.deploy('pr:1', 'topic', B, 2)
        self.assertEqual(self.runtime.databases[one['instance']], self.runtime.databases[latest['instance']])
        self.assertEqual(self.runtime.databases[two['instance']]['source'], databases.branch_id('main'))
        self.assertEqual(latest['backend_sha'], B)
        self.assertIn(databases.release_id(B, 'topic'), latest['api_path'])

    def test_legacy_import_is_preferred_over_main_and_survives_close(self):
        legacy = self.registry.deploy('pr:88', A, 1, b'package')
        first = self.deploy('pr:88', 'events', B, 2)
        self.assertEqual(self.runtime.databases[first['instance']]['source'], legacy['instance'])
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
