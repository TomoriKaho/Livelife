"""Merge the account and Agent session migration branches."""

revision = "0003_merge_account_agent"
down_revision = ("0002_accounts", "0002_agent_sessions")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
