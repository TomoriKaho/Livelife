"""Index public information: python -m app.retrieval {status,sync,rebuild,watch}."""

import argparse
import json
import logging
import time

from sqlalchemy import create_engine, func, or_, select
from sqlalchemy.orm import sessionmaker

from app.core.config import get_database_url
from app.db.models import RetrievalChunk, RetrievalState
from app.services.retrieval.config import get_retrieval_settings
from app.services.retrieval.indexing import process_batch, rebuild


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("status", "sync", "rebuild", "watch"))
    parser.add_argument("--batch-size", type=int, default=50)
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
    try:
        if args.command == "rebuild":
            print(json.dumps({"invalidated": rebuild(factory)}))
            return
        if args.command == "status":
            with factory() as session:
                stale = or_(
                    RetrievalState.indexed_revision.is_(None),
                    RetrievalState.indexed_revision != RetrievalState.revision,
                    RetrievalState.profile.is_(None),
                    RetrievalState.profile != settings.profile,
                )
                print(
                    json.dumps(
                        {
                            "profile": settings.profile,
                            "records": session.scalar(
                                select(func.count()).select_from(RetrievalState)
                            ),
                            "pending": session.scalar(
                                select(func.count()).select_from(RetrievalState).where(stale)
                            ),
                            "failed": session.scalar(
                                select(func.count())
                                .select_from(RetrievalState)
                                .where(RetrievalState.last_error.is_not(None))
                            ),
                            "chunks": session.scalar(
                                select(func.count()).select_from(RetrievalChunk)
                            ),
                        }
                    )
                )
            return
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
        engine.dispose()


if __name__ == "__main__":
    main()
