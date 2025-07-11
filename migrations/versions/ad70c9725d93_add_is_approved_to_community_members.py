"""Add is_approved to community_members

Revision ID: ad70c9725d93
Revises: 4f89c2b0e3e1
Create Date: 2025-07-08 18:58:20.564845

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ad70c9725d93'
down_revision: Union[str, None] = '4f89c2b0e3e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('community_members', sa.Column('is_approved', sa.Boolean(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('community_members', 'is_approved')
    # ### end Alembic commands ###
