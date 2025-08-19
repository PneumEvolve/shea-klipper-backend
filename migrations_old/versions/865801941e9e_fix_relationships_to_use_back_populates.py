"""fix relationships to use back_populates

Revision ID: 865801941e9e
Revises: 471baf6e2995
Create Date: 2025-08-09 14:54:12.237019
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '865801941e9e'
down_revision: Union[str, None] = '471baf6e2995'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create foreign key relationship from inbox_messages to users
    op.create_foreign_key('fk_inbox_messages_user_id', 'inbox_messages', 'users', ['user_id'], ['id'])
    
    # Create foreign key relationship from inbox_messages to conversations
    op.create_foreign_key('fk_inbox_messages_conversation_id', 'inbox_messages', 'conversations', ['conversation_id'], ['id'])

    # If needed, create any indexes that are necessary for the relationships
    # op.create_index('ix_inbox_messages_user_id', 'inbox_messages', ['user_id'])
    # op.create_index('ix_inbox_messages_conversation_id', 'inbox_messages', ['conversation_id'])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop the foreign keys if we're downgrading
    op.drop_constraint('fk_inbox_messages_user_id', 'inbox_messages', type_='foreignkey')
    op.drop_constraint('fk_inbox_messages_conversation_id', 'inbox_messages', type_='foreignkey')

    # Drop the indexes if necessary (based on your previous migration)
    # op.drop_index('ix_inbox_messages_user_id', table_name='inbox_messages')
    # op.drop_index('ix_inbox_messages_conversation_id', table_name='inbox_messages')