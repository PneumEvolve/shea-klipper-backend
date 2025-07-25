"""create inbox table

Revision ID: 57966afe177b
Revises: 5a2e777d7157
Create Date: 2025-07-22 11:24:08.987050

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '57966afe177b'
down_revision: Union[str, None] = '5a2e777d7157'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('inbox_messages',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=True),
    sa.Column('content', sa.String(), nullable=True),
    sa.Column('timestamp', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_inbox_messages_id'), 'inbox_messages', ['id'], unique=False)
    op.create_index(op.f('ix_inbox_messages_user_id'), 'inbox_messages', ['user_id'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_inbox_messages_user_id'), table_name='inbox_messages')
    op.drop_index(op.f('ix_inbox_messages_id'), table_name='inbox_messages')
    op.drop_table('inbox_messages')
    # ### end Alembic commands ###
