"""Create the shared information store."""

import sqlalchemy as sa
from alembic import op

revision = "0001_information"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "information_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("platform", sa.String(64), nullable=False),
        sa.Column("source_id", sa.String(255), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("raw_content", sa.Text(), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("first_fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activity_location", sa.String(500), nullable=True),
        sa.Column("activity_start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activity_end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("registration_deadline_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("platform", "source_id", name="uq_information_source"),
        sa.CheckConstraint(
            "activity_end_at IS NULL OR activity_start_at IS NULL "
            "OR activity_end_at > activity_start_at",
            name="ck_information_activity_interval",
        ),
    )
    op.create_index("ix_information_fetched", "information_items", ["fetched_at", "id"])
    op.create_index(
        "ix_information_platform_fetched", "information_items", ["platform", "fetched_at", "id"]
    )
    op.create_index(
        "ix_information_activity", "information_items", ["activity_start_at", "activity_end_at"]
    )


def downgrade() -> None:
    op.drop_table("information_items")
