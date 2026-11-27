"""RAG publication gate and a worker whose lifetime follows its preview API."""

from contextlib import contextmanager
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

from .branch_database import locked
from .common import atomic_json


def command(python, backend, env, operation, *, timeout=30):
    try:
        result = subprocess.run(
            [str(python), "-m", "app.retrieval", operation], cwd=backend, env=env,
            check=True, timeout=timeout, capture_output=True, text=True,
        )
    except subprocess.SubprocessError:
        print(json.dumps({"retrieval_operation_failed": operation}), flush=True)
        raise
    # Report counts only. Never propagate a branch traceback or environment to RPC.
    return json.loads(result.stdout.splitlines()[-1])


def prepare(python, backend, env, state, *, sync_timeout=420):
    # Serializes bootstrap with other releases of the same branch. Once installed,
    # a profile cannot change under older APIs/workers still sharing the database.
    with locked(state / "retrieval"):
        profile = command(python, backend, env, "status")["profile"]
        marker = state / "retrieval/profile.json"
        if marker.is_symlink():
            raise ValueError("retrieval profile marker must not be a link")
        if marker.exists() and json.loads(marker.read_text()) != {"profile": profile}:
            raise RuntimeError("retrieval profile changed; stop all branch runtimes before migration")
        atomic_json(marker, {"profile": profile})
        command(python, backend, env, "reconcile")
        command(python, backend, env, "sync", timeout=sync_timeout)
        result = command(python, backend, env, "check", timeout=30)
        if result.get("ready") is not True:
            raise RuntimeError("retrieval readiness failed")
        print(json.dumps({"retrieval_ready": result}), flush=True)
        return result


def stop(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


@contextmanager
def worker(python, backend, env, state):
    process = subprocess.Popen(
        [str(python), "-m", "app.retrieval", "watch", "--lock-file",
         str(state / "retrieval/worker.lock")], cwd=backend, env=env,
    )
    try:
        yield process
    finally:
        stop(process)


def wait(api, indexer):
    while api.poll() is None:
        if indexer.poll() is not None:
            raise RuntimeError("retrieval worker exited; restarting preview runtime")
        time.sleep(0.5)
    return api.returncode


def main():
    parser = argparse.ArgumentParser(description="Inspect or prewarm an existing preview RAG database")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--instance", required=True)
    parser.add_argument("--operation", choices=("status", "check", "sync"), default="status")
    args = parser.parse_args()
    from pgembed import get_server
    from .common import instance
    from .branch_database import directory, validate_specification
    from .retrieval_config import load
    from .backend_runtime import runtime_environment

    try:
        release = args.root / "releases" / instance(args.instance)
        spec = json.loads((release / "release.json").read_text())["database"]
        validate_specification(spec)
        state = directory(args.root, spec["id"])
        if not (state / "initialized.json").is_file() or not (state / "postgres/PG_VERSION").is_file():
            raise RuntimeError("existing initialized branch database required")
        retrieval = load(args.root, spec["branch"])
        if not retrieval:
            raise RuntimeError("branch is not opted into RAG")
        with get_server(state / "postgres", cleanup_mode="stop") as server:
            url = server.get_uri(database="postgres").replace("postgresql://", "postgresql+psycopg://", 1)
            env = {**runtime_environment(url, args.instance, state), **retrieval}
            env.pop("AGENT_SESSION_SECRET", None)
            if args.operation == "sync":
                prepare(release / ".venv/bin/python", release / "backend", env, state,
                        sync_timeout=1800)
            else:
                print(json.dumps(command(release / ".venv/bin/python", release / "backend", env,
                                         args.operation)))
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError):
        print("RAG operation failed; verify the instance, configuration, model and index.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
