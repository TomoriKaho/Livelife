"""Index coverage and deployment probes; never return document text or credentials."""

import json

from sqlalchemy import Float, cast, exists, func, literal, or_, select

from app.db.models import InformationRecord, RetrievalChunk, RetrievalState
from app.db.vector import Vector
from app.services.retrieval.embeddings import EmbeddingClient, EmbeddingError


def reconcile(factory) -> int:
    """Restore missing outbox rows after a public-only database snapshot."""
    with factory.begin() as session:
        if session.bind.dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert
        else:
            from sqlalchemy.dialects.sqlite import insert
        statement = (
            insert(RetrievalState)
            .from_select(
                ["information_id"],
                select(InformationRecord.id).where(
                    ~exists().where(RetrievalState.information_id == InformationRecord.id)
                ),
                include_defaults=False,
            )
            .on_conflict_do_nothing(index_elements=["information_id"])
        )
        return sum(1 for _ in session.execute(statement.returning(RetrievalState.information_id)))


def status(factory, settings) -> dict:
    s, c, r = RetrievalState, RetrievalChunk, InformationRecord
    with factory() as session:
        stale = or_(
            s.indexed_revision.is_(None),
            s.indexed_revision != s.revision,
            s.profile.is_(None),
            s.profile != settings.profile,
        )
        valid_chunk = exists().where(
            c.information_id == r.id, c.revision == s.revision, c.profile == settings.profile
        )
        missing_chunks = (
            select(func.count())
            .select_from(r)
            .join(s)
            .where(~stale, func.length(func.trim(r.content)) > 0, ~valid_chunk)
        )
        return {
            "profile": settings.profile,
            "records": session.scalar(select(func.count()).select_from(r)),
            "states": session.scalar(select(func.count()).select_from(s)),
            "missing_states": session.scalar(
                select(func.count()).select_from(r).where(~exists().where(s.information_id == r.id))
            ),
            "pending": session.scalar(select(func.count()).select_from(s).where(stale)),
            "failed": session.scalar(
                select(func.count()).select_from(s).where(s.last_error.is_not(None))
            ),
            "chunks": session.scalar(select(func.count()).select_from(c)),
            "missing_chunks": session.scalar(missing_chunks),
        }


def check(factory, settings, *, client=None) -> dict:
    """Require full coverage and exercise the real model and pgvector operator."""
    if settings.mode != "hybrid":
        raise EmbeddingError("retrieval_not_hybrid")
    # Network work precedes opening the database transaction.
    vector = (client or EmbeddingClient(settings)).encode(["校园公开资料检索"], query=True)[0]
    with factory() as session:
        if session.bind.dialect.name != "postgresql":
            raise EmbeddingError("vector_requires_postgresql")
        value = cast(literal(json.dumps(vector, allow_nan=False)), Vector())
        distance = session.scalar(select(value.op("<=>", return_type=Float)(value)))
        if distance is None or abs(distance) > 1e-5:
            raise EmbeddingError("vector_probe_failed")
        # Also exercise stored vectors, including their dimensions. Empty databases
        # still run the operator probe and explicitly report records=0.
        session.execute(
            select(RetrievalChunk.embedding.op("<=>", return_type=Float)(value))
            .where(RetrievalChunk.profile == settings.profile)
            .limit(1)
        ).all()
    result = status(factory, settings)
    result["ready"] = not any(
        result[k] for k in ("missing_states", "pending", "failed", "missing_chunks")
    )
    result["model_query"] = result["vector_query"] = True
    return result
