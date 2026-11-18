"""Install a reviewed embedding release and opt named test branches into RAG."""

import argparse
import hashlib
import json
import math
import secrets
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from livelife.branch_database import branch_name, locked
from livelife.build_runner import extract_source
from livelife.common import atomic_json, sha
from livelife.embedding_runtime import environment
from livelife.mail_config import private_path
from livelife.retrieval_config import MODEL, REVISION, service_settings
from livelife.supervisor import Supervisor


def probe(settings):
    base = f"http://127.0.0.1:{settings['port']}"
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(base + "/health", timeout=10) as response:
        health = json.load(response)
    if (health.get("status") != "ready" or health.get("model") != settings["model"]
            or health.get("revision") != settings["revision"]):
        raise RuntimeError("embedding health identity mismatch")
    request = urllib.request.Request(
        base + "/v1/embeddings", data=json.dumps({
            "model": settings["model"], "input": ["校园资料检索"], "encoding_format": "float"
        }).encode(), headers={"Authorization": "Bearer " + settings["key"],
                             "Content-Type": "application/json"},
    )
    with opener.open(request, timeout=20) as response:
        result = json.load(response)
    if (result.get("model") != settings["model"] or result.get("revision") != settings["revision"]
            or len(result["data"]) != 1
            or len(result["data"][0]["embedding"]) != settings["dimensions"]):
        raise RuntimeError("embedding response dimension mismatch")
    vector = result["data"][0]["embedding"]
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in vector) or not any(vector):
        raise RuntimeError("embedding probe returned an invalid vector")


def install(root, source, commit, port, branches, threads=4):
    root, source = Path(root).resolve(), Path(source).resolve()
    sha(commit)
    for branch in branches:
        branch_name(branch)
    if type(port) is not int or not 19000 <= port < 20000 or not 1 <= threads <= 8:
        raise ValueError("embedding port must be 19000..19999 and threads 1..8")
    resolved = subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", commit + "^{commit}"], text=True, timeout=10
    ).strip()
    if resolved != commit:
        raise ValueError("source must be a full reviewed commit SHA")
    settings = {"source_sha": commit, "model": MODEL, "revision": REVISION,
                "dimensions": 1024, "port": port, "threads": threads}
    digest = hashlib.sha256(json.dumps(settings, sort_keys=True).encode()).hexdigest()[:16]
    service = "embedding-" + digest
    base = root / "embedding"
    base.mkdir(parents=True, exist_ok=True, mode=0o700)
    private_path(base, directory=True)
    with locked(base):
        directory = base / service
        directory.mkdir(mode=0o700, exist_ok=True)
        private_path(directory, directory=True)
        record = directory / "service.json"
        if record.exists() or record.is_symlink():
            stored = service_settings(root, service)
            if {k: v for k, v in stored.items() if k != "key"} != settings:
                raise ValueError("immutable embedding installation mismatch")
            settings = stored
        else:
            settings["key"] = secrets.token_hex(32)
            atomic_json(record, settings)
            record.chmod(0o600)
        supervisor = Supervisor(root / "supervisor", root / "control-venv/bin/python")
        if not (directory / "installed.json").exists():
            with socket.socket() as check_port:
                check_port.bind(("127.0.0.1", port))
            source_tar = subprocess.check_output(
                ["git", "-C", str(source), "archive", commit, "backend"], timeout=30
            )
            extract_source(source_tar, directory)
            backend = directory / "backend"
            if not (backend / "app/embedding_server.py").is_file():
                raise ValueError("reviewed source has no embedding service")
            env = environment(root, service, settings)
            env.pop("HF_HUB_OFFLINE")
            env["UV_PROJECT_ENVIRONMENT"] = str(backend / ".venv")
            # Dedicated venv/cache, no deployment/chat/SMTP secrets in installation.
            with (directory / "install.log").open("w") as log:
                subprocess.run(
                    ["uv", "sync", "--locked", "--no-dev", "--group", "embedding-server",
                     "--python", "3.12"], cwd=backend, env=env, check=True,
                    stdout=log, stderr=subprocess.STDOUT, timeout=1800,
                )
                subprocess.run(
                    [str(backend / ".venv/bin/python"), "-c",
                     "import os; from sentence_transformers import SentenceTransformer; "
                     "SentenceTransformer(os.environ['EMBEDDING_MODEL'], "
                     "revision=os.environ['EMBEDDING_MODEL_REVISION'], "
                     "device='cpu', trust_remote_code=False)"],
                    cwd=backend, env=env, check=True, stdout=log, stderr=subprocess.STDOUT,
                    timeout=1800,
                )
            atomic_json(directory / "installed.json", {"source_sha": commit})
        supervisor.configure(
            service, f"{root}/control-venv/bin/python -m livelife.embedding_runtime "
            f"--root {root} --service {service}", root / "control", stopwaitsecs=30,
        )
        end = time.monotonic() + 180
        while True:
            try:
                probe(settings)
                break
            except (OSError, ValueError, KeyError, RuntimeError):
                if time.monotonic() >= end:
                    raise RuntimeError("embedding startup failed; inspect the service log") from None
                time.sleep(2)
        credentials = root / "credentials"
        credentials.mkdir(mode=0o700, exist_ok=True)
        private_path(credentials, directory=True)
        config = credentials / "retrieval.json"
        if config.exists() or config.is_symlink():
            private_path(config)
        # Only publish the opt-in after the actual model has passed a request.
        atomic_json(config, {"branches": list(dict.fromkeys(branches)), "service": service})
        config.chmod(0o600)
        return {"service": service, "port": port, "branches": branches, "source_sha": commit}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True, help="local reviewed Git checkout")
    parser.add_argument("--sha", required=True, help="full reviewed source SHA")
    parser.add_argument("--port", type=int, default=19073)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--branch", action="append", default=[])
    args = parser.parse_args()
    try:
        print(json.dumps(install(args.root, args.source, args.sha, args.port,
                                 args.branch, args.threads)))
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
        print("Embedding installation failed; inspect the private installation/service logs.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
