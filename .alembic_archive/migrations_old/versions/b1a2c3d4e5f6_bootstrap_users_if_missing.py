from alembic import op
import sqlalchemy as sa

revision = "b1a2c3d4e5f6"        # <- any new unique id
down_revision = "805df2c6c1f9"   # <- CRITICAL: sits right after the branchpoint
branch_labels = None
depends_on = None

def upgrade():
    conn = op.get_bind()
    has_users = conn.execute(sa.text("select to_regclass('public.users')")).scalar()
    if not has_users:
        op.create_table(
            "users",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("email", sa.String, unique=True, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        )

def downgrade():
    # Keep no-op to avoid dropping real data if this ever ran in a real env
    pass