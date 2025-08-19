"""Add node_membership table

Revision ID: 089911684901
Revises: 5e28c20f4e76
Create Date: 2025-06-02 20:29:14.781110

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '089911684901'
down_revision: Union[str, None] = '5e28c20f4e76'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'node_membership',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('node_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['node_id'], ['nodes.id']),
        sa.PrimaryKeyConstraint('user_id', 'node_id')
    )

def downgrade() -> None:
    op.drop_table('node_membership')