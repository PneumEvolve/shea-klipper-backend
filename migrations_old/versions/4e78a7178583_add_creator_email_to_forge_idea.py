"""Add creator email to forge idea

Revision ID: 4e78a7178583
Revises: a4e6238df396
Create Date: 2025-08-07 16:00:28.183304
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '4e78a7178583'
down_revision: Union[str, None] = 'a4e6238df396'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: Add column as nullable
    op.add_column('forge_ideas', sa.Column('user_email', sa.String(), nullable=True))

    # Step 2: Backfill existing rows with a placeholder (or real) email
    # Use a placeholder email or retrieve real values if you have them
    op.execute("UPDATE forge_ideas SET user_email = 'unknown@pneumevolve.com'")

    # Step 3: Make column non-nullable
    op.alter_column('forge_ideas', 'user_email', nullable=False)


def downgrade() -> None:
    op.drop_column('forge_ideas', 'user_email')