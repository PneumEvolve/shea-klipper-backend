"""add skipped_breathing to cc_cravings

Revision ID: add_skipped_breathing
Revises: add_clear_and_calm
Branch_labels: None
Depends_on: None
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_skipped_breathing'
down_revision = 'add_clear_and_calm'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "cc_cravings",
        sa.Column(
            "skipped_breathing",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade():
    op.drop_column("cc_cravings", "skipped_breathing")