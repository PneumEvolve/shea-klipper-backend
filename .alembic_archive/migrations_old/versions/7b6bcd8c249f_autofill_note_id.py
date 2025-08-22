"""autofill note id

Revision ID: 7b6bcd8c249f
Revises: 91eb799d9c39
Create Date: 2025-08-08 22:47:56.233374

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7b6bcd8c249f'
down_revision: Union[str, None] = '91eb799d9c39'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('forge_idea_notes', 'id',
                    existing_type=sa.Integer(),
                    autoincrement=True)

def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('forge_idea_notes', 'id',
                    existing_type=sa.Integer(),
                    autoincrement=False)