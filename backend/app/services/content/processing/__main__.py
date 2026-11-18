"""Explicit file import/extraction/review; no scheduling or implicit migrations."""

import argparse
import asyncio
import json
from pathlib import Path
from uuid import UUID

from app.db.session import Database
from app.schemas.information import InformationInput
from app.services.content.processing.batch import run_batch
from app.services.content.processing.service import Processor


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    submit = sub.add_parser("submit")
    submit.add_argument("file", type=Path)
    run = sub.add_parser("run")
    run.add_argument("job_id", type=UUID)
    run.add_argument("--retry", action="store_true")
    retry = sub.add_parser("retry")
    retry.add_argument("job_id", type=UUID)
    listing = sub.add_parser("list")
    listing.add_argument("--status")
    listing.add_argument("--version")
    listing.add_argument("--limit", type=int, default=50)
    listing.add_argument("--offset", type=int, default=0)
    batch = sub.add_parser("batch")
    batch.add_argument("manifest", type=Path, help="JSON output from submit")
    batch.add_argument("--retry-failed", action="store_true")
    batch.add_argument("--output", type=Path, required=True)
    show = sub.add_parser("show")
    show.add_argument("job_id", type=UUID)
    export = sub.add_parser("export-fallback")
    export.add_argument("job_id", type=UUID)
    fallback = sub.add_parser("fallback")
    fallback.add_argument("file", type=Path)
    fallback.add_argument("--reviewed-by", required=True)
    fallback.add_argument("--reason", required=True)
    publish = sub.add_parser("publish")
    publish.add_argument("job_id", type=UUID)
    publish.add_argument("--reviewed-by", required=True)
    publish.add_argument("--reason", required=True)
    args = parser.parse_args()
    db = Database.from_environment()
    try:
        if not db.session_factory:
            parser.error("set development DATABASE_URL and run alembic upgrade head first")
        service = Processor(db.session_factory)
        if args.command == "submit":
            if args.file.stat().st_size > 10_000_000:
                parser.error("input file exceeds 10 MB")
            rows = json.loads(args.file.read_text())
            rows = rows if isinstance(rows, list) else [rows]
            if not 1 <= len(rows) <= 100:
                parser.error("submit 1-100 records")
            records = [InformationInput.model_validate(row) for row in rows]
            result = [
                {"job_id": service.submit(row), "source_id": row.source_id} for row in records
            ]
        elif args.command == "run":
            result = asyncio.run(service.process(args.job_id, retry=args.retry))
        elif args.command == "retry":
            result = asyncio.run(service.retry_failed(args.job_id))
        elif args.command == "list":
            result = service.list_jobs(
                status=args.status, version=args.version, limit=args.limit, offset=args.offset
            )
        elif args.command == "batch":
            if args.manifest.stat().st_size > 1_000_000:
                parser.error("manifest exceeds 1 MB")
            manifest = json.loads(args.manifest.read_text())

            def checkpoint(results):
                temporary = args.output.with_suffix(args.output.suffix + ".tmp")
                temporary.write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str))
                temporary.replace(args.output)

            result = asyncio.run(
                run_batch(
                    service,
                    [row["job_id"] for row in manifest],
                    retry_failed=args.retry_failed,
                    on_result=checkpoint,
                )
            )
        elif args.command == "export-fallback":
            result = service.export_fallback(args.job_id)
        elif args.command == "fallback":
            if args.file.stat().st_size > 1_000_000:
                parser.error("fallback file exceeds 1 MB")
            result = {
                "job_id": service.manual_fallback(
                    json.loads(args.file.read_text()),
                    reviewed_by=args.reviewed_by,
                    reason=args.reason,
                )
            }
        elif args.command == "show":
            result = service.get(args.job_id)
        else:
            result = {
                "information_id": service.publish(
                    args.job_id, reviewed_by=args.reviewed_by, reason=args.reason
                )
            }
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        if args.command in {"run", "retry"} and result["status"] == "failed":
            raise SystemExit(1)
        if args.command == "batch" and any(
            row["batch_error"] or row["status"] not in {"needs_review", "published"}
            for row in result
        ):
            raise SystemExit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
