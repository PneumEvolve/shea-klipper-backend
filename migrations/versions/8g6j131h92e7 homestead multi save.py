"""homestead multi-save: add name, last_played_at to rooms; add player_states table
 
Revision ID: 8g6j131h92e7
Revises: 7f5i020g81d6
Create Date: 2026-05-26 12:00:00.000000
 
"""
from typing import Sequence, Union
 
from alembic import op
import sqlalchemy as sa
 
revision: str = '8g6j131h92e7'
down_revision: Union[str, None] = '7f5i020g81d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
 
 
def upgrade() -> None:
    # ── 1. homestead_rooms: new columns ───────────────────────────────────────
    op.add_column(
        'homestead_rooms',
        sa.Column('name', sa.String(64), nullable=False, server_default='My Homestead'),
    )
    op.add_column(
        'homestead_rooms',
        sa.Column(
            'last_played_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text('now()'),
        ),
    )
 
    # ── 2. homestead_player_states: new table ─────────────────────────────────
    op.create_table(
        'homestead_player_states',
        sa.Column('id',      sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('room_id', sa.Integer(), sa.ForeignKey('homestead_rooms.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id',           ondelete='CASCADE'), nullable=False),
        sa.Column('role',    sa.String(2), nullable=False),  # 'p1' | 'p2'
 
        # Player inventory & gear
        sa.Column('inventory',    sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('hotbar',       sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('hotbar_slots', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('equipment',    sa.JSON(), nullable=False,
                  server_default='{"weapon":null,"armor":null,"accessory":null}'),
        sa.Column('character',    sa.JSON(), nullable=False, server_default='{}'),
 
        # World state
        sa.Column('farm_plots',  sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('node_state',  sa.JSON(), nullable=False, server_default='{}'),
 
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text('now()'),
        ),
 
        sa.UniqueConstraint('room_id', 'user_id', name='uq_homestead_player_state'),
    )
 
    op.create_index('ix_homestead_player_states_room_id', 'homestead_player_states', ['room_id'])
    op.create_index('ix_homestead_player_states_user_id', 'homestead_player_states', ['user_id'])
 
 
def downgrade() -> None:
    op.drop_index('ix_homestead_player_states_user_id', table_name='homestead_player_states')
    op.drop_index('ix_homestead_player_states_room_id', table_name='homestead_player_states')
    op.drop_table('homestead_player_states')
 
    op.drop_column('homestead_rooms', 'last_played_at')
    op.drop_column('homestead_rooms', 'name')
 