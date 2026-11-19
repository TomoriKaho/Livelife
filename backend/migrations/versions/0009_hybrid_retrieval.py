"""Versioned retrieval chunks and transactional indexing invalidation."""

import sqlalchemy as sa
from alembic import op

revision = "0009_hybrid_retrieval"
down_revision = "0008_merge_history_favorites"
branch_labels = None
depends_on = None


class Vector(sa.types.UserDefinedType):
    def get_col_spec(self, **kw):
        return "VECTOR"


def upgrade():
    postgres = op.get_bind().dialect.name == "postgresql"
    if postgres:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "information_retrieval_state",
        sa.Column("information_id", sa.Uuid(), primary_key=True),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("indexed_revision", sa.BigInteger()),
        sa.Column("profile", sa.String(64)),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("retry_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.String(64)),
        sa.ForeignKeyConstraint(["information_id"], ["information_items.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_retrieval_retry", "information_retrieval_state", ["retry_at", "information_id"]
    )
    op.create_table(
        "information_retrieval_chunks",
        sa.Column("information_id", sa.Uuid(), primary_key=True),
        sa.Column("ordinal", sa.Integer(), primary_key=True),
        sa.Column("revision", sa.BigInteger(), nullable=False),
        sa.Column("profile", sa.String(64), nullable=False),
        sa.Column("start", sa.Integer(), nullable=False),
        sa.Column("end", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("embedding", Vector() if postgres else sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["information_id"], ["information_items.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_retrieval_profile", "information_retrieval_chunks", ["profile", "information_id"]
    )
    # Backfill existing records. Subsequent writes are captured even through SQL,
    # bulk imports or a process that has not yet been upgraded to the new worker.
    op.execute(
        "INSERT INTO information_retrieval_state (information_id) SELECT id FROM information_items"
    )
    invalidate = """
        INSERT INTO information_retrieval_state (information_id) VALUES (NEW.id)
        ON CONFLICT (information_id) DO UPDATE SET
          revision = information_retrieval_state.revision + 1,
          attempts = 0, retry_at = NULL, last_error = NULL;
    """
    cleanup = """
        DELETE FROM information_retrieval_chunks WHERE information_id = OLD.id;
        DELETE FROM information_retrieval_state WHERE information_id = OLD.id;
    """
    if postgres:
        op.execute(
            "CREATE FUNCTION livelife_retrieval_changed() RETURNS trigger LANGUAGE plpgsql AS $$ "
            "BEGIN IF TG_OP = 'DELETE' THEN "
            + cleanup
            + " RETURN OLD; END IF; "
            + invalidate
            + " RETURN NEW; END $$"
        )
        op.execute(
            "CREATE TRIGGER information_retrieval_changed AFTER INSERT OR UPDATE OR DELETE "
            "ON information_items FOR EACH ROW EXECUTE FUNCTION livelife_retrieval_changed()"
        )
    else:
        for event in ("INSERT", "UPDATE", "DELETE"):
            body = cleanup if event == "DELETE" else invalidate
            op.execute(
                f"CREATE TRIGGER information_retrieval_{event.lower()} AFTER {event} "
                f"ON information_items BEGIN {body} END"
            )


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER information_retrieval_changed ON information_items")
        op.execute("DROP FUNCTION livelife_retrieval_changed()")
    else:
        for event in ("insert", "update", "delete"):
            op.execute(f"DROP TRIGGER information_retrieval_{event}")
    op.drop_table("information_retrieval_chunks")
    op.drop_table("information_retrieval_state")
    # vector may be shared by other tables; never drop the extension here.
