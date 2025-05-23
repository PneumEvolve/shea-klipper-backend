"""Add payments table

Revision ID: 2ff15663af35
Revises: 52adac373808
Create Date: 2025-04-13 17:17:23.943401

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2ff15663af35'
down_revision: Union[str, None] = '52adac373808'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('payments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('amount', sa.Float(), nullable=False),
    sa.Column('currency', sa.String(), nullable=True),
    sa.Column('stripe_session_id', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('stripe_session_id')
    )
    op.create_index(op.f('ix_payments_id'), 'payments', ['id'], unique=False)
    op.add_column('users', sa.Column('has_active_payment', sa.Boolean(), nullable=True))
    op.add_column('users', sa.Column('api_balance_dollars', sa.Float(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('users', 'api_balance_dollars')
    op.drop_column('users', 'has_active_payment')
    op.drop_index(op.f('ix_payments_id'), table_name='payments')
    op.drop_table('payments')
    # ### end Alembic commands ###
