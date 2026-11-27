"""Run one installed, immutable embedding service with only its own credentials."""

import argparse
import os
from pathlib import Path

from .retrieval_config import model_environment, service_settings


def environment(root, service, settings):
    env = {key: os.environ[key] for key in (
        "PATH", "HOME", "LANG", "LC_ALL", "SSL_CERT_FILE", "SSL_CERT_DIR", "TMPDIR"
    ) if key in os.environ}
    env.update(model_environment(settings))
    env.update(
        HF_HOME=str(Path(root) / "embedding" / service / "cache"),
        HF_HUB_OFFLINE="1", PYTHONUNBUFFERED="1",
    )
    return env


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--service", required=True)
    args = parser.parse_args()
    settings = service_settings(args.root, args.service)
    backend = args.root.resolve() / "embedding" / args.service / "backend"
    python = backend / ".venv/bin/python"
    os.chdir(backend)
    os.execve(str(python), [str(python), "-m", "uvicorn", "app.embedding_server:app",
                           "--host", "127.0.0.1", "--port", str(settings["port"])],
              environment(args.root.resolve(), args.service, settings))


if __name__ == "__main__":
    main()
