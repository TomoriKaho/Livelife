"""Replace disposable development transcripts with permanent account history.

Destructive once by development-data policy. Downgrade cannot recover history.
"""

import sqlalchemy as sa
from alembic import op

revision = "0006_agent_history"
down_revision = "0003_place_resolution"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "UPDATE agent_user_usage SET tokens_used = tokens_used + tokens_reserved, "
        "tokens_reserved = 0, active_request_id = NULL, active_request_expires_at = NULL"
    )
    op.execute("DELETE FROM agent_sessions")
    with op.batch_alter_table("agent_sessions") as batch:
        batch.alter_column("expires_at", existing_type=sa.DateTime(timezone=True), nullable=True)
        batch.add_column(
            sa.Column("title", sa.String(100), nullable=False, server_default="新的对话")
        )
        batch.create_index("ix_agent_owner_updated", ["user_id", "last_seen_at", "id"])
    op.create_table(
        "agent_messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "session_id",
            sa.Uuid(),
            sa.ForeignKey("agent_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    op.create_index(
        "ix_agent_message_order", "agent_messages", ["session_id", "sequence"], unique=True
    )


def downgrade():
    op.drop_table("agent_messages")
    op.execute("DELETE FROM agent_sessions")
    with op.batch_alter_table("agent_sessions") as batch:
        batch.drop_index("ix_agent_owner_updated")
        batch.drop_column("title")
        batch.alter_column("expires_at", existing_type=sa.DateTime(timezone=True), nullable=False)
