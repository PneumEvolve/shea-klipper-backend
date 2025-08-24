"""add user_username to forge_ideas

Revision ID: a9be345fbb4f
Revises: fd17aab42cdf
Create Date: 2025-08-24 12:45:07.606972

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a9be345fbb4f'
down_revision: Union[str, None] = 'fd17aab42cdf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column('forge_ideas', sa.Column('user_username', sa.String(), nullable=True))

def downgrade():
    op.drop_column('forge_ideas', 'user_username')