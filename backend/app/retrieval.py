"""Index public information: python -m app.retrieval {status,sync,rebuild,watch}."""

import argparse
import json
import logging
import time
from contextlib import ExitStack
from pathlib import Path

from sqlalchemy import create_engine, or_, select
from sqlalchemy.orm import sessionmaker

from app.core.config import get_database_url
from app.db.models import RetrievalState
from app.services.retrieval.config import get_retrieval_settings
from app.services.retrieval.indexing import process_batch, rebuild
from app.services.retrieval.maintenance import check, reconcile, status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("status", "sync", "rebuild", "watch", "reconcile", "check")
    )
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--lock-file", type=Path, help="Unix deployment worker election lock")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    settings = get_retrieval_settings()
    url = get_database_url()
    if not url:
        parser.error("DATABASE_URL is required; use an explicitly selected database")
    if args.command in {"sync", "watch"} and not settings.base_url:
        parser.error("EMBEDDING_BASE_URL is required")
    if not 1 <= args.batch_size <= 1000:
        parser.error("--batch-size must be between 1 and 1000")
    engine = create_engine(url)
    factory = sessionmaker(engine, expire_on_commit=False)
    resources = ExitStack()
    try:
        if args.lock_file:
            if args.command != "watch":
                parser.error("--lock-file is only supported by watch")
            import fcntl

            lock = resources.enter_context(args.lock_file.open("a"))
            # All API versions on one branch share this lock. Standby workers
            # take over after the active runtime exits; no stale PID files.
            fcntl.flock(lock, fcntl.LOCK_EX)
        if args.command == "reconcile":
            print(json.dumps({"created": reconcile(factory)}))
            return
        if args.command == "check":
            result = check(factory, settings)
            print(json.dumps(result))
            raise SystemExit(0 if result["ready"] else 1)
        if args.command == "rebuild":
            print(json.dumps({"invalidated": rebuild(factory)}))
            return
        if args.command == "status":
            print(json.dumps(status(factory, settings)))
            return
        reconcile(factory)
        failed = False
        while True:
            result = process_batch(factory, settings, batch_size=args.batch_size)
            failed = failed or bool(result["failed"])
            print(json.dumps(result), flush=True)
            if result["failed"]:
                if args.command == "sync":
                    raise SystemExit(1)
                time.sleep(5)
            if result["selected"] == 0:
                if args.command == "sync":
                    with factory() as session:
                        pending = session.scalar(
                            select(RetrievalState.information_id)
                            .where(
                                or_(
                                    RetrievalState.indexed_revision.is_(None),
                                    RetrievalState.indexed_revision != RetrievalState.revision,
                                    RetrievalState.profile.is_(None),
                                    RetrievalState.profile != settings.profile,
                                )
                            )
                            .limit(1)
                        )
                    raise SystemExit(1 if failed or pending is not None else 0)
                time.sleep(5)
    except KeyboardInterrupt:
        return
    finally:
        resources.close()
        engine.dispose()


if __name__ == "__main__":
    main()
