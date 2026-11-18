"""Account feedback and processing audit, removed together on account deletion."""

import sqlalchemy as sa
from alembic import op

revision = "0011_user_feedback"
down_revision = "0010_processing_diagnostics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_feedback",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("client_request_id", sa.Uuid(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.UniqueConstraint("user_id", "client_request_id", name="uq_feedback_owner_request"),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'resolved', 'closed')",
            name="ck_feedback_status",
        ),
    )
    op.create_index("ix_feedback_owner_submitted", "user_feedback", ["user_id", "submitted_at"])
    op.create_index(
        "ix_feedback_status_submitted", "user_feedback", ["status", "submitted_at", "id"]
    )
    op.create_table(
        "feedback_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "feedback_id",
            sa.Uuid(),
            sa.ForeignKey("user_feedback.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor", sa.String(100), nullable=False),
        sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("from_status", sa.String(16), nullable=False),
        sa.Column("to_status", sa.String(16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
    )
    op.create_index("ix_feedback_events_feedback", "feedback_events", ["feedback_id", "version"])


def downgrade() -> None:
    op.drop_table("feedback_events")
    op.drop_table("user_feedback")
