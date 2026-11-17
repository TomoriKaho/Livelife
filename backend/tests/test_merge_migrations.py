"""Upgrade either development branch without losing its already-persisted data."""

from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from test_agent import settings
from test_favorites import account, activity

from app.db.models import ActivityFavorite, AgentSession, AgentUserUsage, User
from app.db.session import Database
from app.services.agent.service import create_session, get_conversation, pin_session
from app.services.favorites.service import save_favorite

BACKEND = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("start", ["0006_activity_favorites", "0007_agent_pins"])
def test_upgrade_from_either_branch_preserves_data(tmp_path, start):
    db = Database(f"sqlite+pysqlite:///{(tmp_path / 'merge.db').as_posix()}")
    config = Config(str(BACKEND / "alembic.ini"))
    try:
        with db.engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, start)
        owner, _ = account(db)
        target = activity(db)
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
                assert MigrationContext.configure(connection).get_current_heads() == (
                    "0008_merge_history_favorites",
                )
        assert ScriptDirectory.from_config(config).get_heads() == ["0008_merge_history_favorites"]
        with db.session_factory() as session:
            assert session.get(User, owner) is not None
            if sid:
                row = session.get(AgentSession, sid)
                assert row.is_pinned and row.messages[0]["content"] == "保留已有对话"
                assert session.get(AgentUserUsage, owner).tokens_used == 23
            else:
                assert session.get(ActivityFavorite, (owner, target)) is not None
    finally:
        db.close()
