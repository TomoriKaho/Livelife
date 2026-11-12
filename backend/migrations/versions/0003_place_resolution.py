"""Add place aliases and auditable location resolution to the local Demo."""

import sqlalchemy as sa
from alembic import op

revision = "0003_place_resolution"
down_revision = "0002_information_places"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("information_places", sa.Column("building_id", sa.String(100)))
    op.add_column(
        "information_places",
        sa.Column("campus", sa.String(100), nullable=False, server_default="北京大学燕园"),
    )
    # Earlier Demo IDs came from map buildings. Keep existing IDs and references stable.
    op.execute("UPDATE information_places SET building_id = id")
    op.create_index("ix_information_places_building_id", "information_places", ["building_id"])
    op.create_table(
        "information_place_aliases",
        sa.Column(
            "place_id", sa.String(100), sa.ForeignKey("information_places.id"), primary_key=True
        ),
        sa.Column("alias", sa.String(500), primary_key=True),
    )
    op.add_column("information_items", sa.Column("location_resolution", sa.JSON()))


def downgrade() -> None:
    op.drop_column("information_items", "location_resolution")
    op.drop_table("information_place_aliases")
    op.drop_index("ix_information_places_building_id", table_name="information_places")
    op.drop_column("information_places", "building_id")
    op.drop_column("information_places", "campus")
