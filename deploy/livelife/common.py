"""Validation and atomic files shared by the two server-side tools."""
import json
import os
from pathlib import Path
import re
import tempfile


def read_request(stream, limit):
    """One bounded JSON object; do not wait for SSH EOF after its closing brace."""
    chunks = []
    size = depth = 0
    started = quoted = escaped = False
    while True:
        chunk = stream.read1(min(65536, limit + 1 - size))
        if not chunk:
            raise ValueError('incomplete JSON request')
        size += len(chunk)
        if size > limit:
            raise ValueError('request exceeds limit')
        for index, value in enumerate(chunk):
            if not started:
                if value in b' \t\r\n':
                    continue
                if value != ord('{'):
                    raise ValueError('request must be a JSON object')
                started, depth = True, 1
            elif quoted:
                if escaped:
                    escaped = False
                elif value == ord('\\'):
                    escaped = True
                elif value == ord('"'):
                    quoted = False
            elif value == ord('"'):
                quoted = True
            elif value in b'{[':
                depth += 1
            elif value in b'}]':
                depth -= 1
                if depth == 0:
                    if chunk[index + 1:].strip():
                        raise ValueError('trailing data after JSON request')
                    return json.loads(b''.join(chunks) + chunk[:index + 1])
        chunks.append(chunk)


def sha(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{40}", value):
        raise ValueError("expected full lowercase Git SHA")
    return value


def instance(value):
    if not isinstance(value, str) or not re.fullmatch(r"be-[0-9a-f]{40}", value):
        raise ValueError("invalid backend instance ID")
    return value


def owner(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"main|pr:[1-9][0-9]*|frontend:([1-9][0-9]*|branch-[0-9a-f]{32})|branch:[0-9a-f]{32}|web:[0-9a-f]{32}", value
    ):
        raise ValueError("invalid owner ID")
    return value


def atomic_json(path, value):
    atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def atomic_text(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".next-")
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)
