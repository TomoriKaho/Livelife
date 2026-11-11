"""Bind new Agent sessions and shared usage to accounts; leave legacy sessions unowned."""

import sqlalchemy as sa
from alembic import op

revision = "0005_agent_account_auth"
down_revision = "0004_profiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("agent_sessions") as batch:
        batch.add_column(sa.Column("user_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            "fk_agent_session_user", "users", ["user_id"], ["id"], ondelete="CASCADE"
        )
        batch.create_index("ix_agent_sessions_user_id", ["user_id"])
    op.create_table(
        "agent_user_usage",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("request_window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.Column("active_request_id", sa.String(36)),
        sa.Column("active_request_expires_at", sa.DateTime(timezone=True)),
        sa.Column("usage_day", sa.Date(), nullable=False),
        sa.Column("tokens_used", sa.Integer(), nullable=False),
        sa.Column("tokens_reserved", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("agent_user_usage")
    with op.batch_alter_table("agent_sessions") as batch:
        batch.drop_index("ix_agent_sessions_user_id")
        batch.drop_constraint("fk_agent_session_user", type_="foreignkey")
        batch.drop_column("user_id")
