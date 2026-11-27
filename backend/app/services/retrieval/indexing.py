"""Short database transactions around slow, retryable embedding work."""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, or_, select, update

from app.db.models import InformationRecord, RetrievalChunk, RetrievalState
from app.services.retrieval.chunks import split_record
from app.services.retrieval.embeddings import EmbeddingClient, EmbeddingError, validate_vector

logger = logging.getLogger(__name__)


def rebuild(factory) -> int:
    """Invalidate all indexed generations; an in-flight old worker cannot restore them."""
    with factory.begin() as session:
        result = session.execute(
            update(RetrievalState).values(
                revision=RetrievalState.revision + 1, attempts=0, retry_at=None, last_error=None
            )
        )
        return result.rowcount


def process_batch(factory, settings, *, client=None, batch_size=50, now=None) -> dict:
    if not 1 <= batch_size <= 1000:
        raise ValueError("batch_size must be between 1 and 1000")
    clock = now
    now = now or datetime.now(UTC)
    client = client or EmbeddingClient(settings)
    with factory() as session:
        identities = list(
            session.scalars(
                select(RetrievalState.information_id)
                .where(
                    or_(
                        RetrievalState.indexed_revision.is_(None),
                        RetrievalState.indexed_revision != RetrievalState.revision,
                        RetrievalState.profile.is_(None),
                        RetrievalState.profile != settings.profile,
                    ),
                    or_(RetrievalState.retry_at.is_(None), RetrievalState.retry_at <= now),
                )
                .order_by(RetrievalState.information_id)
                .limit(batch_size)
            )
        )
    counts = {"selected": len(identities), "indexed": 0, "failed": 0, "superseded": 0}
    for identity in identities:
        with factory() as session:
            snapshot = session.execute(
                select(InformationRecord, RetrievalState.revision)
                .join(RetrievalState, RetrievalState.information_id == InformationRecord.id)
                .where(InformationRecord.id == identity)
            ).first()
            if snapshot is None:
                counts["superseded"] += 1
                continue
            record, revision = snapshot
            chunks = split_record(record, settings)
        # No transaction or row lock is held during network/model work.
        try:
            vectors = []
            for offset in range(0, len(chunks), 16):
                group = chunks[offset : offset + 16]
                encoded = client.encode([chunk.text for chunk in group])
                if len(encoded) != len(group):
                    raise EmbeddingError("embedding_response_count")
                vectors.extend(validate_vector(v, settings.dimensions) for v in encoded)
            error = None
        except EmbeddingError as exc:
            error = str(exc)
        with factory.begin() as session:
            # Match the lock order of the information write + invalidation trigger.
            exists = session.scalar(
                select(InformationRecord.id)
                .where(InformationRecord.id == identity)
                .with_for_update()
            )
            state = session.scalar(
                select(RetrievalState)
                .where(RetrievalState.information_id == identity)
                .with_for_update()
            )
            if (
                exists is None
                or state is None
                or state.revision != revision
                or (state.indexed_revision == revision and state.profile == settings.profile)
            ):
                counts["superseded"] += 1
                continue
            if error:
                state.attempts += 1
                state.last_error = error[:64]
                state.retry_at = (clock or datetime.now(UTC)) + timedelta(
                    seconds=min(300, 2 ** min(state.attempts, 9))
                )
                counts["failed"] += 1
                logger.warning("retrieval_index_failed id=%s code=%s", identity, error)
                continue
            session.execute(delete(RetrievalChunk).where(RetrievalChunk.information_id == identity))
            session.add_all(
                RetrievalChunk(
                    information_id=identity,
                    ordinal=chunk.ordinal,
                    revision=revision,
                    profile=settings.profile,
                    start=chunk.start,
                    end=chunk.end,
                    body=chunk.body,
                    embedding=vector,
                )
                for chunk, vector in zip(chunks, vectors, strict=True)
            )
            state.indexed_revision = revision
            state.profile = settings.profile
            state.attempts = 0
            state.last_error = None
            state.retry_at = None
            counts["indexed"] += 1
    return counts
