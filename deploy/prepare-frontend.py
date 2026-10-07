"""Package completed static files using a trusted build identity."""

import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import tarfile


def package_frontend(dist, output, commit, run, attempt):
    from livelife.common import sha

    commit = sha(commit)
    ident = f"fe-{commit}-{int(run)}-{int(attempt)}"
    dist, output = Path(dist), Path(output)
    payload = io.BytesIO()
    count = total = 0
    with gzip.GzipFile(fileobj=payload, mode="wb", mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode="w") as archive:
            for path in sorted(dist.rglob("*")):
                if path.is_symlink() or not (path.is_dir() or path.is_file()):
                    raise ValueError("static build contains a link or special file")
                if path.is_file():
                    count += 1
                    total += path.stat().st_size
                    if count > 10000 or total > 256 * 1024**2:
                        raise ValueError("static build expanded size exceeds limit")
                    item = archive.gettarinfo(
                        str(path), arcname=str(path.relative_to(dist))
                    )
                    item.uid = item.gid = item.mtime = 0
                    item.uname = item.gname = ""
                    item.mode = 0o644
                    with path.open("rb") as source:
                        archive.addfile(item, source)
    bundle = payload.getvalue()
    if len(bundle) > 64 * 1024**2:
        raise ValueError("frontend bundle exceeds 64 MiB")
    if not (dist / "index.html").is_file():
        raise ValueError("static build lacks index.html")
    manifest = {
        "schema_version": 1,
        "frontend_sha": commit,
        "run_id": int(run),
        "run_attempt": int(attempt),
        "build_id": ident,
        "digest": hashlib.sha256(bundle).hexdigest(),
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "frontend.tgz").write_bytes(bundle)
    (output / "manifest.json").write_text(json.dumps(manifest))
    return manifest


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    package_frontend(
        root / "frontend/dist",
        root / "deploy/.state/frontend-artifact",
        os.environ["LIVELIFE_FRONTEND_SHA"],
        os.environ["GITHUB_RUN_ID"],
        os.environ["GITHUB_RUN_ATTEMPT"],
    )
