"""Add short-lived Agent conversations and IP request windows."""

import sqlalchemy as sa
from alembic import op

revision = "0002_agent_sessions"
down_revision = "0001_information"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("messages", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.Column("active_request_id", sa.String(36), nullable=True),
        sa.Column("active_request_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("usage_day", sa.Date(), nullable=False),
        sa.Column("tokens_used", sa.Integer(), nullable=False),
        sa.Column("tokens_reserved", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_agent_session_expires", "agent_sessions", ["expires_at"])
    op.create_table(
        "agent_ip_windows",
        sa.Column("ip_hash", sa.String(64), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("ip_hash"),
    )


def downgrade() -> None:
    op.drop_table("agent_ip_windows")
    op.drop_index("ix_agent_session_expires", table_name="agent_sessions")
    op.drop_table("agent_sessions")
