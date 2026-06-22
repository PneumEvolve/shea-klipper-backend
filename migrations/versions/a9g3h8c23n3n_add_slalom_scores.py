"""add slalom_scores table for leaderboard

Revision ID: add_slalom_scores
Revises: add_goal_notes
Create Date: 2026-06-22
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "add_slalom_scores"
down_revision = "add_goal_notes"  # <-- confirm this is still your current head before running
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "slalom_scores",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("mode", sa.String(length=8), nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=True),
        sa.Column("player1_id", sa.Integer(), nullable=True),
        sa.Column("player1_name", sa.String(length=32), nullable=False),
        sa.Column("player2_id", sa.Integer(), nullable=True),
        sa.Column("player2_name", sa.String(length=32), nullable=True),
        sa.Column("gates_passed", sa.Integer(), nullable=False),
        sa.Column("gems", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["room_id"], ["slalom_rooms.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["player1_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["player2_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(op.f("ix_slalom_scores_id"), "slalom_scores", ["id"])
    op.create_index(
        "ix_slalom_scores_rank",
        "slalom_scores",
        ["mode", "gates_passed", "gems"],
    )


def downgrade() -> None:
    op.drop_index("ix_slalom_scores_rank", table_name="slalom_scores")
    op.drop_index(op.f("ix_slalom_scores_id"), table_name="slalom_scores")
    op.drop_table("slalom_scores")