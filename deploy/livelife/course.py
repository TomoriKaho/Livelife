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

from .common import atomic_json, instance, sha, read_request
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
        if op == 'android_tools':
            # Administrative transfer of verified project tools, never source artifacts.
            import io
            out = io.BytesIO()
            with tarfile.open(fileobj=out, mode='w:gz', dereference=True) as archive:
                for name in ('jdk', 'android-sdk/build-tools/36.0.0'):
                    directory = self.root / 'build-tools' / name
                    if not directory.is_dir():
                        raise ValueError('Android signing tools are not installed')
                    archive.add(directory, arcname=name, filter=lambda item: None
                        if item.name.startswith('jdk/jmods/') or item.name == 'jdk/jmods' or item.name.endswith('/src.zip')
                        else item)
            data = out.getvalue()
            if len(data) > 256*1024**2:
                raise ValueError('Android tool transfer exceeds limit')
            return {'bundle':base64.b64encode(data).decode(), 'digest':hashlib.sha256(data).hexdigest()}
        if op.startswith('build_'):
            from .build_queue import BuildQueue, job_id
            queue = BuildQueue(self.root / 'builds')
            if op == 'build_submit':
                worker = f'{self.root}/control-venv/bin/python -m livelife.build_runner {self.root}'
                self.supervisor.configure('build-worker', worker, self.root / 'control')
                return queue.submit(request)
            if op == 'build_status':
                return queue.lookup(request['job'], request.get('offset', 0))
            if op == 'build_artifact':
                component = request.get('component', 'frontend')
                if component not in ('frontend', 'android'):
                    raise ValueError('unsupported artifact component')
                result = queue.completed(request['job'], component, request['sha'])
                manifest = result['result']
                payload = (queue.jobs / job_id(request['job']) / ('artifact/android-unsigned.apk' if component == 'android' else 'artifact/frontend.tgz')).read_bytes()
                if len(payload) > 64 * 1024**2 or hashlib.sha256(payload).hexdigest() != manifest['digest']:
                    raise ValueError('stored frontend artifact mismatch')
                return {'manifest': manifest, 'bundle': base64.b64encode(payload).decode()}
            raise ValueError('unsupported build operation')
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
            if request.get('job'):
                self.install_built(request['job'], commit, port, directory)
            elif request.get("bundle") is None:
                raise ValueError("release source missing; redeploy the recorded SHA")
            if metadata.exists():
                return self.handle({**request, 'job': None, 'bundle': None})
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
        elif any(json.loads(metadata.read_text()).get(k) != v for k, v in {'sha': commit, 'port': port}.items()):
            raise ValueError("immutable release metadata mismatch")
        self.supervisor.configure(ident,
            f"{directory}/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port {port} "
            f"--root-path /api/versions/{ident}", directory / "backend",
            f'LIVELIFE_BACKEND_SHA="{commit}"')
        check_health(port)
        return {"status": "ready", "sha": commit, "port": port}

    def install_built(self, job, commit, port, directory):
        from .build_queue import BuildQueue, job_id
        from .build_runner import extract_source
        queue = BuildQueue(self.root / 'builds')
        result = queue.completed(job, 'backend', commit)
        if not result['result']['available']:
            raise ValueError('backend entry not initialized')
        workspace = queue.jobs / job_id(job) / 'repo'
        venv = workspace / 'backend/.venv'
        if venv.is_symlink() or not (venv / 'pyvenv.cfg').is_file() or not (venv / 'bin/python').is_file():
            raise ValueError('tested virtual environment is missing')
        if (venv / 'bin/python').resolve() != Path(sys.executable).resolve():
            raise ValueError('unexpected virtual environment interpreter')
        source = subprocess.check_output(['git', '--git-dir', str(self.root / 'builds/source.git'), 'archive', commit, 'backend'], timeout=30)
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir()
        extract_source(source, directory)
        (directory / '.venv').symlink_to(venv, target_is_directory=True)
        atomic_json(directory / 'release.json', {'sha': commit, 'port': port, 'job': job})

    @staticmethod
    def port(value):
        if not isinstance(value, int) or not 18000 <= value < 18064:
            raise ValueError("course port is outside 18000..18063")
        return value


def main():
    try:
        request = read_request(sys.stdin.buffer, MAX_BUNDLE * 2)
        # This module is installed under ~/livelife/control/livelife/.
        root = Path(__file__).resolve().parents[2]
        print(json.dumps(Course(root).handle(request)))
    except Exception as exc:
        print(json.dumps({"error": str(exc)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
