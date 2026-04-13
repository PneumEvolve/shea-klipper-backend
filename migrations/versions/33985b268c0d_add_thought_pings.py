"""add_thought_pings

Revision ID: 33985b268c0d
Revises: rootwork_states_001
Create Date: 2026-04-13 12:13:47.966797

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '33985b268c0d'
down_revision: Union[str, None] = 'rootwork_states_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('thought_pings',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('sender_id', sa.Integer(), nullable=False),
    sa.Column('recipient_id', sa.Integer(), nullable=False),
    sa.Column('sent_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['recipient_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['sender_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_thought_pings_id'), 'thought_pings', ['id'], unique=False)
    op.create_index(op.f('ix_thought_pings_recipient_id'), 'thought_pings', ['recipient_id'], unique=False)
    op.create_index(op.f('ix_thought_pings_sender_id'), 'thought_pings', ['sender_id'], unique=False)
    op.create_index(op.f('ix_thought_pings_sent_at'), 'thought_pings', ['sent_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_thought_pings_sent_at'), table_name='thought_pings')
    op.drop_index(op.f('ix_thought_pings_sender_id'), table_name='thought_pings')
    op.drop_index(op.f('ix_thought_pings_recipient_id'), table_name='thought_pings')
    op.drop_index(op.f('ix_thought_pings_id'), table_name='thought_pings')
    op.drop_table('thought_pings')