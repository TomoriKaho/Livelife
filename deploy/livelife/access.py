"""Private, server-only preview key provisioned independently of build artifacts."""
from pathlib import Path
import re
import secrets

from .common import atomic_text


def read_key(root):
    key = (Path(root) / 'credentials/preview-key.txt').read_text().strip()
    if not re.fullmatch('[0-9a-f]{64}', key):
        raise ValueError('invalid preview key file; provision it on the public host')
    return key


def configure(root, rotate=False):
    root = Path(root)
    credentials = root / 'credentials'
    credentials.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = credentials / 'preview-key.txt'
    if rotate or not path.exists():
        atomic_text(path, secrets.token_hex(32) + '\n')
    key = read_key(root)
    path.chmod(0o600)
    # Exact, case-sensitive regex: map's ordinary string entries ignore case.
    atomic_text(credentials / 'preview-key.conf', f'~^{key}$ 1;\n')


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Provision preview access without printing its secret')
    parser.add_argument('--root', default='/opt/livelife')
    parser.add_argument('--rotate', action='store_true')
    args = parser.parse_args()
    configure(args.root, args.rotate)
    print('Preview key configured; reload the Livelife gateway to apply it.')
