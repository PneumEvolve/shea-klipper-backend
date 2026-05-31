"""deadmiles: create deadmiles_rooms table

Revision ID: ah8l353j14g9
Revises: 9h7k242i03f8
Create Date: 2026-05-30 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'ah8l353j14g9'
down_revision: Union[str, None] = '9h7k242i03f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'deadmiles_rooms',
        sa.Column('id',          sa.Integer(),                  nullable=False),
        sa.Column('join_code',   sa.String(8),                  nullable=False),
        sa.Column('player1_id',  sa.Integer(),                  nullable=True),
        sa.Column('player2_id',  sa.Integer(),                  nullable=True),
        sa.Column('status',      sa.String(16),                 nullable=False, server_default='waiting'),
        sa.Column('map_seed',    sa.Integer(),                  nullable=False),
        sa.Column('final_score', sa.JSON(),                     nullable=True),
        sa.Column('created_at',  sa.DateTime(timezone=True),    nullable=False, server_default=sa.text('now()')),
        sa.Column('ended_at',    sa.DateTime(timezone=True),    nullable=True),
        sa.ForeignKeyConstraint(['player1_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['player2_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_deadmiles_rooms_id',        'deadmiles_rooms', ['id'],        unique=False)
    op.create_index('ix_deadmiles_rooms_join_code', 'deadmiles_rooms', ['join_code'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_deadmiles_rooms_join_code', table_name='deadmiles_rooms')
    op.drop_index('ix_deadmiles_rooms_id',        table_name='deadmiles_rooms')
    op.drop_table('deadmiles_rooms')