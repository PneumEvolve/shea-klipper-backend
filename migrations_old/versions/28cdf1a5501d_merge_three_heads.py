"""Merge three heads

Revision ID: 28cdf1a5501d
Revises: 1c86335c3242, 9a1b2c3d4e56, b1a2c3d4e5f6
Create Date: 2025-08-16 13:21:07.319873

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '28cdf1a5501d'
down_revision: Union[str, None] = ('1c86335c3242', '9a1b2c3d4e56', 'b1a2c3d4e5f6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
