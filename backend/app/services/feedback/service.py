from datetime import UTC, datetime, timedelta
from math import ceil
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import FeedbackEvent, User, UserFeedback
from app.schemas.feedback import FeedbackReceipt, FeedbackSubmission

STATUSES = ("pending", "processing", "resolved", "closed")


class FeedbackError(ValueError):
    def __init__(self, status: int, detail: str, retry_after: int | None = None):
        super().__init__(detail)
        self.status = status
        self.retry_after = retry_after


def lock_owner(session: Session, user_id: UUID) -> None:
    if session.scalar(select(User.id).where(User.id == user_id).with_for_update()) is None:
        raise FeedbackError(401, "Session is invalid or expired")


def submit_feedback(
    session: Session, user_id: UUID, payload: FeedbackSubmission
) -> tuple[FeedbackReceipt, bool]:
    """Own the transaction; lock account before any mutation, including deletion."""
    try:
        lock_owner(session, user_id)
        existing = session.scalar(
            select(UserFeedback).where(
                UserFeedback.user_id == user_id,
                UserFeedback.client_request_id == payload.client_request_id,
            )
        )
        if existing is not None:
            if existing.content != payload.content:
                raise FeedbackError(409, "Request ID already belongs to different feedback")
            receipt = FeedbackReceipt.model_validate(existing)
            session.commit()
            return receipt, False
        now = datetime.now(UTC)
        recent = session.scalars(
            select(UserFeedback.submitted_at)
            .where(
                UserFeedback.user_id == user_id,
                UserFeedback.submitted_at > now - timedelta(days=1),
            )
            .order_by(UserFeedback.submitted_at.desc())
        ).all()
        for interval, maximum in [(timedelta(minutes=1), 3), (timedelta(days=1), 20)]:
            window = [instant for instant in recent if instant > now - interval]
            if len(window) >= maximum:
                retry = max(1, ceil((window[maximum - 1] + interval - now).total_seconds()))
                raise FeedbackError(429, "Feedback submission limit reached", retry)
        row = UserFeedback(
            id=uuid4(),
            user_id=user_id,
            client_request_id=payload.client_request_id,
            content=payload.content,
            submitted_at=now,
            status="pending",
            version=1,
        )
        session.add(row)
        receipt = FeedbackReceipt.model_validate(row)
        session.commit()
        return receipt, True
    except Exception:
        session.rollback()
        raise


def change_status(
    session: Session, feedback_id: UUID, target: str, *, actor: str, reason: str, version: int
) -> bool:
    actor, reason = actor.strip(), reason.strip()
    if target not in STATUSES or not 1 <= len(actor) <= 100 or not 1 <= len(reason) <= 1000:
        raise FeedbackError(422, "Valid status, actor (1-100) and reason (1-1000) required")
    if "\x00" in actor + reason or version < 1:
        raise FeedbackError(422, "Invalid audit fields or version")
    try:
        owner = session.scalar(select(UserFeedback.user_id).where(UserFeedback.id == feedback_id))
        if owner is None:
            raise FeedbackError(404, "Feedback not found")
        lock_owner(session, owner)
        row = session.scalar(
            select(UserFeedback).where(UserFeedback.id == feedback_id).with_for_update()
        )
        if row is None:
            raise FeedbackError(404, "Feedback not found")
        if row.version != version:
            raise FeedbackError(409, "Feedback changed; show it again and use the current version")
        if row.status == target:
            session.commit()
            return False
        session.add(
            FeedbackEvent(
                id=uuid4(),
                feedback_id=row.id,
                created_at=datetime.now(UTC),
                actor=actor,
                reason=reason,
                from_status=row.status,
                to_status=target,
                version=row.version + 1,
            )
        )
        row.status = target
        row.version += 1
        session.commit()
        return True
    except Exception:
        session.rollback()
        raise
