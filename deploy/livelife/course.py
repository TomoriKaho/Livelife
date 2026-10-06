"""Restricted stdin JSON entry point on the course machine (no Docker/root)."""
import base64
import hashlib
import gzip
import io
import json
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tarfile
import time
import urllib.request

from .common import atomic_json, instance, sha
from .supervisor import Supervisor

MAX_BUNDLE = 20 * 1024 * 1024


def unpack(encoded, destination, digest):
    data = base64.b64decode(encoded, validate=True)
    if len(data) > MAX_BUNDLE or hashlib.sha256(data).hexdigest() != digest:
        raise ValueError("invalid bundle size or digest")
    destination = Path(destination).resolve()
    # Bound expansion BEFORE parsing headers; PAX metadata is also untrusted.
    with gzip.GzipFile(fileobj=io.BytesIO(data)) as compressed:
        expanded = compressed.read(110 * 1024 * 1024 + 1)
    if len(expanded) > 110 * 1024 * 1024:
        raise ValueError("bundle expanded size exceeds limit")
    with tarfile.open(fileobj=io.BytesIO(expanded), mode="r|") as archive:
        count = total = 0
        for item in archive:
            count += 1
            total += item.size
            if count > 10000 or total > 100 * 1024 * 1024:
                raise ValueError("bundle expanded size exceeds limit")
            path = Path(item.name)
            if (not item.isfile() and not item.isdir()) or path.is_absolute() or ".." in path.parts:
                raise ValueError("links, special files and path traversal are forbidden")
            if not path.parts or path.parts[0] != "backend" or path.parts[1:2] in [(".venv",), ("venv",)]:
                raise ValueError("bundle must contain backend source only")
            if not (destination / path).resolve().is_relative_to(destination):
                raise ValueError("bundle path escapes release")
            archive.extract(item, destination, filter="data")


def check_health(port, timeout=45):
    end = time.monotonic() + timeout
    error = None
    while time.monotonic() < end:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/test/hello", timeout=2) as response:
                if response.status == 200 and json.load(response) == {"message": "hello world"}:
                    return
                error = "unexpected hello response"
        except Exception as exc:
            error = str(exc)
        time.sleep(0.5)
    raise RuntimeError(f"hello health check failed on {port}: {error}")


class Course:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.releases = self.root / "releases"
        self.releases.mkdir(parents=True, exist_ok=True)
        self.supervisor = Supervisor(self.root / "supervisor", self.root / "control-venv/bin/python")

    def handle(self, request):
        op = request["op"]
        if op == "port_available":
            port = self.port(request["port"])
            with socket.socket() as sock:
                try:
                    sock.bind(("127.0.0.1", port))
                    return {"available": True}
                except OSError:
                    return {"available": False}
        ident = instance(request["instance"])
        directory = self.releases / ident
        if op == "remove":
            self.supervisor.remove(ident)
            if directory.exists():
                shutil.rmtree(directory)
            return {"status": "removed"}
        if op != "ensure":
            raise ValueError("unsupported course operation")
        commit = sha(request["sha"])
        if ident != f"be-{commit}":
            raise ValueError("instance/SHA mismatch")
        port = self.port(request["port"])
        metadata = directory / "release.json"
        if not metadata.exists():
            if request.get("bundle") is None:
                raise ValueError("release source missing; redeploy the recorded SHA")
            # Clean incomplete installs before retry; completed versions are immutable.
            if directory.exists():
                shutil.rmtree(directory)
            directory.mkdir()
            unpack(request["bundle"], directory, request["digest"])
            requirements = directory / "backend/.deploy-requirements.txt"
            if not requirements.is_file():
                requirements = directory / "backend/requirements.txt"
            if not (directory / "backend/app/main.py").is_file() or not requirements.is_file():
                raise ValueError("requires backend/app/main.py and exported runtime requirements from CI")
            wheels = directory / "backend/.wheels"
            if not wheels.is_dir() or not list(wheels.glob("*.whl")):
                raise ValueError("artifact missing CI wheelhouse; run Backend checks first")
            venv = directory / ".venv"
            subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True, capture_output=True, timeout=60)
            try:
                with (directory / "install.log").open("w") as log:
                    subprocess.run([str(venv / "bin/python"), "-m", "pip", "install", "--disable-pip-version-check",
                                    "--no-index", "--find-links", str(wheels), "--no-cache-dir",
                                    "-r", str(requirements)],
                                   check=True, stdout=log, stderr=subprocess.STDOUT, timeout=180)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
                tail = (directory / "install.log").read_text(errors="replace")[-2000:]
                raise RuntimeError(f"offline dependency install failed: {tail}") from error
            atomic_json(metadata, {"sha": commit, "port": port})
        elif json.loads(metadata.read_text()) != {"sha": commit, "port": port}:
            raise ValueError("immutable release metadata mismatch")
        self.supervisor.configure(ident,
            f"{directory}/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port {port} "
            f"--root-path /api/versions/{ident}", directory / "backend",
            f'LIVELIFE_BACKEND_SHA="{commit}"')
        check_health(port)
        return {"status": "ready", "sha": commit, "port": port}

    @staticmethod
    def port(value):
        if not isinstance(value, int) or not 18000 <= value < 18064:
            raise ValueError("course port is outside 18000..18063")
        return value


def main():
    try:
        raw = sys.stdin.buffer.read(MAX_BUNDLE * 2 + 1)
        if len(raw) > MAX_BUNDLE * 2:
            raise ValueError("request exceeds limit")
        request = json.loads(raw)
        # This module is installed under ~/livelife/control/livelife/.
        root = Path(__file__).resolve().parents[2]
        print(json.dumps(Course(root).handle(request)))
    except Exception as exc:
        print(json.dumps({"error": str(exc)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
