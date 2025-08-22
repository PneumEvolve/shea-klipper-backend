"""add terms fields to users

Revision ID: ae5b8ba20b1c
Revises: 5f960c82dd6c
Create Date: 2025-08-21 14:21:17.601155

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'ae5b8ba20b1c'
down_revision: Union[str, None] = '5f960c82dd6c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # add with default so existing rows get a value, then (optionally) drop the default
    op.add_column('users', sa.Column('accepted_terms', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.add_column('users', sa.Column('accepted_terms_at', sa.TIMESTAMP(timezone=True)))
    op.add_column('users', sa.Column('accepted_terms_version', sa.String()))
    # optional: remove default so future inserts must set it explicitly
    op.alter_column('users', 'accepted_terms', server_default=None)

def downgrade():
    op.drop_column('users', 'accepted_terms_version')
    op.drop_column('users', 'accepted_terms_at')
    op.drop_column('users', 'accepted_terms')