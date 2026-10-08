"""Create a persistent TEST-only signing key; never print/export its secret."""

import hashlib
from pathlib import Path
import secrets
import subprocess
import sys

root = Path(sys.argv[1]).resolve()
credentials = root / "credentials"
credentials.mkdir(mode=0o700, exist_ok=True)
key = credentials / "android-test.jks"
password = credentials / "android-test.pass"
keytool = root / "build-tools/jdk/bin/keytool"
if not key.exists():
    if password.exists():
        raise SystemExit(
            "Password already exists but keystore missing; inspect before replacing credentials"
        )
    password.write_text(secrets.token_urlsafe(48) + "\n")
    password.chmod(0o600)
    subprocess.run(
        [
            str(keytool),
            "-genkeypair",
            "-keystore",
            str(key),
            "-alias",
            "livelife-test",
            "-keyalg",
            "RSA",
            "-keysize",
            "3072",
            "-validity",
            "10000",
            "-dname",
            "CN=Livelife Test, OU=Development, O=Livelife",
            "-storepass:file",
            str(password),
            "-keypass:file",
            str(password),
        ],
        check=True,
        capture_output=True,
        timeout=60,
    )
    key.chmod(0o600)
cert = subprocess.check_output(
    [
        str(keytool),
        "-exportcert",
        "-keystore",
        str(key),
        "-alias",
        "livelife-test",
        "-storepass:file",
        str(password),
    ],
    timeout=30,
)
(credentials / "android-test.sha256").write_text(
    hashlib.sha256(cert).hexdigest() + "\n"
)
print(
    "Persistent Android test signing key is ready; private files remain on this host."
)
