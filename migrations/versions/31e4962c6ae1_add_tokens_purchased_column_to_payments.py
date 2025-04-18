"""Add tokens_purchased column to payments

Revision ID: 31e4962c6ae1
Revises: 3ca896ecb3ca
Create Date: 2025-04-17 13:11:58.028373

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '31e4962c6ae1'
down_revision: Union[str, None] = '3ca896ecb3ca'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('payments', sa.Column('tokens_purchased', sa.Integer(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('payments', 'tokens_purchased')
    # ### end Alembic commands ###
