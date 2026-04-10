"""add created_at to projects

Revision ID: 0fc4272779fe
Revises: cascade_delete_users
Create Date: 2026-04-09 21:00:44.616459

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0fc4272779fe'
down_revision: Union[str, None] = 'cascade_delete_users'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('projects', sa.Column(
        'created_at',
        sa.DateTime(),
        nullable=True,
        server_default=sa.text('now()')
    ))

def downgrade() -> None:
    op.drop_column('projects', 'created_at')