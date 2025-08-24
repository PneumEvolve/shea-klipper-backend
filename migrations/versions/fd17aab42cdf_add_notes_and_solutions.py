"""Add Notes and Solutions

Revision ID: fd17aab42cdf
Revises: 68c2c5117903
Create Date: 2025-08-23 11:56:35.692313

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'fd17aab42cdf'
down_revision: Union[str, None] = '68c2c5117903'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.create_table(
        "problem_notes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("problem_id", sa.Integer, sa.ForeignKey("problems.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("author_user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    

    op.create_table(
        "solution_notes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("solution_id", sa.Integer, sa.ForeignKey("solutions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("author_user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    

    # optional denorm counts
    if not has_column("problems", "notes_count"):
        op.add_column("problems", sa.Column("notes_count", sa.Integer(), nullable=False, server_default=sa.text("0")))
    if not has_column("solutions", "notes_count"):
        op.add_column("solutions", sa.Column("notes_count", sa.Integer(), nullable=False, server_default=sa.text("0")))

    # feature toggle + score for Solutions in Forge
    if not has_column("solutions", "featured_in_forge"):
        op.add_column("solutions", sa.Column("featured_in_forge", sa.Boolean(), nullable=False, server_default=sa.text("false")))
        op.create_index("ix_solutions_featured_in_forge", "solutions", ["featured_in_forge"])
    if not has_column("solutions", "impact_score"):
        op.add_column("solutions", sa.Column("impact_score", sa.Float(), nullable=False, server_default=sa.text("0")))

def downgrade():
    # drop added columns
    if has_column("solutions", "impact_score"):
        op.drop_column("solutions", "impact_score")
    if has_column("solutions", "featured_in_forge"):
        op.drop_index("ix_solutions_featured_in_forge", table_name="solutions")
        op.drop_column("solutions", "featured_in_forge")
    if has_column("solutions", "notes_count"):
        op.drop_column("solutions", "notes_count")
    if has_column("problems", "notes_count"):
        op.drop_column("problems", "notes_count")

    # drop tables
    op.drop_index("ix_solution_notes_created_at", table_name="solution_notes")
    op.drop_index("ix_solution_notes_solution_id", table_name="solution_notes")
    op.drop_table("solution_notes")

    op.drop_index("ix_problem_notes_created_at", table_name="problem_notes")
    op.drop_index("ix_problem_notes_problem_id", table_name="problem_notes")
    op.drop_table("problem_notes")


# ---- helpers (optional if you like defensive migrations) ----
from sqlalchemy import inspect
def has_column(table, column):
    bind = op.get_bind()
    insp = inspect(bind)
    cols = [c["name"] for c in insp.get_columns(table)]
    return column in cols