"""Persistent references, immutable backend versions, and serial deployment.

The manager holds the file lock through external operations as well as the SQL
transaction. Browser connections never affect retention. Runtime failures leave
the previous references/routes intact and are returned to the workflow.
"""
from contextlib import contextmanager
import fcntl
from pathlib import Path
import sqlite3
import time

from .common import instance, owner, sha


class Registry:
    def __init__(self, root, runtime, base_url, port_start=18000, slots=64,
                 grace=3600, lease=259200, clock=time.time):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.runtime = runtime
        self.base_url = base_url.rstrip("/")
        self.port_start = port_start
        self.slots = slots
        self.grace = grace
        self.lease = lease
        self.clock = clock
        with self.locked() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS instances (
                    id TEXT PRIMARY KEY, sha TEXT NOT NULL, port INTEGER UNIQUE,
                    created REAL NOT NULL, unreferenced REAL);
                CREATE TABLE IF NOT EXISTS refs (
                    owner TEXT PRIMARY KEY, instance TEXT REFERENCES instances(id),
                    target TEXT NOT NULL, frontend_sha TEXT, expires REAL);
                CREATE TABLE IF NOT EXISTS generations (
                    owner TEXT PRIMARY KEY, generation INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS retirements (
                    id TEXT PRIMARY KEY, port INTEGER UNIQUE);
            """)

    @contextmanager
    def locked(self):
        with (self.root / "manager.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            db = sqlite3.connect(self.root / "registry.sqlite3", timeout=60)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            try:
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise
            finally:
                db.close()

    def current(self, db, key, generation):
        owner(key)
        if not isinstance(generation, int) or generation < 0:
            raise ValueError("invalid workflow generation")
        previous = db.execute("SELECT generation FROM generations WHERE owner=?", (key,)).fetchone()
        return previous is None or generation >= previous[0]

    def stamp(self, db, key, generation):
        db.execute("INSERT OR REPLACE INTO generations VALUES (?, ?)", (key, generation))

    def routes(self, db):
        result = {}
        for row in db.execute("SELECT * FROM instances"):
            result[f"/api/versions/{row['id']}/"] = dict(row)
        for row in db.execute("SELECT r.owner, i.* FROM refs r JOIN instances i ON r.instance=i.id"):
            if row["owner"] == "main":
                result["/api/staging/"] = dict(row)
            elif row["owner"].startswith("pr:"):
                result[f"/api/pr-{row['owner'].split(':')[1]}/"] = dict(row)
        return result

    def publish(self, db, previous):
        try:
            self.runtime.publish(self.routes(db))
        except Exception:
            # Runtime.publish must validate before reloading. Restore even when
            # the reload itself failed; don't advertise a failed candidate.
            self.runtime.publish(previous)
            raise

    def mark_unused(self, db):
        now = self.clock()
        db.execute("""UPDATE instances SET unreferenced=NULL
            WHERE id IN (SELECT instance FROM refs WHERE instance IS NOT NULL)""")
        db.execute("""UPDATE instances SET unreferenced=? WHERE unreferenced IS NULL
            AND id NOT IN (SELECT instance FROM refs WHERE instance IS NOT NULL)""", (now,))

    def deploy(self, key, commit, generation, bundle):
        owner(key)
        if key.startswith("frontend:"):
            raise ValueError("frontend owners use bind")
        sha(commit)
        ident = f"be-{commit}"
        with self.locked() as db:
            if not self.current(db, key, generation):
                return {"status": "superseded"}
            if db.execute("SELECT 1 FROM retirements WHERE id=?", (ident,)).fetchone():
                raise ValueError("version cleanup is pending; run collect before redeploying it")
            previous = self.routes(db)
            row = db.execute("SELECT * FROM instances WHERE id=?", (ident,)).fetchone()
            created = row is None
            if created:
                used = {r[0] for r in db.execute("SELECT port FROM instances UNION SELECT port FROM retirements")}
                port = next((p for p in range(self.port_start, self.port_start + self.slots)
                             if p not in used and self.runtime.port_available(p)), None)
                if port is None:
                    raise RuntimeError("backend port pool exhausted; release unused previews first")
            else:
                port = row["port"]
            try:
                # Existing versions are recovered and health checked, not replaced.
                self.runtime.ensure(ident, commit, port, bundle if created else None)
                if created:
                    db.execute("INSERT INTO instances VALUES (?, ?, ?, ?, NULL)",
                               (ident, commit, port, self.clock()))
                expires = self.clock() + self.lease if key.startswith("branch:") else None
                db.execute("INSERT OR REPLACE INTO refs VALUES (?, ?, ?, NULL, ?)",
                           (key, ident, ident, expires))
                self.stamp(db, key, generation)
                self.mark_unused(db)
                self.publish(db, previous)
            except Exception:
                if created:
                    try:
                        self.runtime.remove(ident, port)
                    except Exception:
                        # Even a failed candidate may have started remotely.
                        # Roll back its publication, persist a cleanup reservation.
                        db.rollback()
                        db.execute("INSERT OR IGNORE INTO retirements VALUES (?, ?)", (ident, port))
                        db.commit()
                raise
            return self.describe(db, key)

    def bind(self, key, target, generation, frontend_sha=None):
        owner(key)
        if not key.startswith("frontend:"):
            raise ValueError("only frontend owners can bind")
        if frontend_sha is not None:
            sha(frontend_sha)
        with self.locked() as db:
            if not self.current(db, key, generation):
                return {"status": "superseded"}
            if target == "staging":
                stage = db.execute("SELECT instance FROM refs WHERE owner='main'").fetchone()
                if stage is None:
                    raise ValueError("staging is not deployed")
                stage_info = db.execute("SELECT port FROM instances WHERE id=?", (stage[0],)).fetchone()
                self.runtime.health(stage_info[0])
                ident = None  # Explicitly follow main; never fallback from a pinned version.
            elif isinstance(target, str) and target.startswith("pr:"):
                owner(target)
                row = db.execute("SELECT instance FROM refs WHERE owner=?", (target,)).fetchone()
                if row is None:
                    raise ValueError("target backend PR has no deployed version")
                ident = row[0]
            else:
                ident = instance(target)
            if ident is not None:
                row = db.execute("SELECT * FROM instances WHERE id=?", (ident,)).fetchone()
                if row is None:
                    raise ValueError("target version has been released; deploy it before binding")
                self.runtime.health(row["port"])
            db.execute("INSERT OR REPLACE INTO refs VALUES (?, ?, ?, ?, NULL)",
                       (key, ident, target, frontend_sha))
            self.stamp(db, key, generation)
            self.mark_unused(db)
            return self.describe(db, key)

    def release(self, key, generation):
        owner(key)
        if key == "main":
            raise ValueError("staging cannot be released")
        with self.locked() as db:
            if not self.current(db, key, generation):
                return {"status": "superseded"}
            previous = self.routes(db)
            db.execute("DELETE FROM refs WHERE owner=?", (key,))
            self.stamp(db, key, generation)  # Tombstone rejects late build completions.
            self.mark_unused(db)
            self.publish(db, previous)
            return {"status": "released", "owner": key}

    def collect(self):
        with self.locked() as db:
            previous = self.routes(db)
            db.execute("DELETE FROM refs WHERE expires IS NOT NULL AND expires<=?", (self.clock(),))
            self.mark_unused(db)
            rows = db.execute("SELECT * FROM instances WHERE unreferenced IS NOT NULL AND unreferenced<=?",
                              (self.clock() - self.grace,)).fetchall()
            for row in rows:
                db.execute("INSERT INTO retirements VALUES (?, ?)", (row["id"], row["port"]))
                db.execute("DELETE FROM instances WHERE id=?", (row["id"],))
            self.publish(db, previous)
            # Persist a cleanup outbox BEFORE destructive external operations.
            # Failed cleanup retains its port reservation and is retried next run.
            db.commit()
            pending = db.execute("SELECT * FROM retirements").fetchall()
            for row in pending:
                self.runtime.remove(row["id"], row["port"])
                db.execute("DELETE FROM retirements WHERE id=?", (row["id"],))
                db.commit()
            return {"status": "collected", "instances": [r["id"] for r in pending]}

    def describe(self, db, key):
        row = db.execute("SELECT * FROM refs WHERE owner=?", (key,)).fetchone()
        if row is None:
            raise ValueError("owner has no active deployment or binding")
        ident = row["instance"]
        if ident is None:
            ident = db.execute("SELECT instance FROM refs WHERE owner='main'").fetchone()[0]
        info = db.execute("SELECT * FROM instances WHERE id=?", (ident,)).fetchone()
        path = "/api/staging/" if row["target"] == "staging" or key == "main" else f"/api/versions/{ident}/"
        return {"status": "ready", "owner": key, "instance": ident, "backend_sha": info["sha"],
                "frontend_sha": row["frontend_sha"], "api_base_url": self.base_url + path,
                "api_path": path, "expires": row["expires"]}

    def lookup(self, key):
        with self.locked() as db:
            return self.describe(db, owner(key))

    def snapshot(self):
        with self.locked() as db:
            return {"instances": [dict(r) for r in db.execute("SELECT * FROM instances")],
                    "refs": [dict(r) for r in db.execute("SELECT * FROM refs")],
                    "retirements": [dict(r) for r in db.execute("SELECT * FROM retirements")]}

    def recover(self):
        failures = []
        with self.locked() as db:
            for row in db.execute("SELECT * FROM instances"):
                try:
                    self.runtime.ensure(row["id"], row["sha"], row["port"], None)
                except Exception as error:
                    failures.append({"instance": row["id"], "error": str(error)})
            self.runtime.publish(self.routes(db))
        if failures:
            raise RuntimeError(f"unhealthy backend instances: {failures}")
        return {"status": "recovered"}
