"""A private Supervisor per project/user, never the host's Supervisor."""
from pathlib import Path
import subprocess
import time

from .common import atomic_text


class Supervisor:
    def __init__(self, root, python):
        self.root = Path(root).resolve()
        self.python = str(python)
        if any(c in str(self.root) for c in "\n\r% "):
            raise ValueError("control root must not contain whitespace or %")
        self.programs = self.root / "programs"
        self.programs.mkdir(parents=True, exist_ok=True)
        self.config = self.root / "supervisord.conf"
        atomic_text(self.config, f"""[unix_http_server]
file={self.root}/supervisor.sock
chmod=0600
[supervisord]
pidfile={self.root}/supervisord.pid
logfile={self.root}/supervisord.log
logfile_maxbytes=5MB
logfile_backups=2
childlogdir={self.root}
[rpcinterface:supervisor]
supervisor.rpcinterface_factory=supervisor.rpcinterface:make_main_rpcinterface
[supervisorctl]
serverurl=unix://{self.root}/supervisor.sock
[include]
files={self.programs}/*.conf
""")

    def ctl(self, *args, check=True):
        return subprocess.run([self.python, "-m", "supervisor.supervisorctl", "-c", str(self.config), *args],
                              capture_output=True, text=True, check=check, timeout=60)

    def ensure(self):
        if self.ctl("pid", check=False).returncode == 0:
            return
        subprocess.run([self.python, "-m", "supervisor.supervisord", "-c", str(self.config)],
                       check=True, capture_output=True, timeout=30)
        for _ in range(30):
            if self.ctl("pid", check=False).returncode == 0:
                return
            time.sleep(0.1)
        raise RuntimeError("project Supervisor failed to start")

    def configure(self, name, command, cwd, environment=""):
        self.ensure()
        content = f"""[program:{name}]
command={command}
directory={cwd}
autostart=true
autorestart=true
startsecs=1
startretries=5
stopasgroup=true
killasgroup=true
stopwaitsecs=15
stdout_logfile={self.root}/{name}.log
stdout_logfile_maxbytes=5MB
stdout_logfile_backups=2
redirect_stderr=true
"""
        if environment:
            content += f"environment={environment}\n"
        path = self.programs / f"{name}.conf"
        if not path.exists() or path.read_text() != content:
            atomic_text(path, content)
            self.ctl("reread")
            self.ctl("update", name)
        else:
            self.ctl("start", name, check=False)

    def remove(self, name):
        self.ensure()
        path = self.programs / f"{name}.conf"
        if path.exists():
            self.ctl("stop", name, check=False)
            path.unlink()
            self.ctl("reread")
            self.ctl("update")
