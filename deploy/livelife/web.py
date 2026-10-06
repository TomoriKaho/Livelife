"""Static releases and durable web/backend references, under Registry's lock."""
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import tarfile
import uuid

from .common import instance, sha

MAX_BUNDLE = 64 * 1024 * 1024
MAX_EXPANDED = 256 * 1024 * 1024
SHARED = {'.ttf', '.woff', '.woff2', '.png', '.jpg', '.jpeg', '.webp'}
STATIC = SHARED | {'.html', '.js', '.css', '.json', '.txt', '.md', '.svg', '.ico', '.map'}


def build_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'fe-[0-9a-f]{40}-[1-9][0-9]*-[1-9][0-9]*', value):
        raise ValueError('invalid immutable web build ID')
    return value


def environment(value):
    if not isinstance(value, str) or not re.fullmatch(r'main|branch-[0-9a-f]{32}', value):
        raise ValueError('invalid web environment')
    return value


def validate_manifest(value):
    if value.get('schema_version') != 1:
        raise ValueError('unsupported web artifact schema')
    sha(value['frontend_sha'])
    build_id(value['build_id'])
    if value['build_id'] != f"fe-{value['frontend_sha']}-{int(value['run_id'])}-{int(value['run_attempt'])}":
        raise ValueError('build identity mismatch')
    if not re.fullmatch('[0-9a-f]{64}', value.get('digest', '')):
        raise ValueError('invalid web bundle digest')
    return value


def unpack(bundle, destination):
    if len(bundle) > MAX_BUNDLE:
        raise ValueError('web bundle exceeds 64 MiB')
    total, count, seen = 0, 0, set()
    with tarfile.open(fileobj=io.BytesIO(bundle), mode='r:gz') as archive:
        for item in archive:
            count += 1
            name = PurePosixPath(item.name)
            if (count > 10000 or not re.fullmatch(r'[A-Za-z0-9_.\-/]+', item.name)
                or name.is_absolute() or any(p in ('.', '..') for p in item.name.split('/'))
                or str(name) != item.name or item.name in seen):
                raise ValueError('unsafe or duplicate static artifact path')
            seen.add(item.name)
            if not item.isfile() or name.suffix.lower() not in STATIC:
                raise ValueError('only regular static files are accepted')
            total += item.size
            if item.size < 0 or total > MAX_EXPANDED:
                raise ValueError('expanded web artifact exceeds 256 MiB')
            path = destination / item.name
            path.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(item) as source, path.open('xb') as target:
                shutil.copyfileobj(source, target)
    if 'index.html' not in seen:
        raise ValueError('missing web index.html')


class WebRegistry:
    def __init__(self, registry):
        self.registry = registry
        self.root = Path(getattr(registry.runtime, 'root', registry.root)) / 'web'
        self.quota = getattr(registry.runtime, 'config', {}).get('web_quota_bytes', 2 * 1024**3)

    @staticmethod
    def initialize(db):
        db.executescript('''
            CREATE TABLE IF NOT EXISTS web_builds (id TEXT PRIMARY KEY, data TEXT NOT NULL, unused REAL);
            CREATE TABLE IF NOT EXISTS web_envs (id TEXT PRIMARY KEY, data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS web_deployments (id TEXT PRIMARY KEY, data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS web_uploads (id TEXT PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS web_checks (id TEXT PRIMARY KEY, data TEXT NOT NULL);
        ''')

    @staticmethod
    def get(db, table, key):
        row = db.execute(f'SELECT data FROM {table} WHERE id=?', (key,)).fetchone()
        return None if row is None else json.loads(row[0])

    @staticmethod
    def save(db, table, key, value):
        db.execute(f'INSERT OR REPLACE INTO {table}(id,data) VALUES (?,?)', (key, json.dumps(value)))

    def physical_bytes(self):
        sizes = {}
        if self.root.exists():
            for path in self.root.rglob('*'):
                if path.is_file():
                    info = path.stat()
                    sizes[(info.st_dev, info.st_ino)] = info.st_size
        return sum(sizes.values())

    def store(self, db, manifest, bundle):
        validate_manifest(manifest)
        if bundle is None or len(bundle) > MAX_BUNDLE or hashlib.sha256(bundle).hexdigest() != manifest['digest']:
            raise ValueError('web bundle digest mismatch or size exceeded')
        # Duplicate push/PR builds of a SHA reuse its first complete artifact.
        for row in db.execute('SELECT data FROM web_builds'):
            previous = json.loads(row[0])
            if previous['frontend_sha'] == manifest['frontend_sha']:
                if (self.root / 'builds' / previous['build_id'] / 'index.html').is_file():
                    return previous['build_id']
        ident = build_id(manifest['build_id'])
        destination = self.root / 'builds' / ident
        # Reclaim only files whose grace period has passed. Expiring live routes
        # belongs to collect(), where a gateway publication is also performed.
        self.collect(db, expire=False)
        db.execute('INSERT OR IGNORE INTO web_uploads VALUES (?)', (ident,))
        db.commit()
        if destination.exists():
            # An interrupted upload may have left files but never a published build.
            shutil.rmtree(destination)
        destination.mkdir(parents=True)
        try:
            unpack(bundle, destination)
            prefix = f'/__livelife/web-builds/{ident}/assets/'
            if prefix not in (destination / 'index.html').read_text():
                raise ValueError('HTML does not reference its immutable build')
            for path in list(destination.rglob('*')):
                if not path.is_file():
                    continue
                if path.suffix.lower() in SHARED:
                    relative = path.relative_to(destination)
                    if relative.parts[0] != 'assets' or len(relative.parts) != 2:
                        raise ValueError('shared assets must have flat hashed asset names')
                    shared = self.root / 'shared' / relative
                    shared.parent.mkdir(parents=True, exist_ok=True)
                    if shared.exists():
                        if hashlib.sha256(shared.read_bytes()).digest() != hashlib.sha256(path.read_bytes()).digest():
                            raise ValueError('shared asset name collision')
                        path.unlink()
                        path.hardlink_to(shared)
                    else:
                        shared.hardlink_to(path)
                    compressed = shared.with_name(shared.name + '.gz')
                else:
                    compressed = path.with_name(path.name + '.gz')
                if path.suffix.lower() not in {'.png', '.jpg', '.jpeg', '.webp', '.ico', '.woff2'}:
                    if not compressed.exists():
                        compressed.write_bytes(gzip.compress(path.read_bytes(), compresslevel=6, mtime=0))
                    if path.suffix.lower() in SHARED:
                        path.with_name(path.name + '.gz').hardlink_to(compressed)
            if self.physical_bytes() > self.quota:
                raise ValueError('web storage quota exceeded; collect unused previews first')
            self.save(db, 'web_builds', ident, manifest)
            db.execute('DELETE FROM web_uploads WHERE id=?', (ident,))
            return ident
        except BaseException:
            shutil.rmtree(destination, ignore_errors=True)
            self.remove_unlinked_assets()
            db.execute('DELETE FROM web_uploads WHERE id=?', (ident,))
            db.commit()
            raise

    def remove_unlinked_assets(self):
        shared = self.root / 'shared'
        if shared.exists():
            for path in shared.rglob('*'):
                if path.is_file() and path.stat().st_nlink == 1:
                    path.unlink()

    def resolve(self, db, target):
        if target == 'staging':
            row = db.execute("SELECT instance FROM refs WHERE owner='main'").fetchone()
            if row is None:
                raise ValueError('staging backend is not deployed')
            ident = row[0]
        else:
            ident = instance(target)
        info = db.execute('SELECT * FROM instances WHERE id=?', (ident,)).fetchone()
        if info is None:
            raise ValueError('paired backend is not deployed')
        self.registry.runtime.health(info['port'])
        return None if target == 'staging' else ident, info['sha']

    def selected_target(self, db, env):
        key = 'frontend:' + (str(env['pr']) if env.get('pr') else env['id'])
        selected = db.execute('SELECT target FROM refs WHERE owner=?', (key,)).fetchone()
        if selected:
            return selected[0], 'staging' if selected[0] == 'staging' else 'fixed'
        return env.get('auto_target'), env.get('auto_mode', 'staging')

    def config(self, db, deployment):
        manifest = self.get(db, 'web_builds', deployment['build_id'])
        if deployment['target'] == 'staging':
            row = db.execute("SELECT i.sha FROM refs r JOIN instances i ON r.instance=i.id WHERE r.owner='main'").fetchone()
            if row is None:
                raise ValueError('staging is not deployed')
            commit = row[0]
        else:
            commit = deployment['target'][3:]
        path = '/api/staging/' if deployment['target'] == 'staging' else f"/api/versions/{deployment['target']}/"
        return {'schema_version': 1, 'environment': deployment['environment'],
                'frontend_sha': manifest['frontend_sha'], 'build_id': manifest['build_id'],
                'backend_mode': deployment['mode'], 'backend_sha': commit,
                'api_base_url': self.registry.base_url + path}

    def routes(self, db):
        result = {}
        for row in db.execute('SELECT data FROM web_envs'):
            env = json.loads(row[0])
            if env.get('closed') or not env.get('current'):
                continue
            deployment = self.get(db, 'web_deployments', env['current'])
            config = self.config(db, deployment)
            prefixes = ['/staging/'] if env['id'] == 'main' else [f"/preview/{env['id']}/"]
            if env.get('pr'):
                prefixes.append(f"/preview/pr-{env['pr']}/")
            for prefix in prefixes:
                result[prefix] = {'kind': 'web', 'build_id': deployment['build_id'],
                                  'deployment': deployment['id'], 'config': config, 'root': str(self.root)}
        return result

    def retire(self, db, ident):
        if not ident:
            return
        deployment = self.get(db, 'web_deployments', ident)
        if deployment is None:
            return
        deployment['role'] = 'unused'
        deployment['unused'] = self.registry.clock()
        self.save(db, 'web_deployments', ident, deployment)
        db.execute('DELETE FROM refs WHERE owner=?', ('web:' + ident,))

    def publish(self, request):
        key = environment(request['environment'])
        generation = request['generation']
        if not isinstance(generation, int) or generation < 0:
            raise ValueError('invalid web generation')
        with self.registry.locked() as db:
            env = self.get(db, 'web_envs', key) or {'id': key, 'content_generation': -1, 'close_generation': -1}
            if generation <= env['close_generation'] or (request.get('manifest') and generation < env['content_generation']):
                return {'status': 'superseded'}
            pr = request.get('pr')
            if pr is not None and (not isinstance(pr, int) or isinstance(pr, bool) or pr < 1 or key == 'main'):
                raise ValueError('invalid preview PR')
            source_sha = sha(request['source_sha'])
            if generation < env['content_generation'] and source_sha != env.get('source_sha'):
                return {'status': 'superseded'}
            manifest = request.get('manifest')
            if env.get('rolled_back') and not manifest:
                return self.describe(db, env)
            ident = self.store(db, manifest, request.get('bundle')) if manifest else request.get('build_id', env.get('desired_build'))
            if ident is not None and self.get(db, 'web_builds', build_id(ident)) is None:
                raise ValueError('unknown web build')
            env.update(branch=request['branch'], pr=pr, source_sha=source_sha, closed=False,
                       content_generation=generation if manifest else env['content_generation'], desired_build=ident,
                       auto_target=request.get('target'), auto_mode=request.get('mode', 'staging'),
                       expires=None if key == 'main' or pr else (
                           self.registry.clock() + self.registry.lease if request.get('renew', True) else env.get('expires')),
                       status=request.get('status', 'waiting'), error=request.get('error', ''))
            if pr:
                branch_key, pr_key = 'frontend:' + key, 'frontend:' + str(pr)
                branch_selection = db.execute('SELECT * FROM refs WHERE owner=?', (branch_key,)).fetchone()
                if branch_selection:
                    db.execute('INSERT OR IGNORE INTO refs VALUES (?, ?, ?, ?, NULL)',
                               (pr_key, branch_selection['instance'], branch_selection['target'], branch_selection['frontend_sha']))
                    db.execute('DELETE FROM refs WHERE owner=?', (branch_key,))
            if manifest:
                env['rolled_back'] = False
            if env['auto_mode'] not in ('staging', 'own'):
                raise ValueError('invalid automatic backend mode')
            self.save(db, 'web_envs', key, env)
            db.commit()  # Upload/desired state survive another component finishing later.
            target, mode = self.selected_target(db, env)
            failed = [json.loads(r[0]) for r in db.execute('SELECT data FROM web_checks')
                      if json.loads(r[0])['environment'] == key and json.loads(r[0])['source_sha'] == source_sha
                      and json.loads(r[0])['status'] != 'success'
                      and (json.loads(r[0])['component'] == 'frontend' or mode == 'own')]
            if failed:
                env.update(status='failed', error=' / '.join(r['component'] + ' ' + r['status'] for r in failed))
                self.save(db, 'web_envs', key, env)
            if not ident or not target or env['status'] == 'failed':
                return self.describe(db, env)
            return self.promote(db, env, ident, target, mode)

    def promote(self, db, env, ident, target, mode):
        backend, _ = self.resolve(db, target)
        current = self.get(db, 'web_deployments', env.get('current', ''))
        if current and (current['build_id'], current['target'], current['mode']) == (ident, target, mode):
            env.update(status='ready', error='')
            self.save(db, 'web_envs', env['id'], env)
            self.registry.publish(db, self.registry.routes(db))
            return self.describe(db, env)
        previous_routes = self.registry.routes(db)
        deployment = {'id': uuid.uuid4().hex, 'environment': env['id'], 'build_id': ident,
                      'target': target, 'mode': mode, 'role': 'candidate', 'created': self.registry.clock()}
        self.save(db, 'web_deployments', deployment['id'], deployment)
        db.execute('INSERT INTO refs VALUES (?, ?, ?, ?, NULL)',
                   ('web:' + deployment['id'], backend, target, self.get(db, 'web_builds', ident)['frontend_sha']))
        db.commit()  # Durable candidate pin before publishing any external files/routes.
        try:
            self.retire(db, env.get('previous'))
            if current:
                current['role'] = 'previous'
                self.save(db, 'web_deployments', current['id'], current)
            deployment['role'] = 'current'
            self.save(db, 'web_deployments', deployment['id'], deployment)
            env.update(previous=env.get('current'), current=deployment['id'], status='ready', error='')
            self.save(db, 'web_envs', env['id'], env)
            self.registry.mark_unused(db)
            self.registry.publish(db, previous_routes)
            return self.describe(db, env)
        except Exception as error:
            db.rollback()
            self.retire(db, deployment['id'])
            failed_env = self.get(db, 'web_envs', env['id'])
            failed_env.update(status='failed', error=str(error)[:500])
            self.save(db, 'web_envs', env['id'], failed_env)
            self.registry.mark_unused(db)
            db.commit()
            raise

    def describe(self, db, env):
        result = {k: env.get(k) for k in ('id', 'branch', 'pr', 'source_sha', 'status', 'error', 'expires',
                  'desired_build', 'last_build', 'content_generation', 'closed', 'rolled_back')}
        result['frontend_url'] = self.registry.base_url + ('/staging/' if env['id'] == 'main' else
                                    f"/preview/pr-{env['pr']}/" if env.get('pr') else f"/preview/{env['id']}/")
        result['checks'] = [json.loads(r[0]) for r in db.execute('SELECT data FROM web_checks')
                            if json.loads(r[0])['environment'] == env['id']
                            and json.loads(r[0])['source_sha'] == env.get('source_sha')]
        if not env.get('closed') and env.get('current'):
            result.update(self.config(db, self.get(db, 'web_deployments', env['current'])))
        return result

    def lookup(self, key):
        with self.registry.locked() as db:
            env = self.get(db, 'web_envs', environment(key))
            return {'status': 'missing'} if env is None else self.describe(db, env)

    def close(self, db, key, generation):
        if key == 'main':
            raise ValueError('shared frontend cannot be released')
        env = self.get(db, 'web_envs', environment(key)) or {'id': key, 'content_generation': -1, 'close_generation': -1}
        if generation < max(env['content_generation'], env['close_generation']):
            return {'status': 'superseded'}
        self.retire(db, env.get('current'))
        self.retire(db, env.get('previous'))
        for row in list(db.execute('SELECT id,data FROM web_deployments')):
            dep = json.loads(row['data'])
            if dep['environment'] == key and dep['role'] == 'candidate':
                self.retire(db, row['id'])
        db.execute('DELETE FROM refs WHERE owner=?', ('frontend:' + (str(env['pr']) if env.get('pr') else key),))
        db.execute('DELETE FROM refs WHERE owner=?', ('frontend:' + key,))
        env.update(closed=True, close_generation=generation, status='released', last_build=env.get('desired_build'), desired_build=None,
                   current=None, previous=None, expires=None, error='')
        self.save(db, 'web_envs', key, env)
        return {'status': 'released', 'environment': key}

    def release(self, key, generation):
        with self.registry.locked() as db:
            previous = self.registry.routes(db)
            result = self.close(db, key, generation)
            self.registry.mark_unused(db)
            self.registry.publish(db, previous)
            return result

    def rollback(self, key, generation):
        with self.registry.locked() as db:
            env = self.get(db, 'web_envs', environment(key))
            if not env or env.get('closed') or not env.get('previous'):
                raise ValueError('no previous web deployment')
            if generation < env['content_generation']:
                return {'status': 'superseded'}
            previous_routes = self.registry.routes(db)
            env['current'], env['previous'] = env['previous'], env['current']
            env['content_generation'] = generation
            current = self.get(db, 'web_deployments', env['current'])
            self.resolve(db, current['target'])
            env.update(desired_build=current['build_id'], status='ready', error='', rolled_back=True)
            for field in ('current', 'previous'):
                dep = self.get(db, 'web_deployments', env[field])
                dep['role'] = field
                self.save(db, 'web_deployments', dep['id'], dep)
            self.save(db, 'web_envs', key, env)
            self.registry.publish(db, previous_routes)
            return self.describe(db, env)

    def recover(self, db):
        # Restore committed routes BEFORE releasing unpublished candidate pins.
        self.registry.runtime.publish(self.registry.routes(db))
        for row in list(db.execute('SELECT id,data FROM web_deployments')):
            if json.loads(row['data'])['role'] == 'candidate':
                self.retire(db, row['id'])
        self.registry.mark_unused(db)
        for row in list(db.execute('SELECT id FROM web_uploads')):
            if self.get(db, 'web_builds', row['id']) is None:
                shutil.rmtree(self.root / 'builds' / build_id(row['id']), ignore_errors=True)
            db.execute('DELETE FROM web_uploads WHERE id=?', (row['id'],))
        self.remove_unlinked_assets()

    def note(self, request):
        key = environment(request['environment'])
        if request['component'] not in ('frontend', 'backend') or request['status'] not in ('success', 'failure', 'cancelled'):
            raise ValueError('invalid build status')
        sha(request['source_sha'])
        ident = key + ':' + request['component']
        with self.registry.locked() as db:
            prior = self.get(db, 'web_checks', ident)
            if prior is None or prior['generation'] <= request['generation']:
                self.save(db, 'web_checks', ident, {k: request[k] for k in
                    ('environment', 'component', 'source_sha', 'status', 'generation')})
            return {'status': 'recorded'}

    def collect(self, db, expire=True):
        now = self.registry.clock()
        for row in list(db.execute('SELECT id,data FROM web_envs')):
            env = json.loads(row['data'])
            if expire and env.get('expires') is not None and env['expires'] <= now:
                self.close(db, row['id'], env['content_generation'])
        for row in list(db.execute('SELECT id,data FROM web_deployments')):
            dep = json.loads(row['data'])
            if dep['role'] == 'unused' and dep['unused'] + self.registry.grace <= now:
                shutil.rmtree(self.root / 'deployments' / row['id'], ignore_errors=True)
                db.execute('DELETE FROM web_deployments WHERE id=?', (row['id'],))
        used = {json.loads(r[0])['build_id'] for r in db.execute('SELECT data FROM web_deployments')}
        used.update(json.loads(r[0]).get('desired_build') for r in db.execute('SELECT data FROM web_envs'))
        for row in list(db.execute('SELECT * FROM web_builds')):
            if row['id'] in used:
                db.execute('UPDATE web_builds SET unused=NULL WHERE id=?', (row['id'],))
            elif row['unused'] is None:
                db.execute('UPDATE web_builds SET unused=? WHERE id=?', (now, row['id']))
            elif row['unused'] + self.registry.grace <= now:
                shutil.rmtree(self.root / 'builds' / build_id(row['id']), ignore_errors=True)
                db.execute('DELETE FROM web_builds WHERE id=?', (row['id'],))
        self.remove_unlinked_assets()

    def snapshot(self, db):
        return {'web_environments': [self.describe(db, json.loads(r[0])) for r in db.execute('SELECT data FROM web_envs')],
                'web_builds': [json.loads(r[0]) for r in db.execute('SELECT data FROM web_builds')]}
