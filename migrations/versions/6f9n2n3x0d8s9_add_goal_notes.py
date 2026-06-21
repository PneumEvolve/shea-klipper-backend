"""add notes column to goals

Revision ID: add_goal_notes
Revises: <fill in with your current head revision>
Create Date: 2026-06-21
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "add_goal_notes"
down_revision = 'b3e1c9f4a821' # <-- set this to your current head before running
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("goals", sa.Column("notes", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("goals", "notes")