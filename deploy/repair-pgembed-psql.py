"""Repair the known pgembed 0.2.0 Linux x86_64 psql ELF, without altering uv's cache."""

import hashlib
import importlib.metadata
import os
from pathlib import Path
import platform
import stat
import struct
import subprocess
import tempfile

ORIGINAL = "96c9132818e047bf76be2354b553329a2841fdcf2195ba70e7ca8b4362e9388e"
REPAIRED = "b234b65ed4d41adc520b905bd0d167c99681016701972a7eeacd1a34048be753"


def repair(path):
    path = Path(path)
    if path.is_symlink():
        raise ValueError("psql must be a regular installed file")
    data = bytearray(path.read_bytes())
    digest = hashlib.sha256(data).hexdigest()
    if digest == REPAIRED:
        return False
    if digest != ORIGINAL:
        raise ValueError("unknown pgembed psql binary; refusing to patch")
    # The LOAD at program-header offset 456 covers the page containing DT_DEBUG.
    # Restore PF_W (R -> RW). This segment stays non-executable; no code changes.
    if struct.unpack_from("<II", data, 456) != (1, 4):
        raise ValueError("unexpected psql program header")
    struct.pack_into("<I", data, 460, 6)
    if hashlib.sha256(data).hexdigest() != REPAIRED:
        raise ValueError("psql repair digest mismatch")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".psql-repair-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(stat.S_IMODE(path.stat().st_mode))
        # uv may hard-link the original from its cache. Never modify it in place.
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return True


def main():
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        print("pgembed psql repair is only needed for the known Linux x86_64 wheel")
        return
    if importlib.metadata.version("pgembed") != "0.2.0":
        raise ValueError("review the native tool workaround when changing pgembed")
    from pgembed.postgres_server import POSTGRES_BIN_PATH
    path = POSTGRES_BIN_PATH / "psql"
    changed = repair(path)
    subprocess.run([str(path), "--version"], check=True, timeout=10)
    print(f"pgembed psql verified; repaired={changed}; sha256={REPAIRED}")


if __name__ == "__main__":
    main()
