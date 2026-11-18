"""Trusted server CLI. Database access is the authorization boundary."""

import argparse
import json
import sys
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.db.models import FeedbackEvent, UserFeedback
from app.db.session import Database
from app.services.feedback.service import STATUSES, FeedbackError, change_status


def instant(value: str) -> datetime:
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.utcoffset() is None:
            raise ValueError
        return result
    except ValueError:
        raise argparse.ArgumentTypeError("Use an ISO timestamp with timezone") from None


def bounded_limit(value: str) -> int:
    try:
        result = int(value)
        if 1 <= result <= 100:
            return result
    except ValueError:
        pass
    raise argparse.ArgumentTypeError("limit must be 1-100")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    actions = root.add_subparsers(dest="action", required=True)
    listing = actions.add_parser("list", help="List newest receipt summaries (no content)")
    listing.add_argument("--status", choices=STATUSES)
    listing.add_argument("--user-id", type=UUID)
    listing.add_argument("--since", type=instant)
    listing.add_argument("--before", type=instant)
    listing.add_argument("--limit", type=bounded_limit, default=20)
    listing.add_argument("--offset", type=int, default=0)
    detail = actions.add_parser("show", help="Show feedback content and processing records")
    detail.add_argument("id", type=UUID)
    update = actions.add_parser("set-status", help="Change status with optimistic version check")
    update.add_argument("id", type=UUID)
    update.add_argument("status", choices=STATUSES)
    update.add_argument("--version", type=int, required=True)
    update.add_argument("--actor", required=True)
    update.add_argument("--reason", required=True)
    return root


def summary(row: UserFeedback) -> dict:
    return {
        key: getattr(row, key) for key in ("id", "user_id", "submitted_at", "status", "version")
    }


def execute(args: argparse.Namespace, database: Database) -> dict:
    if not database.configured or database.session_factory is None:
        raise FeedbackError(503, "Set DATABASE_URL before running feedback maintenance")
    with database.session_factory() as session:
        if args.action == "set-status":
            changed = change_status(
                session,
                args.id,
                args.status,
                actor=args.actor,
                reason=args.reason,
                version=args.version,
            )
            return {"id": args.id, "changed": changed}
        if args.action == "show":
            row = session.get(UserFeedback, args.id)
            if row is None:
                raise FeedbackError(404, "Feedback not found")
            events = session.scalars(
                select(FeedbackEvent)
                .where(FeedbackEvent.feedback_id == row.id)
                .order_by(FeedbackEvent.version)
            ).all()
            return {
                **summary(row),
                "content": row.content,
                "events": [
                    {
                        key: getattr(event, key)
                        for key in (
                            "created_at",
                            "actor",
                            "reason",
                            "from_status",
                            "to_status",
                            "version",
                        )
                    }
                    for event in events
                ],
            }
        if args.offset < 0:
            raise FeedbackError(422, "offset must be non-negative")
        statement = select(UserFeedback)
        for column, value in [
            (UserFeedback.status, args.status),
            (UserFeedback.user_id, args.user_id),
        ]:
            if value is not None:
                statement = statement.where(column == value)
        if args.since is not None:
            statement = statement.where(UserFeedback.submitted_at >= args.since)
        if args.before is not None:
            statement = statement.where(UserFeedback.submitted_at < args.before)
        rows = session.scalars(
            statement.order_by(UserFeedback.submitted_at.desc(), UserFeedback.id.desc())
            .limit(args.limit)
            .offset(args.offset)
        ).all()
        return {"items": [summary(row) for row in rows], "offset": args.offset}


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    database = None
    try:
        database = Database.from_environment()
        # JSON escapes control characters from untrusted feedback for terminal safety.
        print(json.dumps(execute(args, database), ensure_ascii=True, default=str))
        return 0
    except FeedbackError as error:
        print(f"Feedback maintenance failed ({error.status}): {error}", file=sys.stderr)
        return 1
    except (SQLAlchemyError, ValueError):
        print("Feedback database unavailable; check configuration and migrations", file=sys.stderr)
        return 1
    finally:
        if database is not None:
            database.close()


if __name__ == "__main__":
    raise SystemExit(main())
