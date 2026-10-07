"""Durable course-host build queue. No source code runs in the SSH process."""

from contextlib import contextmanager
import fcntl
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import time

from .common import sha

TERMINAL = ("success", "failure", "cancelled")


def job_id(value):
    if not isinstance(value, str) or not re.fullmatch("[0-9a-f]{32}", value):
        raise ValueError("invalid build job ID")
    return value


class BuildQueue:
    def __init__(self, root, slots=2, clock=time.time):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.jobs = self.root / "jobs"
        self.jobs.mkdir(exist_ok=True)
        if not isinstance(slots, int) or isinstance(slots, bool) or not 1 <= slots <= 2:
            raise ValueError("build concurrency must be 1 or 2")
        self.slots, self.clock = slots, clock
        with self.db() as db:
            db.executescript("""CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, component TEXT NOT NULL, sha TEXT NOT NULL,
                branch TEXT NOT NULL, generation INTEGER NOT NULL,
                run_id INTEGER NOT NULL, attempt INTEGER NOT NULL,
                status TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL,
                error TEXT NOT NULL DEFAULT '', result TEXT);
                CREATE INDEX IF NOT EXISTS jobs_pending ON jobs(status,created);""")
            if "options" not in {r[1] for r in db.execute("PRAGMA table_info(jobs)")}:
                db.execute("ALTER TABLE jobs ADD COLUMN options TEXT")

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.root / "queue.sqlite3", timeout=30)
        db.row_factory = sqlite3.Row
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def submit(self, request):
        component = request["component"]
        if component not in ("frontend", "backend", "android"):
            raise ValueError("unsupported build component")
        commit = sha(request["sha"])
        options = None
        if component == "android":
            from .android_build import validate_config
            options = validate_config(request["config"], commit)
        branch = request["branch"]
        if (
            not isinstance(branch, str)
            or not 1 <= len(branch.encode()) <= 255
            or any(ord(c) < 32 for c in branch)
        ):
            raise ValueError("invalid display branch")
        run, attempt = request["run_id"], request.get("attempt", 1)
        if (
            any(
                not isinstance(v, int) or isinstance(v, bool) or v < 1
                for v in (run, attempt)
            )
            or attempt > 999
        ):
            raise ValueError("invalid build run identity")
        generation = run * 1000 + attempt
        ident = hashlib.sha256(
            f"{component}:{commit}:{run}:{attempt}".encode()
        ).hexdigest()[:32]
        now = self.clock()
        with self.db() as db:
            same = db.execute("SELECT * FROM jobs WHERE id=?", (ident,)).fetchone()
            if same:
                return self.describe(same)
            newer = db.execute(
                "SELECT 1 FROM jobs WHERE component=? AND branch=? AND generation>? AND sha<>?",
                (component, branch, generation, commit),
            ).fetchone()
            if newer:
                return {
                    "status": "cancelled",
                    "reason": "newer request already recorded",
                }
            # First-attempt push/PR notifications share one physical build.
            # Explicit reruns may rebuild a failed or already completed version.
            if attempt == 1 and component != "android":
                reused = db.execute(
                    "SELECT * FROM jobs WHERE component=? AND sha=? AND status IN ('queued','running','success') ORDER BY created LIMIT 1",
                    (component, commit),
                ).fetchone()
                if reused:
                    return self.describe(reused)
            db.execute(
                "UPDATE jobs SET status='cancelled',updated=?,error='superseded before execution' WHERE component=? AND branch=? AND status='queued' AND generation<? AND sha<>?",
                (now, component, branch, generation, commit),
            )
            db.execute(
                "INSERT INTO jobs(id,component,sha,branch,generation,run_id,attempt,status,created,updated) VALUES(?,?,?,?,?,?,?,'queued',?,?)",
                (ident, component, commit, branch, generation, run, attempt, now, now),
            )
            if options is not None:
                db.execute("UPDATE jobs SET options=? WHERE id=?", (json.dumps(options), ident))
            return self.describe(
                db.execute("SELECT * FROM jobs WHERE id=?", (ident,)).fetchone()
            )

    def claim(self):
        with self.db() as db:
            if (
                db.execute(
                    "SELECT COUNT(*) FROM jobs WHERE status='running'"
                ).fetchone()[0]
                >= self.slots
            ):
                return None
            row = db.execute(
                "SELECT * FROM jobs WHERE status='queued' ORDER BY created,id LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            db.execute(
                "UPDATE jobs SET status='running',updated=? WHERE id=?",
                (self.clock(), row["id"]),
            )
            return dict(row)

    def finish(self, ident, result=None, error=""):
        ident = job_id(ident)
        with self.db() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (ident,)).fetchone()
            if row is None or row["status"] != "running":
                raise ValueError("only an active build can finish")
            db.execute(
                "UPDATE jobs SET status=?,updated=?,error=?,result=? WHERE id=?",
                (
                    "failure" if error else "success",
                    self.clock(),
                    str(error)[:1000],
                    json.dumps(result) if result is not None else None,
                    ident,
                ),
            )

    def recover(self):
        # The worker's exclusive lock and bwrap --die-with-parent ensure old
        # sandbox processes cannot survive a worker restart.
        with self.db() as db:
            db.execute(
                "UPDATE jobs SET status='failure',updated=?,error='build worker restarted; rerun the request' WHERE status='running'",
                (self.clock(),),
            )

    @staticmethod
    def describe(row):
        result = {
            k: row[k]
            for k in (
                "id",
                "component",
                "sha",
                "branch",
                "run_id",
                "attempt",
                "status",
                "created",
                "updated",
                "error",
            )
        }
        if "options" in row.keys() and row["options"]:
            result["config"] = json.loads(row["options"])
        if row["result"]:
            result["result"] = json.loads(row["result"])
        return result

    def lookup(self, ident, offset=0):
        ident = job_id(ident)
        if (
            not isinstance(offset, int)
            or isinstance(offset, bool)
            or not 0 <= offset <= 4 * 1024**2
        ):
            raise ValueError("invalid build log offset")
        with self.db() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (ident,)).fetchone()
            if row is None:
                raise ValueError("unknown build job")
            result = self.describe(row)
        log = self.jobs / ident / "build.log"
        data = b""
        if log.is_file():
            with log.open("rb") as stream:
                stream.seek(offset)
                data = stream.read(32768)
        return {
            **result,
            "log": data.decode(errors="replace"),
            "log_offset": offset + len(data),
        }

    def completed(self, ident, component=None, commit=None):
        result = self.lookup(ident)
        if result["status"] != "success":
            raise ValueError("build has not passed its checks")
        if component and result["component"] != component:
            raise ValueError("build component mismatch")
        if commit and result["sha"] != sha(commit):
            raise ValueError("build SHA mismatch")
        return result

    def collect(self, release_root, grace=7 * 86400):
        """Keep runtime venvs while any immutable release still points at them."""
        protected = set()
        for metadata in Path(release_root).glob("be-*/release.json"):
            try:
                value = json.loads(metadata.read_text()).get("job")
                if value:
                    protected.add(job_id(value))
            except (ValueError, OSError):
                # Do not discard build history if a release record is damaged.
                return []
        with self.db() as db:
            expired = [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM jobs WHERE status IN ('success','failure','cancelled') AND updated<?",
                    (self.clock() - grace,),
                )
                if row["id"] not in protected
            ]
            for row in expired:
                db.execute("DELETE FROM jobs WHERE id=?", (row["id"],))
        import shutil

        for row in expired:
            directory = self.jobs / job_id(row["id"])
            if directory.exists():
                shutil.rmtree(directory)
        return [row["id"] for row in expired]

    def worker_lock(self):
        path = (self.root / "worker.lock").open("a")
        fcntl.flock(path, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return path
