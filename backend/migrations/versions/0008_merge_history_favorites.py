"""Merge independent favorites and permanent Agent history migrations.

Keep previously applied revisions unchanged. The merge itself changes no data.
"""

revision = "0008_merge_history_favorites"
down_revision = ("0006_activity_favorites", "0007_agent_pins")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
