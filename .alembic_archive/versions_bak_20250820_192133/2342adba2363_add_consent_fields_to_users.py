"""add consent fields to users

Revision ID: 2342adba2363
Revises: a1b811ca79ca
Create Date: 2025-08-20 18:02:11.730553

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2342adba2363'
down_revision: Union[str, None] = 'a1b811ca79ca'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



def upgrade():
    op.add_column(
        'users',
        sa.Column('terms_accepted_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        'users',
        sa.Column('policy_version', sa.String(length=32), nullable=True)
    )

def downgrade():
    op.drop_column('users', 'policy_version')
    op.drop_column('users', 'terms_accepted_at')
