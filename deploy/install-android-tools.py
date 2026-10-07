"""Project-local, checksum-verified Android tools; no sudo or signing secrets."""

import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import xml.etree.ElementTree as ET
import zipfile

GRADLE = "8.14.3"
JDK = "21.0.8+9"
PACKAGES = {
    "platform-tools": "platform-tools",
    "build-tools;36.0.0": "build-tools/36.0.0",
    "platforms;android-36": "platforms/android-36",
    "cmdline-tools;19.0": "cmdline-tools/19.0",
}


def download(url, limit=256 * 1024**2):
    value = subprocess.check_output(
        [
            "curl",
            "--fail",
            "--silent",
            "--show-error",
            "--location",
            "--connect-timeout",
            "10",
            "--max-time",
            "900",
            "--max-filesize",
            str(limit),
            url,
        ],
        timeout=910,
    )
    if len(value) > limit:
        raise ValueError("tool download exceeds limit")
    return value


def verified(url, expected, algorithm="sha256"):
    data = download(url)
    if hashlib.new(algorithm, data).hexdigest() != expected:
        raise ValueError("tool checksum mismatch: " + url)
    return data


def extract_zip(data, destination):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        total = 0
        for info in archive.infolist():
            path = Path(info.filename)
            total += info.file_size
            if (
                path.is_absolute()
                or ".." in path.parts
                or total > 1024**3
                or (info.external_attr >> 16) & 0o170000 == 0o120000
            ):
                raise ValueError("unsafe tool archive")
        archive.extractall(destination)
        for info in archive.infolist():
            if (info.external_attr >> 16) & 0o111:
                (destination / info.filename).chmod(0o755)


def install(root, signing_only=False):
    tools = root / "build-tools"
    tools.mkdir(parents=True, exist_ok=True)
    records = {}
    if not (tools / "jdk/bin/java").is_file():
        asset = json.loads(
            download(
                "https://api.azul.com/metadata/v1/zulu/packages/5e5dcd0a-1358-476e-ae9a-bc4cf3e37405",
                65536,
            )
        )
        url, checksum = asset["download_url"], asset["sha256_hash"]
        if (
            asset["java_version"] != [21, 0, 8]
            or checksum
            != "63f56bbb46958cf57352fba08f2755e0953799195e5545acc0c8a92920beff1e"
        ):
            raise ValueError("unexpected pinned JDK metadata")
        asset = {"link": url, "checksum": checksum}
        data = verified(url + "?livelife=android28", checksum)
        with tempfile.TemporaryDirectory(dir=tools) as tmp:
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
                archive.extractall(tmp, filter="data")
            dirs = list(Path(tmp).iterdir())
            if len(dirs) != 1:
                raise ValueError("unexpected JDK archive")
            dirs[0].rename(tools / "jdk")
        records["jdk"] = {
            "version": JDK,
            "sha256": asset["checksum"],
            "url": asset["link"],
        }
    sdk = tools / "android-sdk"
    sdk.mkdir(exist_ok=True)
    # Checksums come from Google's HTTPS repository metadata, not mirrors.
    xml = ET.fromstring(
        download(
            "https://dl.google.com/android/repository/repository2-3.xml", 16 * 1024**2
        )
    )
    needed = {"build-tools;36.0.0"} if signing_only else set(PACKAGES)
    for package in xml.iter():
        if (
            package.tag.rsplit("}", 1)[-1] != "remotePackage"
            or package.get("path") not in needed
        ):
            continue
        name = package.get("path")
        destination = sdk / PACKAGES[name]
        if destination.exists():
            continue
        for archive in package.iter("archive"):
            host = archive.findtext("host-os")
            if host not in (None, "linux"):
                continue
            complete = archive.find("complete")
            if complete is None:
                continue
            checksum = complete.find("checksum")
            url = "https://dl.google.com/android/repository/" + complete.findtext("url")
            data = verified(url, checksum.text, checksum.get("type", "sha1"))
            with tempfile.TemporaryDirectory(dir=tools) as tmp:
                extract_zip(data, Path(tmp))
                dirs = list(Path(tmp).iterdir())
                if len(dirs) != 1:
                    raise ValueError("unexpected SDK archive")
                destination.parent.mkdir(parents=True, exist_ok=True)
                dirs[0].rename(destination)
            records[name] = {
                "url": url,
                "checksum": checksum.text,
                "algorithm": checksum.get("type", "sha1"),
            }
            break
    if not signing_only:
        for name in needed:
            if not (sdk / PACKAGES[name]).exists():
                raise ValueError("required SDK package missing: " + name)
        # License acceptance is an explicit maintainer step, never implicit here.
        if not (tools / "gradle/bin/gradle").is_file():
            url = f"https://downloads.gradle.org/distributions/gradle-{GRADLE}-bin.zip"
            checksum = download(url + ".sha256", 1024).decode().strip()
            data = verified(f'https://mirrors.huaweicloud.com/gradle/gradle-{GRADLE}-bin.zip?livelife=android28', checksum)
            with tempfile.TemporaryDirectory(dir=tools) as tmp:
                extract_zip(data, Path(tmp))
                (Path(tmp) / f"gradle-{GRADLE}").rename(tools / "gradle")
            records["gradle"] = {"version": GRADLE, "sha256": checksum, "url": url}
    manifest = tools / "android-tools.json"
    previous = json.loads(manifest.read_text()) if manifest.exists() else {}
    manifest.write_text(json.dumps({**previous, **records}, indent=2) + "\n")
    print(
        "Android tools installed. Maintainer: review/accept SDK licenses with sdkmanager --licenses."
    )


if __name__ == "__main__":
    install(Path(sys.argv[1]).resolve(), "--signing-only" in sys.argv[2:])
