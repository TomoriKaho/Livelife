"""Unprivileged CI: test the hello contract, package only Git-tracked backend."""
import json
import os
from pathlib import Path
import io
import socket
import subprocess
import sys
import tempfile
import tarfile

from livelife.course import check_health
from livelife.common import sha


def dependency_format(root):
    root = Path(root)
    if (root / "pyproject.toml").is_file() and (root / "uv.lock").is_file():
        return "uv"
    if (root / "requirements.txt").is_file():
        return "requirements"
    return None


def package(commit, destination, requirements, wheels):
    source = subprocess.check_output(["git", "archive", "--format=tar", commit, "backend"])
    with tarfile.open(destination, "w:gz") as bundle:
        with tarfile.open(fileobj=io.BytesIO(source), mode="r:") as tracked:
            for member in tracked:
                if member.name.startswith("backend/.wheels") or member.name == "backend/.deploy-requirements.txt":
                    raise ValueError("backend source uses a reserved artifact path")
                bundle.addfile(member, tracked.extractfile(member) if member.isfile() else None)
        bundle.add(requirements, arcname="backend/.deploy-requirements.txt")
        for wheel in sorted(Path(wheels).glob("*.whl")):
            bundle.add(wheel, arcname="backend/.wheels/" + wheel.name)
    if Path(destination).stat().st_size > 20 * 1024 * 1024:
        raise ValueError("backend artifact exceeds 20 MiB; review dependency size before deploying")


def main():
    commit = sha(subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip())
    out = Path(os.environ.get("LIVELIFE_ARTIFACT_DIR", "deploy/.state/backend-artifact"))
    out.mkdir(parents=True, exist_ok=True)
    (out / "backend.tgz").unlink(missing_ok=True)
    mode = dependency_format("backend")
    exists = Path("backend/app/main.py").is_file() and mode is not None
    (out / "manifest.json").write_text(json.dumps({"sha": commit, "available": exists}))
    if not exists:
        print("#24 backend entry/locked dependencies missing: infrastructure checked; no backend deploy artifact.")
        return
    requirements = out.resolve() / "runtime-requirements.txt"
    if mode == "uv":
        subprocess.run(["uv", "sync", "--locked", "--python", sys.executable], cwd="backend", check=True)
        subprocess.run(["uv", "export", "--locked", "--no-dev", "--no-emit-project",
                        "--format", "requirements.txt", "--output-file", str(requirements)],
                       cwd="backend", check=True, stdout=subprocess.DEVNULL)
        # Preserve the venv symlink: resolving it would execute base Python.
        python = str(Path("backend/.venv/bin/python").absolute())
        if Path("backend/tests").is_dir():
            subprocess.run(["uv", "run", "--no-sync", "pytest"], cwd="backend", check=True)
        subprocess.run(["uv", "run", "--no-sync", "ruff", "check", "."], cwd="backend", check=True)
        subprocess.run(["uv", "run", "--no-sync", "ruff", "format", "--check", "."], cwd="backend", check=True)
    else:
        requirements.write_bytes(Path("backend/requirements.txt").read_bytes())
        subprocess.run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
                        "-r", str(requirements)], check=True)
        python = sys.executable
        if Path("backend/tests").is_dir():
            subprocess.run([python, "-m", "unittest", "discover", "-s", "backend/tests"], check=True)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    with tempfile.TemporaryFile() as log:
        process = subprocess.Popen([python, "-m", "uvicorn", "app.main:app",
                                    "--host", "127.0.0.1", "--port", str(port)],
                                   cwd="backend", stdout=log, stderr=log)
        try:
            check_health(port)
        except Exception:
            log.seek(0)
            print(log.read().decode(errors="replace")[-4000:])
            raise
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    with tempfile.TemporaryDirectory() as wheel_root:
        subprocess.run([sys.executable, "-m", "pip", "download", "--only-binary=:all:",
                        "--disable-pip-version-check", "-r", str(requirements), "-d", wheel_root], check=True)
        package(commit, out / "backend.tgz", requirements, wheel_root)
    requirements.unlink()  # Upload only manifest.json and backend.tgz.


if __name__ == "__main__":
    main()
