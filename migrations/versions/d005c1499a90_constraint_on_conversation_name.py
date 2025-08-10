"""Constraint on Conversation.name

Revision ID: d005c1499a90
Revises: 599f25844eab
Create Date: 2025-08-10 12:15:23.042273

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd005c1499a90'
down_revision: Union[str, None] = '599f25844eab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.create_unique_constraint("uq_conversation_name", "conversations", ["name"])

def downgrade():
    op.drop_constraint("uq_conversation_name", "conversations", type_="unique")