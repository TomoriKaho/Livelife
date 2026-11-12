"""Add map places, publisher names and date-only activity evidence."""

import sqlalchemy as sa
from alembic import op

revision = "0002_information_places"
down_revision = "0005_agent_account_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "information_places",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_place_longitude"),
        sa.CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_place_latitude"),
    )
    op.create_index("ix_information_places_latitude", "information_places", ["latitude"])
    with op.batch_alter_table("information_items") as batch:
        batch.add_column(sa.Column("source_name", sa.String(500), nullable=True))
        batch.add_column(sa.Column("place_id", sa.String(100), nullable=True))
        batch.add_column(sa.Column("activity_date", sa.Date(), nullable=True))
        batch.create_foreign_key("fk_information_place", "information_places", ["place_id"], ["id"])
        batch.create_index("ix_information_place", ["place_id"])


def downgrade() -> None:
    with op.batch_alter_table("information_items") as batch:
        batch.drop_index("ix_information_place")
        batch.drop_constraint("fk_information_place", type_="foreignkey")
        batch.drop_column("place_id")
        batch.drop_column("source_name")
        batch.drop_column("activity_date")
    op.drop_table("information_places")
