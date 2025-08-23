"""merge parallel heads before forge_items

Revision ID: c48a982c1c8a
Revises: ae5b8ba20b1c, c9febb209ee6
Create Date: 2025-08-22 13:29:21.174639

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c48a982c1c8a'
down_revision: Union[str, None] = ('ae5b8ba20b1c', 'c9febb209ee6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
