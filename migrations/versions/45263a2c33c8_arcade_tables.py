"""arcade tables

Revision ID: 45263a2c33c8
Revises: 31bbad557aa9
Create Date: 2026-11-23 13:23:17.088438

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '45263a2c33c8'
down_revision: Union[str, None] = '31bbad557aa9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.create_table(
        "arcade_rooms",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("game_id", sa.String(32), nullable=False),
        sa.Column("join_code", sa.String(8), nullable=False),
        sa.Column("player1_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("player2_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="waiting"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_arcade_rooms_id", "arcade_rooms", ["id"])
    op.create_index("ix_arcade_rooms_game_id", "arcade_rooms", ["game_id"])
    op.create_index("ix_arcade_rooms_join_code", "arcade_rooms", ["join_code"])

    op.create_table(
        "arcade_saves",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("game_id", sa.String(32), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "game_id", name="uq_arcade_save_user_game"),
    )
    op.create_index("ix_arcade_saves_id", "arcade_saves", ["id"])
    op.create_index("ix_arcade_saves_user_id", "arcade_saves", ["user_id"])


def downgrade():
    op.drop_table("arcade_saves")
    op.drop_table("arcade_rooms")