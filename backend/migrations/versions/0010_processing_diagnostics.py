"""Retain per-attempt extraction diagnostics across retries."""

import sqlalchemy as sa
from alembic import op

revision = "0010_processing_diagnostics"
down_revision = "0009_information_processing"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "information_processing_attempts", sa.Column("diagnostics", sa.JSON(), nullable=True)
    )


def downgrade():
    op.drop_column("information_processing_attempts", "diagnostics")
