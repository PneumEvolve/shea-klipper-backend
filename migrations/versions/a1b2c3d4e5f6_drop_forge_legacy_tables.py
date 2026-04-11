"""drop forge_ideas, forge_workers, forge_votes

Revision ID: a1b2c3d4e5f6
Revises: 0fc4272779fe
Create Date: 2026-04-10
"""
from alembic import op

revision = 'a1b2c3d4e5f6'
down_revision = '0fc4272779fe'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table('forge_workers')
    op.drop_table('forge_votes')
    op.drop_table('forge_ideas')


def downgrade():
    pass