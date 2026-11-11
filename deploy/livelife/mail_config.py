"""Server-owned SMTP configuration for the shared course test environment."""

import argparse
import getpass
import json
import os
from pathlib import Path
import stat
import sys
import warnings

from .common import atomic_json

FIELDS = {"SMTP_HOST", "SMTP_PORT", "SMTP_FROM", "SMTP_USERNAME", "SMTP_PASSWORD"}
REQUIRED = {"SMTP_HOST", "SMTP_PORT", "SMTP_FROM"}
INVALID = "invalid SMTP configuration; check credentials/smtp.json privately"


def validate(value):
    if not isinstance(value, dict) or not REQUIRED <= value.keys() <= FIELDS:
        raise ValueError(INVALID)
    if any(
        not isinstance(item, str)
        or any(ord(char) < 32 or ord(char) == 127 for char in item)
        for item in value.values()
    ):
        raise ValueError(INVALID)
    if len(json.dumps(value, ensure_ascii=False).encode("utf-8")) > 12000:
        raise ValueError(INVALID)
    result = {
        key: item if key == "SMTP_PASSWORD" else item.strip()
        for key, item in value.items()
    }
    port = result["SMTP_PORT"]
    if (
        any(not result[key] for key in REQUIRED)
        or not port.isascii()
        or not port.isdigit()
        or len(port) > 5
        or not 1 <= int(port) <= 65535
        or bool(result.get("SMTP_USERNAME")) != bool(result.get("SMTP_PASSWORD"))
    ):
        raise ValueError(INVALID)
    return result


def private_path(path, *, directory=False):
    info = path.lstat()
    expected = stat.S_ISDIR if directory else stat.S_ISREG
    if not expected(info.st_mode):
        raise ValueError(INVALID)
    if os.name == "posix" and (
        info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077
    ):
        raise ValueError(INVALID)
    return info


def load(root):
    """Only this fixed, opt-in server file supplies mail credentials to the API."""
    directory = Path(root) / "credentials"
    path = directory / "smtp.json"
    if not directory.exists() and not directory.is_symlink():
        return {}
    # Reject a linked directory even if its target has no configuration yet.
    if directory.is_symlink():
        raise ValueError(INVALID)
    if not path.exists() and not path.is_symlink():
        return {}
    try:
        private_path(directory, directory=True)
        if private_path(path).st_size > 16384:
            raise ValueError(INVALID)
        return validate(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, UnicodeError):
        # Never include file contents, parser snippets or credentials in logs.
        raise ValueError(INVALID) from None


def save(root, value):
    value = validate(value)
    directory = Path(root) / "credentials"
    path = directory / "smtp.json"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    private_path(directory, directory=True)
    if path.exists() or path.is_symlink():
        private_path(path)
    atomic_json(path, value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument(
        "--check", action="store_true", help="validate without displaying values"
    )
    parser.add_argument("--host")
    parser.add_argument("--port", default="587")
    parser.add_argument("--sender")
    parser.add_argument("--username")
    args = parser.parse_args()
    if args.check:
        try:
            configured = bool(load(args.root))
        except ValueError:
            print(INVALID, file=sys.stderr)
            return 1
        print("SMTP configuration is valid" if configured else "SMTP is not configured")
        return 0 if configured else 1
    if not all((args.host, args.sender, args.username)):
        parser.error("--host, --sender and --username are required")
    if not sys.stdin.isatty():
        parser.error("use an interactive terminal to enter the SMTP password")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            password = getpass.getpass("SMTP authorization password (hidden): ")
        save(
            args.root,
            {
                "SMTP_HOST": args.host,
                "SMTP_PORT": args.port,
                "SMTP_FROM": args.sender,
                "SMTP_USERNAME": args.username,
                "SMTP_PASSWORD": password,
            },
        )
    except (OSError, ValueError, getpass.GetPassWarning):
        print(INVALID, file=sys.stderr)
        return 1
    print("SMTP configuration saved; restart selected API instances to apply")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
