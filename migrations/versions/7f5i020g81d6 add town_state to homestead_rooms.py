"""add town_state to homestead_rooms

Revision ID: 7f5i020g81d6
Revises: 6e4h919f70c5
Create Date: 2026-05-25 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '7f5i020g81d6'
down_revision: Union[str, None] = '6e4h919f70c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'homestead_rooms',
        sa.Column('town_state', sa.JSON(), nullable=False, server_default='{}'),
    )


def downgrade() -> None:
    op.drop_column('homestead_rooms', 'town_state')