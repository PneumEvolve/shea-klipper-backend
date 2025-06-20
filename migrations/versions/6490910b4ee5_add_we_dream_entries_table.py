"""add we_dream_entries table

Revision ID: 6490910b4ee5
Revises: 2f3dc4a3c4a1
Create Date: 2025-05-29 13:45:22.846875

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6490910b4ee5'
down_revision: Union[str, None] = '2f3dc4a3c4a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('we_dream_entries',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('vision', sa.Text(), nullable=False),
    sa.Column('mantra', sa.String(), nullable=False),
    sa.Column('is_active', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_we_dream_entries_id'), 'we_dream_entries', ['id'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_we_dream_entries_id'), table_name='we_dream_entries')
    op.drop_table('we_dream_entries')
    # ### end Alembic commands ###
