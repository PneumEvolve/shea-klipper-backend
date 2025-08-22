from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "c9febb209ee6"
down_revision = "5f960c82dd6c"  # <- whatever your current head is
branch_labels = None
depends_on = None

def upgrade():
    # normalize existing data (safe even if none are NULL)
    op.execute("UPDATE public.users SET accepted_terms = FALSE WHERE accepted_terms IS NULL;")
    # set default + enforce NOT NULL
    op.alter_column(
        "users", "accepted_terms",
        existing_type=sa.Boolean(),
        nullable=False,
        server_default=sa.text("false"),
    )

def downgrade():
    # drop the default; keep NOT NULL (or relax if you prefer)
    op.alter_column(
        "users", "accepted_terms",
        existing_type=sa.Boolean(),
        nullable=False,
        server_default=None,
    )