"""Package only the completed static build, with a verifiable CI identity."""
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import tarfile

root = Path(__file__).resolve().parents[1]
commit = os.environ['LIVELIFE_FRONTEND_SHA']
run = int(os.environ['GITHUB_RUN_ID'])
attempt = int(os.environ['GITHUB_RUN_ATTEMPT'])
ident = f'fe-{commit}-{run}-{attempt}'
dist = root / 'frontend/dist'
payload = io.BytesIO()
with gzip.GzipFile(fileobj=payload, mode='wb', mtime=0) as compressed:
    with tarfile.open(fileobj=compressed, mode='w') as archive:
        for path in sorted(dist.rglob('*')):
            if path.is_file():
                item = archive.gettarinfo(str(path), arcname=str(path.relative_to(dist)))
                item.uid = item.gid = item.mtime = 0
                item.uname = item.gname = ''
                item.mode = 0o644
                with path.open('rb') as source:
                    archive.addfile(item, source)
bundle = payload.getvalue()
if len(bundle) > 64 * 1024**2:
    raise SystemExit('frontend bundle exceeds 64 MiB')
output = root / 'deploy/.state/frontend-artifact'
output.mkdir(parents=True, exist_ok=True)
(output / 'frontend.tgz').write_bytes(bundle)
(output / 'manifest.json').write_text(json.dumps({'schema_version': 1, 'frontend_sha': commit,
    'run_id': run, 'run_attempt': attempt, 'build_id': ident,
    'digest': hashlib.sha256(bundle).hexdigest()}))
