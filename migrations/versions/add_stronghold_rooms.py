"""add stronghold_rooms

Revision ID: 4c2f697d58a3
Revises: 3b1e586c47f2
Create Date: 2026-05-19 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '4c2f697d58a3'
down_revision: Union[str, None] = '3b1e586c47f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'stronghold_rooms',
        sa.Column('id',          sa.Integer(),               nullable=False),
        sa.Column('join_code',   sa.String(8),               nullable=False),
        sa.Column('player1_id',  sa.Integer(),               nullable=True),
        sa.Column('player2_id',  sa.Integer(),               nullable=True),
        sa.Column('status',      sa.String(16),              nullable=False, server_default='waiting'),
        sa.Column('map_seed',    sa.Integer(),               nullable=False),
        sa.Column('final_score', sa.Integer(),               nullable=True),
        sa.Column('created_at',  sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('ended_at',    sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['player1_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['player2_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_stronghold_rooms_id',        'stronghold_rooms', ['id'],        unique=False)
    op.create_index('ix_stronghold_rooms_join_code', 'stronghold_rooms', ['join_code'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_stronghold_rooms_join_code', table_name='stronghold_rooms')
    op.drop_index('ix_stronghold_rooms_id',        table_name='stronghold_rooms')
    op.drop_table('stronghold_rooms')