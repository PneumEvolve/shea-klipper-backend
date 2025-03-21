"""Update Food and Recipe Categories

Revision ID: 9504bfe2ba32
Revises: 5d5f03092a58
Create Date: 2025-03-21 10:39:04.482509

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9504bfe2ba32'
down_revision: Union[str, None] = '5d5f03092a58'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('categories', sa.Column('type', sa.String(), nullable=False, server_default="food"))
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('categories', 'type')
    # ### end Alembic commands ###
