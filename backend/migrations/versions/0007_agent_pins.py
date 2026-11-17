"""Persist account conversation pin state without changing transcripts."""

import sqlalchemy as sa
from alembic import op

revision = "0007_agent_pins"
down_revision = "0006_agent_history"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "agent_sessions",
        sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade():
    op.drop_column("agent_sessions", "is_pinned")
