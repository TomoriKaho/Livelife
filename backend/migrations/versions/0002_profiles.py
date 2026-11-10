"""Create user profiles and interest tags."""

import sqlalchemy as sa
from alembic import op

revision = "0002_profiles"
# #65（PR #68）合入 main 后：该分支已含 0002_accounts 与 0002_agent_sessions，
# 再由 0003_merge_account_agent 合并两条 head。届时把本文件与 revision 改名为
# 0004_profiles，并将 down_revision 改为 "0003_merge_account_agent"，避免第三个 head。
down_revision = "0001_information"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_profiles",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.String(32), nullable=False),
        sa.Column("bio", sa.String(200), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_table(
        "user_interests",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("tag", sa.String(32), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "tag"),
    )


def downgrade() -> None:
    op.drop_table("user_interests")
    op.drop_table("user_profiles")
