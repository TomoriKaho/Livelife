"""Add isolated system extraction jobs, attempts and a bounded execution lease."""

import sqlalchemy as sa
from alembic import op

revision = "0009_information_processing"
down_revision = "0008_merge_history_favorites"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "information_processing_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("key", sa.String(64), nullable=False, unique=True),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("version", sa.String(100), nullable=False),
        sa.Column("model", sa.String(200), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("source", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error", sa.String(100), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("review", sa.JSON(), nullable=True),
    )
    op.create_table(
        "information_processing_attempts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reserved_tokens", sa.Integer(), nullable=False),
        sa.Column("usage", sa.JSON(), nullable=True),
        sa.Column("error", sa.String(100), nullable=True),
    )
    op.create_index(
        "ix_information_processing_attempts_job_id", "information_processing_attempts", ["job_id"]
    )
    op.create_index(
        "ix_information_processing_attempts_started_at",
        "information_processing_attempts",
        ["started_at"],
    )
    table = op.create_table(
        "information_processing_gate",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner", sa.Uuid(), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=False),
    )
    from datetime import UTC, datetime

    op.bulk_insert(
        table, [{"id": 1, "owner": None, "lease_until": datetime(2000, 1, 1, tzinfo=UTC)}]
    )


def downgrade():
    op.drop_table("information_processing_gate")
    op.drop_table("information_processing_attempts")
    op.drop_table("information_processing_jobs")
