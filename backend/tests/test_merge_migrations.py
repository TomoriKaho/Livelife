"""Upgrade either development branch without losing its already-persisted data."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect
from sqlalchemy.engine import make_url
from test_agent import settings
from test_favorites import account, activity

from app.db.models import (
    ActivityFavorite,
    AgentSession,
    AgentUserUsage,
    ProcessingAttempt,
    ProcessingGate,
    ProcessingJob,
    RetrievalChunk,
    RetrievalState,
    User,
)
from app.db.session import Database
from app.services.agent.service import create_session, get_conversation, pin_session
from app.services.favorites.service import save_favorite

BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture(params=["sqlite", "postgresql"])
def database(request, tmp_path):
    if request.param == "postgresql":
        if not request.config.getoption("--local-postgres"):
            pytest.skip("requires --local-postgres")
        from pgembed import get_server

        with get_server(tmp_path / "merge-postgres", cleanup_mode="stop") as server:
            url = make_url(server.get_uri()).set(drivername="postgresql+psycopg")
            db = Database(url.render_as_string(hide_password=False))
            try:
                yield db
            finally:
                db.close()
    else:
        db = Database(f"sqlite+pysqlite:///{(tmp_path / 'merge.db').as_posix()}")
        try:
            yield db
        finally:
            db.close()


@pytest.mark.parametrize(
    "start",
    [
        "0006_activity_favorites",
        "0007_agent_pins",
        "0009_hybrid_retrieval",
        "0010_processing_diagnostics",
    ],
)
def test_upgrade_from_either_branch_preserves_data(database, start):
    db = database
    config = Config(str(BACKEND / "alembic.ini"))
    try:
        with db.engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, start)
        owner, _ = account(db)
        target = activity(db)
        job_id, attempt_id = uuid4(), uuid4()
        diagnostics = {"stage": "validation", "codes": ["missing_time"]}
        if start == "0010_processing_diagnostics":
            assert "information_retrieval_state" not in inspect(db.engine).get_table_names()
            with db.session_factory.begin() as session:
                session.add(
                    ProcessingJob(
                        id=job_id,
                        key="merge-test",
                        content_hash="synthetic",
                        version="v1",
                        model="fixture",
                        status="needs_review",
                        source={"content": "原文"},
                        result={"title": "候选"},
                        attempts=1,
                        created_at=datetime.now(UTC),
                        updated_at=datetime.now(UTC),
                        review={"reason": "待人工核对"},
                    )
                )
                session.add(
                    ProcessingAttempt(
                        id=attempt_id,
                        job_id=job_id,
                        started_at=datetime.now(UTC),
                        reserved_tokens=123,
                        diagnostics=diagnostics,
                    )
                )
        if start == "0009_hybrid_retrieval":
            assert "information_processing_jobs" not in inspect(db.engine).get_table_names()
            with db.session_factory.begin() as session:
                state = session.get(RetrievalState, target)
                state.indexed_revision = state.revision
                state.profile = "merge-test"
                session.add(
                    RetrievalChunk(
                        information_id=target,
                        ordinal=0,
                        revision=state.revision,
                        profile="merge-test",
                        start=0,
                        end=2,
                        body="原文",
                        embedding=[1.0, 0.0],
                    )
                )
        sid = None
        if start == "0006_activity_favorites":
            with db.session_factory() as session:
                save_favorite(session, owner, target)
        else:
            sid = create_session(db.session_factory, settings(), "merge", user_id=owner)[
                "session_id"
            ]
            pin_session(db.session_factory, settings(), sid, user_id=owner, is_pinned=True)
            # Usage is created on conversation access/admission, not session creation.
            get_conversation(db.session_factory, settings(), sid, user_id=owner)
            with db.session_factory.begin() as session:
                row = session.get(AgentSession, sid)
                row.messages = [{"id": str(uuid4()), "role": "user", "content": "保留已有对话"}]
                session.get(AgentUserUsage, owner).tokens_used = 23

        for _ in range(2):
            with db.engine.begin() as connection:
                config.attributes["connection"] = connection
                command.upgrade(config, "head")
                assert set(MigrationContext.configure(connection).get_current_heads()) == set(
                    ScriptDirectory.from_config(config).get_heads()
                )
        assert len(ScriptDirectory.from_config(config).get_heads()) == 1
        with db.session_factory() as session:
            assert session.get(User, owner) is not None
            assert session.get(RetrievalState, target).revision == 1
            assert session.get(ProcessingGate, 1) is not None
            if start == "0010_processing_diagnostics":
                job = session.get(ProcessingJob, job_id)
                assert job.source == {"content": "原文"}
                assert job.result == {"title": "候选"}
                assert job.review == {"reason": "待人工核对"}
                attempt = session.get(ProcessingAttempt, attempt_id)
                assert attempt.diagnostics == diagnostics
                assert attempt.reserved_tokens == 123
            if start == "0009_hybrid_retrieval":
                assert session.get(RetrievalState, target).indexed_revision == 1
                chunk = session.get(RetrievalChunk, (target, 0))
                assert chunk.body == "原文"
                assert chunk.embedding == [1.0, 0.0]
            if sid:
                row = session.get(AgentSession, sid)
                assert row.is_pinned and row.messages[0]["content"] == "保留已有对话"
                assert session.get(AgentUserUsage, owner).tokens_used == 23
            else:
                assert session.get(ActivityFavorite, (owner, target)) is not None
    finally:
        db.close()
