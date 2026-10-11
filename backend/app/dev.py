"""Run the API with automatically prepared, persistent local PostgreSQL."""

import argparse
import os
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path

import uvicorn

from app.core.config import get_database_url
from app.db.local import BACKEND, DEFAULT_DATA_DIR, local_database


@contextmanager
def development_database(data_dir: Path) -> Iterator[str]:
    if get_database_url() is not None:
        raise RuntimeError(
            "DATABASE_URL is already set. For automatic local PostgreSQL, unset it first. "
            "To use your configured database, run uvicorn app.main:app instead."
        )
    previous = os.environ.get("DATABASE_URL")
    try:
        with local_database(data_dir) as url:
            os.environ["DATABASE_URL"] = url
            yield url
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true", help="Reload API code without stopping DB")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    print(f"Preparing local PostgreSQL in {args.data_dir.resolve()} ...", flush=True)
    try:
        with development_database(args.data_dir) as url:
            print(f"Local DATABASE_URL={url}", flush=True)
            # Resolve the app from this checkout even when invoked from another directory.
            uvicorn.run(
                "app.main:app",
                host="127.0.0.1",
                port=args.port,
                reload=args.reload,
                reload_dirs=[str(BACKEND / "app")] if args.reload else None,
            )
    except RuntimeError as exc:
        parser.exit(1, f"{exc}\n")
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
