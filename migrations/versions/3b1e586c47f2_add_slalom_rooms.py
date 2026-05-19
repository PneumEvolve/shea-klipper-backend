"""add slalom_rooms

Revision ID: 3b1e586c47f2
Revises: add_firefly_rooms
Create Date: 2026-05-19 11:30:28.298390

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '3b1e586c47f2'
down_revision: Union[str, None] = 'add_firefly_rooms'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'slalom_rooms',
        sa.Column('id',         sa.Integer(),                  nullable=False),
        sa.Column('join_code',  sa.String(8),                  nullable=False),
        sa.Column('player1_id', sa.Integer(),                  nullable=True),
        sa.Column('player2_id', sa.Integer(),                  nullable=True),
        sa.Column('status',     sa.String(16),                 nullable=False, server_default='waiting'),
        sa.Column('final_gems', sa.Integer(),                  nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),    nullable=False, server_default=sa.text('now()')),
        sa.Column('ended_at',   sa.DateTime(timezone=True),    nullable=True),
        sa.ForeignKeyConstraint(['player1_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['player2_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_slalom_rooms_id',        'slalom_rooms', ['id'],        unique=False)
    op.create_index('ix_slalom_rooms_join_code', 'slalom_rooms', ['join_code'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_slalom_rooms_join_code', table_name='slalom_rooms')
    op.drop_index('ix_slalom_rooms_id',        table_name='slalom_rooms')
    op.drop_table('slalom_rooms')