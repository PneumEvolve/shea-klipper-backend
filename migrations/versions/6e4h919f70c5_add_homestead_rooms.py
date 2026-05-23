"""add homestead_rooms

Revision ID: 6e4h919f70c5
Revises: 5d3g808e69b4
Create Date: 2026-05-22 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '6e4h919f70c5'
down_revision: Union[str, None] = '5d3g808e69b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'homestead_rooms',
        sa.Column('id',                sa.Integer(),               nullable=False),
        sa.Column('join_code',         sa.String(8),               nullable=False),
        sa.Column('player1_id',        sa.Integer(),               nullable=True),
        sa.Column('player2_id',        sa.Integer(),               nullable=True),
        sa.Column('status',            sa.String(16),              nullable=False, server_default='waiting'),
        sa.Column('chest_inventory',   sa.JSON(),                  nullable=False, server_default='{}'),
        sa.Column('placed_objects',    sa.JSON(),                  nullable=False, server_default='[]'),
        sa.Column('created_at',        sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at',        sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['player1_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['player2_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_homestead_rooms_id',        'homestead_rooms', ['id'],        unique=False)
    op.create_index('ix_homestead_rooms_join_code', 'homestead_rooms', ['join_code'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_homestead_rooms_join_code', table_name='homestead_rooms')
    op.drop_index('ix_homestead_rooms_id',        table_name='homestead_rooms')
    op.drop_table('homestead_rooms')