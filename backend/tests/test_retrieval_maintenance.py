from dataclasses import replace

import pytest
from sqlalchemy import delete, select
from test_hybrid_retrieval import FakeEncoder, corpus
from test_hybrid_retrieval import database as database

from app.db.models import RetrievalChunk, RetrievalState
from app.services.retrieval.config import RetrievalSettings
from app.services.retrieval.indexing import process_batch
from app.services.retrieval.maintenance import check, reconcile, status


def test_copy_repair_preserves_existing_versions_and_reports_missing_rows(database):
    corpus(database)
    settings = RetrievalSettings(mode="hybrid", dimensions=3)
    process_batch(database, settings, client=FakeEncoder())
    with database.begin() as session:
        states = list(session.scalars(select(RetrievalState)))
        keep, missing = states[0].information_id, states[1].information_id
        session.get(RetrievalState, keep).revision = 7
        session.execute(delete(RetrievalState).where(RetrievalState.information_id == missing))
    before = status(database, settings)
    assert before["records"] == before["states"] + 1
    assert before["missing_states"] == 1
    assert reconcile(database) == 1
    assert reconcile(database) == 0
    with database() as session:
        assert session.get(RetrievalState, keep).revision == 7
        assert session.get(RetrievalState, missing).indexed_revision is None
    assert status(database, settings)["pending"] == 2
    process_batch(database, settings, client=FakeEncoder())
    assert status(database, settings)["pending"] == 0


def test_readiness_requires_model_vector_query_and_complete_coverage(database):
    if database.kw["bind"].dialect.name != "postgresql":
        pytest.skip("native pgvector readiness requires PostgreSQL")
    settings = RetrievalSettings(mode="hybrid", dimensions=3)
    assert check(database, settings, client=FakeEncoder())["ready"]
    corpus(database)
    assert not check(database, settings, client=FakeEncoder())["ready"]
    process_batch(database, settings, client=FakeEncoder())
    assert check(database, settings, client=FakeEncoder())["ready"]
    assert not check(database, replace(settings, model_revision="new"), client=FakeEncoder())[
        "ready"
    ]
    with database.begin() as session:
        session.execute(delete(RetrievalChunk))
    result = check(database, settings, client=FakeEncoder())
    assert not result["ready"]
    assert result["missing_chunks"] == result["records"]
    with pytest.raises(RuntimeError, match="embedding_unavailable"):
        check(database, settings, client=FakeEncoder(failure=True))
