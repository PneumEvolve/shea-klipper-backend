"""homestead: add last_run_day to player_states (daily run gate)

Revision ID: 9h7k242i03f8
Revises: 8g6j131h92e7
Create Date: 2026-05-26 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9h7k242i03f8'
down_revision: Union[str, None] = '8g6j131h92e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Daily run gate. server_default='-1' backfills existing rows, so every
    # current player gets exactly one fresh run on first load after deploy.
    op.add_column(
        'homestead_player_states',
        sa.Column(
            'last_run_day',
            sa.Integer(),
            nullable=False,
            server_default='-1',
        ),
    )


def downgrade() -> None:
    op.drop_column('homestead_player_states', 'last_run_day')