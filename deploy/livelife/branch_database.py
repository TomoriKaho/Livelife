"""Persistent branch databases; full adoption or sanitized fork, then forward migrations."""
from contextlib import contextmanager
import fcntl
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone

from .common import atomic_json, instance, owner, sha

# Fail closed for new tables: their schema is copied, their rows are not.
PUBLIC_TABLES = frozenset({
    "alembic_version", "information_items", "information_places",
    "information_place_aliases",
})


def branch_name(value):
    if (not isinstance(value, str) or not 1 <= len(value) <= 255
            or any(ord(c) < 32 or ord(c) == 127 for c in value)):
        raise ValueError("invalid database branch name")
    return value


def branch_id(branch):
    return "branch-" + hashlib.sha256(branch_name(branch).encode()).hexdigest()[:32]


def release_id(commit, branch):
    return "be-" + sha(commit) + "-" + branch_id(branch)[7:]


def validate_request(value):
    if not isinstance(value, dict) or set(value) - {"branch", "source_branch", "source_owner"}:
        raise ValueError("invalid database request")
    branch = branch_name(value["branch"])
    if branch != "main" and branch_name(value["source_branch"]) == branch:
        raise ValueError("branch cannot initialize from itself")
    if "source_owner" in value:
        owner(value["source_owner"])


def validate_specification(value):
    if not isinstance(value, dict) or set(value) - {"copy_mode"} != {"id", "branch", "source", "source_branch"}:
        raise ValueError("invalid database specification")
    if value["id"] != branch_id(value["branch"]):
        raise ValueError("database branch identity mismatch")
    if value["source_branch"] is not None:
        branch_name(value["source_branch"])
    mode = value.get("copy_mode", "public")
    if mode not in ("public", "full"):
        raise ValueError("invalid database copy mode")
    source = value["source"]
    if mode == "full" and (source is None or value["source_branch"] != value["branch"]):
        raise ValueError("full copy requires an existing database of the same branch")
    if source is None:
        if value["branch"] != "main":
            raise ValueError("only initial main can start empty")
    else:
        state_id(source)
        if source == value["id"]:
            raise ValueError("database cannot initialize from itself")


def state_id(value):
    if isinstance(value, str) and re.fullmatch(r"branch-[0-9a-f]{32}", value):
        return value
    return instance(value)


def directory(root, ident):
    base = Path(root).resolve() / "databases"
    path = base / state_id(ident)
    if base.is_symlink() or path.is_symlink() or (path / "postgres").is_symlink():
        raise ValueError("database paths must not be symlinks")
    base.mkdir(mode=0o700, exist_ok=True)
    base.chmod(0o700)
    return path


@contextmanager
def locked(path):
    path.mkdir(mode=0o700, exist_ok=True)
    path.chmod(0o700)
    lock = path / "migration.lock"
    if lock.is_symlink():
        raise ValueError("database lock must not be a symlink")
    with lock.open("a") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield


def snapshot(source, archive, *, full=False):
    # Use the very same PostgreSQL distribution as pgembed (no system PATH tool).
    from pgembed.postgres_server import POSTGRES_BIN_PATH
    uri = source.get_uri(database="postgres")
    exclusions = []
    if not full:
        tables = subprocess.check_output([
            str(POSTGRES_BIN_PATH / "psql"), uri, "-XAt", "-v", "ON_ERROR_STOP=1", "-c",
            "SELECT json_agg(json_build_array(schemaname, tablename)) FROM pg_tables "
            "WHERE schemaname NOT IN ('pg_catalog','information_schema')",
        ], timeout=30)
        for schema, table in json.loads(tables) or []:
            if schema != "public" or table not in PUBLIC_TABLES:
                # pg_dump patterns are identifiers, not SQL or shell fragments.
                quoted = '.'.join('"' + x.replace('"', '""') + '"' for x in (schema, table))
                exclusions.append("--exclude-table-data=" + quoted)
    subprocess.run([
        str(POSTGRES_BIN_PATH / "pg_dump"), "--dbname", uri, "--format=custom",
        "--no-owner", "--no-acl", *([] if full else ["--no-blobs"]), *exclusions, "--file", str(archive),
    ], check=True, timeout=120)
    archive.chmod(0o600)


def copy_runtime_settings(source_state, staging):
    # Existing signed Agent sessions must retain their key during same-branch
    # adoption. Never regenerate it silently or copy it into a new branch.
    path = source_state / "runtime.json"
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 16384:
        raise ValueError("same-branch adoption requires valid original runtime settings")
    settings = json.loads(path.read_text())
    secret = settings.get("agent_session_secret")
    if not isinstance(secret, str) or len(secret) < 32:
        raise ValueError("invalid original Agent session secret")
    atomic_json(staging / "runtime.json", {"agent_session_secret": secret})
    (staging / "runtime.json").chmod(0o600)


def restore(server, archive):
    from pgembed.postgres_server import POSTGRES_BIN_PATH
    subprocess.run([
        str(POSTGRES_BIN_PATH / "pg_restore"), "--dbname", server.get_uri(database="postgres"),
        "--exit-on-error", "--single-transaction", "--no-owner", "--no-acl", str(archive),
    ], check=True, timeout=120)


def source_directory(root, ident):
    # Legacy references can point at a release that already has a branch DB.
    if ident.startswith("be-"):
        metadata = Path(root) / "releases" / instance(ident) / "release.json"
        if metadata.is_file():
            specification = json.loads(metadata.read_text()).get("database")
            if specification:
                validate_specification(specification)
                ident = specification["id"]
    path = directory(root, ident)
    if not (path / "postgres/PG_VERSION").is_file():
        raise ValueError("source database is missing; refusing empty fallback")
    if ident.startswith("branch-") and not (path / "initialized.json").is_file():
        raise ValueError("source database has not completed initialization")
    return path


@contextmanager
def prepared_database(root, specification, server_factory, migrate):
    validate_specification(specification)
    state = directory(root, specification["id"])
    marker = state / "initialized.json"
    # Serialize initialization and migrations; release the lock before serving.
    # pgembed maintains interprocess handle references, so retiring an old API
    # does not stop PostgreSQL while another API holds this branch's handle.
    with locked(state):
        if marker.is_symlink():
            raise ValueError("database marker must not be a symlink")
        initialized_now = not marker.exists()
        if initialized_now:
            if (state / "postgres").exists():
                raise ValueError("unmarked database requires maintenance; refusing overwrite")
            staging = state / "initializing"
            if staging.is_symlink():
                raise ValueError("initialization directory must not be a symlink")
            staging.mkdir(mode=0o700, exist_ok=True)
            # A killed initialization may have left a running PostgreSQL. Acquire
            # and stop it before deleting only this unpublished temporary cluster.
            if (staging / "postgres").is_symlink():
                raise ValueError("temporary database must not be a symlink")
            if (staging / "postgres").exists():
                with server_factory(staging / "postgres", cleanup_mode="delete"):
                    pass
            settings = staging / "runtime.json"
            if settings.is_symlink():
                raise ValueError("temporary runtime settings must not be a symlink")
            settings.unlink(missing_ok=True)
            archive = staging / "snapshot.dump"
            if archive.is_symlink():
                raise ValueError("snapshot must not be a symlink")
            try:
                snapshot_at = datetime.now(timezone.utc).isoformat()
                source = specification["source"]
                if source is not None:
                    source_state = source_directory(root, source)
                    if source_state == state:
                        raise ValueError("source resolves to target database")
                    with locked(source_state), server_factory(source_state / "postgres", cleanup_mode="stop") as server:
                        full = specification.get("copy_mode", "public") == "full"
                        if full:
                            copy_runtime_settings(source_state, staging)
                        snapshot(server, archive, full=full)
                with server_factory(staging / "postgres", cleanup_mode="stop") as server:
                    if source is not None:
                        restore(server, archive)
                    migrate(server, staging)
                # Cluster is stopped before moving. No live filesystem copying.
                (staging / "postgres").rename(state / "postgres")
                if (staging / "runtime.json").exists():
                    (staging / "runtime.json").rename(state / "runtime.json")
                atomic_json(marker, {**specification, "snapshot_at": snapshot_at})
            finally:
                archive.unlink(missing_ok=True)
            shutil.rmtree(staging)
        elif json.loads(marker.read_text())["id"] != specification["id"]:
            raise ValueError("database marker identity mismatch")
        if not (state / "postgres/PG_VERSION").is_file():
            raise ValueError("initialized database is missing; refusing empty fallback")
        # Keep the handle alive after unlocking for the entire API lifetime.
        server = server_factory(state / "postgres", cleanup_mode="stop")
        server.__enter__()
        try:
            if not initialized_now:
                migrate(server, state)
        except BaseException:
            server.__exit__(*sys.exc_info())
            raise
    try:
        yield server, state
    finally:
        server.__exit__(None, None, None)
