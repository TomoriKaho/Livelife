"""Trusted runner: cached source, isolated checks, bounded logs and packaging."""

import concurrent.futures
import fcntl
import io
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import tarfile
import time

from .build_queue import BuildQueue

REPOSITORY = "https://github.com/TomoriKaho/Livelife.git"
NPM = "https://registry.npmmirror.com"
PYPI = "https://mirrors.aliyun.com/pypi/simple"
PYPI_FALLBACK = "https://pypi.tuna.tsinghua.edu.cn/simple"


def extract_source(data, destination):
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as archive:
        total = 0
        for index, item in enumerate(archive):
            total += item.size
            path = Path(item.name)
            if (
                index >= 10000
                or total > 256 * 1024**2
                or path.is_absolute()
                or ".." in path.parts
                or not (item.isfile() or item.isdir())
            ):
                raise ValueError("unsafe or oversized source archive")
            archive.extract(item, destination, filter="data")


def rewrite_mirrors(workspace, index=PYPI):
    """Only transient checkouts change URLs; lock versions/hashes are preserved."""
    lock = workspace / "backend/uv.lock"
    if lock.exists():
        content = lock.read_text().replace("https://pypi.org/simple", index)
        for mirror in (PYPI, PYPI_FALLBACK):
            content = content.replace(mirror, index).replace(
                mirror.removesuffix("simple") + "packages/",
                index.removesuffix("simple") + "packages/",
            )
        content = content.replace(
            "https://files.pythonhosted.org/", index.removesuffix("simple")
        )
        lock.write_text(content)
    lock = workspace / "frontend/package-lock.json"
    if lock.exists():
        lock.write_text(
            lock.read_text().replace("https://registry.npmjs.org/", NPM + "/")
        )


def sandbox_command(root, workspace, command):
    root = Path(root).resolve()
    workspace = Path(workspace).resolve()
    tools = root / "build-tools"
    cache = root / "builds/cache"
    source = root / "builds/source.git"
    args = [
        str(tools / "ubuntu/usr/bin/bwrap"),
        "--unshare-all",
        "--share-net",
        "--die-with-parent",
        "--new-session",
        "--tmpfs",
        "/proc",
        "--dev",
        "/dev",
        "--tmpfs",
        "/tmp",
        "--tmpfs",
        "/var",
        "--dir",
        "/var/lib/nginx",
        "--dir",
        "/var/log/nginx",
        "--dir",
        "/tmp/home",
    ]
    for path in (
        "/usr",
        "/bin",
        "/lib",
        "/lib64",
        "/etc/ssl",
        "/etc/resolv.conf",
        "/etc/hosts",
        "/etc/nsswitch.conf",
        "/etc/ld.so.cache",
    ):
        if Path(path).exists():
            args += ["--ro-bind", path, path]
    args += [
        "--ro-bind", str(tools / "sandbox/passwd"), "/etc/passwd",
        "--ro-bind", str(tools / "sandbox/group"), "/etc/group",
        "--ro-bind",
        str(tools),
        str(tools),
        "--ro-bind",
        str(source),
        str(source),
        "--ro-bind",
        str(root / "control"),
        "/runner",
        "--ro-bind",
        str(tools / "ubuntu/etc/nginx"),
        "/etc/nginx",
        "--bind",
        str(workspace),
        str(workspace),
        "--bind",
        str(cache),
        str(cache),
        "--chdir",
        str(workspace),
    ]
    # The course home, control databases, SSH files and deployment processes
    # are absent from this mount/PID namespace. No credentials enter its env.
    args += ["--", *command]
    return args


def anchor_cached_commits(source):
    """Advertise cached shallow commits so Git can negotiate incremental packs."""
    shallow = Path(source) / "shallow"
    if not shallow.exists():
        return
    for commit in shallow.read_text().splitlines():
        if len(commit) != 40 or any(c not in "0123456789abcdef" for c in commit):
            raise ValueError("invalid cached shallow commit")
        probe = subprocess.run(
            ["git", "--git-dir", str(source), "cat-file", "-e", commit + "^{commit}"],
            capture_output=True,
            timeout=10,
        )
        if probe.returncode == 0:
            subprocess.run(
                [
                    "git",
                    "--git-dir",
                    str(source),
                    "update-ref",
                    "refs/livelife/source/" + commit,
                    commit,
                ],
                check=True,
                capture_output=True,
                timeout=10,
            )


def run_fetch(command, source, timeout=180):
    """Terminate the whole Git process group before releasing the source lock."""
    shallow_lock = Path(source) / "shallow.lock"
    existing_lock = shallow_lock.exists()
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )
    try:
        _, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            _, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            _, stderr = process.communicate()
        # A helper may have closed its pipes while still running.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        if not existing_lock:
            shallow_lock.unlink(missing_ok=True)
        raise RuntimeError(
            f"Git fetch timed out after {timeout}s: {stderr.decode(errors='replace')[-2000:]}"
        )
    if process.returncode:
        raise RuntimeError(
            f"Git fetch failed ({process.returncode}): {stderr.decode(errors='replace')[-2000:]}"
        )


class Runner:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.queue = BuildQueue(self.root / "builds")
        self.tools = self.root / "build-tools"
        self.python = str(self.tools / "venv/bin/python")
        identity = self.tools / 'sandbox'
        identity.mkdir(parents=True, exist_ok=True)
        (identity / 'passwd').write_text(f'sandbox:x:{os.getuid()}:{os.getgid()}::/tmp/home:/bin/sh\n')
        (identity / 'group').write_text(f'sandbox:x:{os.getgid()}:\n')

    def checkout(self, job, workspace):
        source = self.root / "builds/source.git"
        with (self.root / "builds/source.lock").open("a") as lock:
            deadline = time.monotonic() + 600
            while True:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError('source lock wait exceeded 10 minutes')
                    time.sleep(0.2)
            if not source.exists():
                subprocess.run(
                    ["git", "init", "--bare", str(source)],
                    check=True,
                    capture_output=True,
                    timeout=30,
                )
                subprocess.run(
                    [
                        "git",
                        "--git-dir",
                        str(source),
                        "config",
                        "remote.origin.url",
                        REPOSITORY,
                    ],
                    check=True,
                )
            anchor_cached_commits(source)
            try:
                subprocess.run(
                    [
                        "git",
                        "--git-dir",
                        str(source),
                        "cat-file",
                        "-e",
                        job["sha"] + "^{commit}",
                    ],
                    check=True,
                    capture_output=True,
                )
            except subprocess.CalledProcessError:
                for attempt in range(3):
                    try:
                        run_fetch(
                            [
                                "git",
                                "--git-dir",
                                str(source),
                                "-c",
                                "core.hooksPath=/dev/null",
                                "-c",
                                "http.lowSpeedLimit=1024",
                                "-c",
                                "http.lowSpeedTime=30",
                                "fetch",
                                "--depth=1",
                                "origin",
                                job["sha"] + ":refs/livelife/source/" + job["sha"],
                            ],
                            source,
                        )
                        break
                    except RuntimeError:
                        if attempt == 2:
                            raise
                        time.sleep(2 * (attempt + 1))
            subprocess.run(
                [
                    "git",
                    "--git-dir",
                    str(source),
                    "-c",
                    "core.hooksPath=/dev/null",
                    "worktree",
                    "add",
                    "--detach",
                    str(workspace),
                    job["sha"],
                ],
                check=True,
                capture_output=True,
                timeout=30,
            )
        rewrite_mirrors(workspace)

    def environment(self, job):
        cache = self.root / "builds/cache"
        return {
            "PATH": f"{self.tools}/jdk/bin:{self.tools}/gradle/bin:{self.tools}/node/bin:{self.tools}/venv/bin:{self.tools}/ubuntu/usr/sbin:/usr/bin:/bin:/usr/sbin",
            "HOME": "/tmp/home",
            "LANG": "C.UTF-8",
            "PYTHONUNBUFFERED": "1",
            "UV_INDEX_URL": job.get("pypi_source", PYPI),
            "UV_DEFAULT_INDEX": job.get("pypi_source", PYPI),
            "UV_CACHE_DIR": str(cache / "uv"),
            "UV_PYTHON_DOWNLOADS": "never",
            "UV_LINK_MODE": "copy",
            "PIP_INDEX_URL": job.get("pypi_source", PYPI),
            "PIP_CACHE_DIR": str(cache / "pip"),
            "npm_config_registry": NPM,
            "npm_config_cache": str(cache / "npm"),
            "npm_config_audit": "false",
            "npm_config_fund": "false",
            "NODE_OPTIONS": "--max-old-space-size=1536",
            "LIVELIFE_REMOTE_BACKEND": "true",
            "LIVELIFE_REMOTE_BACKEND_DEPENDENCIES_READY": "true",
            "LIVELIFE_FRONTEND_SHA": job["sha"],
            "GITHUB_RUN_ID": str(job["run_id"]),
            "GITHUB_RUN_ATTEMPT": str(job["attempt"]),
            "VITE_WEB_PREVIEW": "false" if job["component"] == "android" else "true",
            "VITE_ANDROID_TEST": "true" if job["component"] == "android" else "false",
            "VITE_TEST_PUBLIC_ORIGIN": "https://192.144.253.40",
            "JAVA_HOME": str(self.tools / "jdk"),
            # This host disallows mounting namespace procfs. Preserve the empty
            # /proc boundary and supply JDK libraries without /proc/self/exe.
            "LD_LIBRARY_PATH": f"{self.tools}/jdk/lib:{self.tools}/jdk/lib/jli:{self.tools}/jdk/lib/server",
            "ANDROID_HOME": str(self.tools / "android-sdk"),
            "GRADLE_USER_HOME": str(cache / "gradle"),
            "LIVELIFE_ANDROID_VERSION_CODE": str(json.loads(job.get("options") or "{}").get("version_code", 1)),
            "VITE_WEB_BUILD_ID": f"fe-{job['sha']}-{job['run_id']}-{job['attempt']}",
        }

    def run_command(self, job, workspace, command, log):
        log.write(("\n$ " + " ".join(command) + "\n").encode())
        log.flush()
        allowed = sorted(os.sched_getaffinity(0))
        start = int(job["id"][:2], 16) % max(1, len(allowed) // 4) * 4
        cpus = ",".join(str(c) for c in allowed[start : start + 4])
        command = [
            "prlimit",
            "--fsize=268435456",
            "--core=0",
            "--",
            "taskset",
            "--cpu-list",
            cpus,
            *sandbox_command(self.root, workspace, command),
        ]
        process = subprocess.Popen(
            command,
            env=self.environment(job),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        import selectors

        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        deadline = min(time.monotonic() + 1200, job.get("deadline", float("inf")))
        try:
            while selector.get_map():
                if time.monotonic() >= deadline:
                    raise TimeoutError("build command exceeded 20 minutes")
                for key, _ in selector.select(1):
                    data = os.read(key.fd, 65536)
                    if not data:
                        selector.unregister(key.fileobj)
                        continue
                    if log.tell() + len(data) > 4 * 1024**2:
                        raise ValueError("build log exceeds 4 MiB")
                    log.write(data)
                    log.flush()
            if process.wait(timeout=10):
                raise RuntimeError("check command failed; see build log")
        finally:
            selector.close()
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            process.stdout.close()

    def execute(self, job):
        directory = self.queue.jobs / job["id"]
        directory.mkdir(mode=0o700, exist_ok=True)
        workspace = directory / "repo"
        with (directory / "build.log").open("wb") as log:
            try:
                if shutil.disk_usage(self.root).free < 1024**3:
                    raise RuntimeError("less than 1 GiB free disk; build refused")
                job["deadline"] = time.monotonic() + 1800
                log.write(f"Course build {job['component']} {job['sha']}\n".encode())
                log.flush()
                self.checkout(job, workspace)
                if job["component"] == "backend":
                    self.run_command(
                        job,
                        workspace,
                        [
                            self.python,
                            "-m",
                            "unittest",
                            "discover",
                            "-s",
                            "deploy/tests",
                            "-v",
                        ],
                        log,
                    )
                    try:
                        self.run_command(
                            job,
                            workspace,
                            [
                                "uv",
                                "sync",
                                "--directory",
                                "backend",
                                "--locked",
                                "--python",
                                self.python,
                            ],
                            log,
                        )
                    except RuntimeError:
                        # Retry dependency preparation only. Tests are never
                        # rerun to hide a failed assertion or lint result.
                        job["pypi_source"] = PYPI_FALLBACK
                        rewrite_mirrors(workspace, job["pypi_source"])
                        log.write(
                            b"\nPrimary Python mirror unavailable; retrying verified locked dependencies with TUNA.\n"
                        )
                        self.run_command(
                            job,
                            workspace,
                            [
                                "uv",
                                "sync",
                                "--directory",
                                "backend",
                                "--locked",
                                "--python",
                                self.python,
                            ],
                            log,
                        )
                    self.run_command(
                        job, workspace, [self.python, "/runner/prepare-backend.py"], log
                    )
                    result = json.loads(
                        (
                            workspace / "deploy/.state/backend-artifact/manifest.json"
                        ).read_text()
                    )
                else:
                    if job["component"] == "android":
                        from .android_build import prepare
                        prepare(workspace, json.loads(job["options"]))
                    self.run_command(
                        job,
                        workspace,
                        [
                            "npm",
                            "ci",
                            "--prefix",
                            "frontend",
                            "--no-audit",
                            "--no-fund",
                        ],
                        log,
                    )
                    if job["component"] == "android":
                        self.run_command(job, workspace, ["/bin/sh", "-c",
                            "cd frontend && node --test scripts/*.test.mjs && npm run build:preview && npx --no-install cap sync android && cd android && gradle --init-script /runner/android-mirrors.gradle --no-daemon --max-workers=2 -Dorg.gradle.jvmargs=-Xmx1536m assembleRelease"], log)
                        from .android_build import package
                        result = package(workspace / 'frontend/android/app/build/outputs/apk/release/app-release-unsigned.apk', directory / 'artifact', json.loads(job['options']))
                    else:
                        self.run_command(
                            job,
                            workspace,
                            [
                                "/bin/sh",
                                "-c",
                                'cd frontend && node --test scripts/*.test.mjs && npm run build -- --base="/__livelife/web-builds/${VITE_WEB_BUILD_ID}/" && node scripts/check-preview-build.mjs',
                            ],
                            log,
                        )
                        from importlib.util import spec_from_file_location, module_from_spec

                        spec = spec_from_file_location(
                            "prepare_frontend", self.root / "control/prepare-frontend.py"
                        )
                        module = module_from_spec(spec)
                        spec.loader.exec_module(module)
                        result = module.package_frontend(
                            workspace / "frontend/dist",
                            directory / "artifact",
                            job["sha"],
                            job["run_id"],
                            job["attempt"],
                        )
                self.queue.finish(job["id"], result)
                log.write(b"\nAll checks passed.\n")
            except Exception as error:
                log.write(("\nFAILED: " + str(error)[:1000] + "\n").encode())
                self.queue.finish(job["id"], error=str(error))

    def serve(self):
        lock = self.queue.worker_lock()
        self.queue.recover()
        (self.root / "builds/cache").mkdir(exist_ok=True)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            active = set()
            last_collect = 0
            try:
                while True:
                    active = {f for f in active if not f.done()}
                    if time.monotonic() - last_collect > 3600:
                        self.queue.collect(self.root / "releases")
                        if (self.root / "builds/source.git").exists():
                            with (self.root / "builds/source.lock").open(
                                "a"
                            ) as source_lock:
                                fcntl.flock(source_lock, fcntl.LOCK_EX)
                                subprocess.run(
                                    [
                                        "git",
                                        "--git-dir",
                                        str(self.root / "builds/source.git"),
                                        "worktree",
                                        "prune",
                                    ],
                                    check=True,
                                )
                        last_collect = time.monotonic()
                    while len(active) < 2:
                        job = self.queue.claim()
                        if job is None:
                            break
                        active.add(pool.submit(self.execute, job))
                    time.sleep(1)
            finally:
                lock.close()


if __name__ == "__main__":
    Runner(Path(sys.argv[1])).serve()
