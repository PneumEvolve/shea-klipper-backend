from alembic import op
import sqlalchemy as sa

revision = "9a1b2c3d4e56"
# Pick a parent that already exists in your graph. Any current head is fine.
# If unsure, use the most recent head printed by `alembic heads` (e.g. "54e74999f5a5").
down_revision = "54e74999f5a5"

branch_labels = None
depends_on = None

def _col_missing(table: str, col: str) -> bool:
    conn = op.get_bind()
    return conn.execute(sa.text("""
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name=:t AND column_name=:c
    """), {"t": table, "c": col}).scalar() is None

def upgrade():
    # Make these changes only if columns are missing (safe for repeated runs).
    if _col_missing("users", "hashed_password"):
        op.add_column("users", sa.Column("hashed_password", sa.String(), nullable=True))
    if _col_missing("users", "username"):
        op.add_column("users", sa.Column("username", sa.String(), nullable=True))
    if _col_missing("users", "has_active_payment"):
        op.add_column("users", sa.Column("has_active_payment", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    if _col_missing("users", "api_balance_dollars"):
        op.add_column("users", sa.Column("api_balance_dollars", sa.Numeric(10, 2), nullable=False, server_default="0"))
    if _col_missing("users", "profile_pic"):
        op.add_column("users", sa.Column("profile_pic", sa.String(), nullable=True))

    # If you want to enforce NOT NULL on hashed_password later, do it after you seed users.

def downgrade():
    # Keep downgrade gentle in local bootstrap
    with op.batch_alter_table("users") as b:
        for col in ("profile_pic", "api_balance_dollars", "has_active_payment", "username", "hashed_password"):
            try:
                b.drop_column(col)
            except Exception:
                pass