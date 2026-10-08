"""Reuse one authenticated course connection across short-lived RPC callers."""

import fcntl
import hashlib
import json
import os
from pathlib import Path
import random
import stat
import subprocess
import time


class CourseSSH:
    def __init__(self, root, command, remote):
        self.command, self.remote = list(command), remote
        directory = Path(root) / "ssh"
        directory.mkdir(mode=0o700, exist_ok=True)
        info = directory.lstat()
        if (
            not stat.S_ISDIR(info.st_mode)
            or info.st_uid != os.getuid()
            or info.st_mode & 0o077
        ):
            raise ValueError(
                "course SSH directory must be private and owned by the service user"
            )
        # Rotation of either credential file creates a fresh authenticated master.
        files = []
        for index, arg in enumerate(self.command):
            if arg == "-i":
                files.append(self.command[index + 1])
            elif arg.startswith("UserKnownHostsFile="):
                files.append(arg.split("=", 1)[1])
        stamps = [(p, Path(p).stat().st_ino, Path(p).stat().st_mtime_ns) for p in files]
        identity = hashlib.sha256(
            json.dumps([self.command, remote, stamps]).encode()
        ).hexdigest()[:32]
        self.socket = directory / ("c-" + identity)
        self.lock = directory / (identity + ".lock")
        if len(os.fsencode(self.socket)) >= 100:
            raise ValueError("course SSH socket path is too long")

    def check(self):
        result = subprocess.run(
            self.command + ["-S", str(self.socket), "-O", "check", self.remote],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0

    @staticmethod
    def transient(error):
        if any(
            marker in error
            for marker in (
                "Permission denied",
                "Host key verification failed",
                "REMOTE HOST IDENTIFICATION HAS CHANGED",
            )
        ):
            return False
        return any(
            marker in error
            for marker in (
                "Exceeded MaxStartups",
                "kex_exchange_identification",
                "Connection reset by peer",
                "Connection closed by",
                "Connection timed out",
            )
        )

    def ensure(self):
        # Only establishment is serialized. RPC sessions share the master in parallel.
        fd = os.open(self.lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if self.check():
                return
            if self.socket.exists() or self.socket.is_symlink():
                info = self.socket.lstat()
                if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
                    raise ValueError("unexpected course SSH control socket")
                self.socket.unlink()
            for attempt in range(4):
                result = subprocess.run(
                    self.command
                    + [
                        "-M",
                        "-N",
                        "-f",
                        "-S",
                        str(self.socket),
                        "-o",
                        "ControlPersist=120",
                        self.remote,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=25,
                )
                if result.returncode == 0 and self.check():
                    return
                if (
                    result.returncode == 0
                    or not self.transient(result.stderr)
                    or attempt == 3
                ):
                    raise RuntimeError(
                        "course SSH master establishment failed: "
                        + result.stderr[-1000:]
                    )
                # No session/RPC was sent by -N. Only authentication can be retried.
                time.sleep(2**attempt + random.uniform(0, 0.3))

    def rpc(self, request):
        self.ensure()
        # Never silently open a fresh TCP connection if the master disappeared.
        command = self.command + [
            "-S",
            str(self.socket),
            "-o",
            "ControlMaster=no",
            "-o",
            "ProxyCommand=false",
            self.remote,
        ]
        result = subprocess.run(
            command,
            input=json.dumps(request) + "\n",
            text=True,
            capture_output=True,
            timeout=780,
        )
        if result.returncode:
            # A lost response does not prove a mutation was not committed.
            raise RuntimeError(
                f"course RPC failed (operation not replayed): {result.stdout[-2000:]} {result.stderr[-1000:]}"
            )
        return json.loads(result.stdout)
