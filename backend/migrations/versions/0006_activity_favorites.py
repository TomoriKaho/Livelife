"""Add account activity favorites, retaining minimal source identification."""

import sqlalchemy as sa
from alembic import op

revision = "0006_activity_favorites"
down_revision = "0003_place_resolution"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "activity_favorites",
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("information_id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("title", sa.String(500)),
        sa.Column("platform", sa.String(64), nullable=False),
        sa.Column("source_name", sa.String(500)),
        sa.Column("source_url", sa.Text()),
        sa.Column("activity_date", sa.Date()),
        sa.Column("start_at", sa.DateTime(timezone=True)),
        sa.Column("end_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_favorites_owner_created",
        "activity_favorites",
        ["user_id", "created_at", "information_id"],
    )


def downgrade() -> None:
    op.drop_table("activity_favorites")
