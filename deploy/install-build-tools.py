"""Install pinned project tools under group5's home; no sudo/system changes."""

import hashlib
import io
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

NODE = "24.13.0"
NPM = "11.6.2"
PYPI = "https://pypi.tuna.tsinghua.edu.cn/simple"
UBUNTU = "https://mirrors.tuna.tsinghua.edu.cn/ubuntu/"


def download(url, limit=64 * 1024**2):
    # Bounded downloads: the course host's curl path was measured separately.
    data = subprocess.check_output(
        [
            "curl",
            "--fail",
            "--silent",
            "--show-error",
            "--location",
            "--connect-timeout",
            "10",
            "--max-time",
            "90",
            "--range",
            f"0-{limit}",
            "--max-filesize",
            str(limit),
            url,
        ],
        timeout=100,
    )
    if len(data) > limit:
        raise ValueError("tool download exceeds size limit")
    return data


def apt_options(tools):
    apt = tools / "apt"
    return [
        "-o",
        f"Dir::State::lists={apt}/lists",
        "-o",
        f"Dir::Cache={apt}/cache",
        "-o",
        "Dir::Cache::pkgcache=",
        "-o",
        "Dir::Cache::srcpkgcache=",
        "-o",
        f"Dir::Etc::sourcelist={apt}/sources.list",
        "-o",
        "Dir::Etc::sourceparts=-",
        "-o",
        "Dir::Etc::parts=-",
        "-o",
        "Dir::Etc::main=-",
        "-o",
        "APT::Sandbox::User=group5",
    ]


def refresh_apt(tools):
    apt = tools / "apt"
    (apt / "lists/partial").mkdir(parents=True, exist_ok=True)
    (apt / "cache/archives/partial").mkdir(parents=True, exist_ok=True)
    source = "".join(
        f"deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] {UBUNTU} {suite} main\n"
        for suite in ["noble", "noble-updates", "noble-security"]
    )
    (apt / "sources.list").write_text(source)
    subprocess.run(["apt-get", *apt_options(tools), "update"], check=True, timeout=180)


def apt_tool(package, directory, tools):
    metadata = subprocess.check_output(
        ["apt-cache", *apt_options(tools), "show", package], text=True
    ).split("\n\n")[0]
    fields = dict(
        line.split(": ", 1)
        for line in metadata.splitlines()
        if ": " in line and not line.startswith(" ")
    )
    filename = fields["Filename"]
    if ".." in Path(filename).parts or not filename.startswith("pool/"):
        raise ValueError("unexpected apt package path")
    data = None
    for base in (
        UBUNTU,
        "https://mirrors.aliyun.com/ubuntu/",
        "https://archive.ubuntu.com/ubuntu/",
    ):
        try:
            data = download(base + filename, 8 * 1024**2)
            break
        except subprocess.CalledProcessError:
            continue
    if data is None:
        raise ValueError(
            "APT tool version unavailable; refresh project-local APT metadata"
        )
    if hashlib.sha256(data).hexdigest() != fields["SHA256"]:
        raise ValueError("tool does not match trusted APT metadata")
    with tempfile.NamedTemporaryFile(suffix=".deb") as stream:
        stream.write(data)
        stream.flush()
        subprocess.run(["dpkg-deb", "-x", stream.name, str(directory)], check=True)


def main(root):
    tools = root / "build-tools"
    tools.mkdir(mode=0o700, parents=True, exist_ok=True)
    ubuntu = tools / "ubuntu"
    if (
        not (ubuntu / "usr/bin/bwrap").exists()
        or not (ubuntu / "usr/sbin/nginx").exists()
    ):
        refresh_apt(tools)
    for package, probe in [
        ("bubblewrap", "usr/bin/bwrap"),
        ("nginx", "usr/sbin/nginx"),
        ("nginx-common", "etc/nginx/mime.types"),
    ]:
        if not (ubuntu / probe).exists():
            apt_tool(package, ubuntu, tools)
    node = tools / "node"
    if not (node / "bin/node").exists():
        name = f"node-v{NODE}-linux-x64.tar.xz"
        # Authenticate the mirror bytes against the official release manifest.
        sums = download(
            f"https://nodejs.org/dist/v{NODE}/SHASUMS256.txt", 65536
        ).decode()
        expected = next(
            line.split()[0] for line in sums.splitlines() if line.split()[-1] == name
        )
        data = download(f"https://registry.npmmirror.com/-/binary/node/v{NODE}/{name}")
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError("Node mirror checksum mismatch")
        with tempfile.TemporaryDirectory(dir=tools) as temporary:
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:xz") as archive:
                archive.extractall(temporary, filter="data")
            Path(temporary, f"node-v{NODE}-linux-x64").rename(node)
    venv = tools / "venv"
    if not (venv / "bin/python").exists():
        subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
    installed = (
        subprocess.run(
            [
                str(venv / "bin/python"),
                "-c",
                'import importlib.metadata; assert importlib.metadata.version("supervisor")=="4.3.0"',
            ],
            capture_output=True,
        ).returncode
        == 0
    )
    if not installed:
        for index in ("https://mirrors.aliyun.com/pypi/simple/", PYPI):
            result = subprocess.run(
                [
                    str(venv / "bin/python"),
                    "-m",
                    "pip",
                    "install",
                    "--index-url",
                    index,
                    "supervisor==4.3.0",
                ]
            )
            if result.returncode == 0:
                break
        else:
            raise RuntimeError(
                "pinned Supervisor unavailable from both package mirrors"
            )
    if not (venv / "bin/uv").exists():
        import json
        import zipfile

        metadata = json.loads(
            download("https://pypi.org/pypi/uv/0.12.23/json", 1024**2)
        )
        wheel = next(
            item
            for item in metadata["urls"]
            if item["filename"].endswith(
                "manylinux_2_17_x86_64.manylinux2014_x86_64.whl"
            )
        )
        for base in (
            "https://mirrors.aliyun.com/pypi/",
            "https://pypi.tuna.tsinghua.edu.cn/",
        ):
            try:
                data = download(
                    wheel["url"].replace("https://files.pythonhosted.org/", base)
                )
                if hashlib.sha256(data).hexdigest() != wheel["digests"]["sha256"]:
                    raise ValueError("uv mirror checksum mismatch")
                with zipfile.ZipFile(io.BytesIO(data)) as archive:
                    name = next(
                        name
                        for name in archive.namelist()
                        if name.endswith(".data/scripts/uv")
                    )
                    (venv / "bin/uv").write_bytes(archive.read(name))
                    (venv / "bin/uv").chmod(0o755)
                break
            except subprocess.CalledProcessError:
                continue
        else:
            raise RuntimeError("verified uv tool wheel unavailable from both mirrors")
    version = subprocess.check_output(
        [
            str(node / "bin/node"),
            str(node / "lib/node_modules/npm/bin/npm-cli.js"),
            "--version",
        ],
        text=True,
    ).strip()
    if version != NPM:
        subprocess.run(
            [
                str(node / "bin/node"),
                str(node / "lib/node_modules/npm/bin/npm-cli.js"),
                "install",
                "--prefix",
                str(node),
                "--global",
                "--registry",
                "https://registry.npmmirror.com",
                "npm@" + NPM,
            ],
            check=True,
        )
    subprocess.run(
        [
            str(ubuntu / "usr/bin/bwrap"),
            "--unshare-all",
            "--share-net",
            "--ro-bind",
            "/usr",
            "/usr",
            "--ro-bind",
            "/lib",
            "/lib",
            "--ro-bind",
            "/lib64",
            "/lib64",
            "--",
            "/usr/bin/true",
        ],
        check=True,
    )
    print(
        "Pinned Node/npm, uv, Supervisor, Nginx and namespace sandbox installed in project tools."
    )


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "/home/group5/livelife").resolve())
