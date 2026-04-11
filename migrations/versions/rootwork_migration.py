"""create rootwork_states table
 
Revision ID: rootwork_states_001
Revises: a1b2c3d4e5f6
Create Date: 2026-04-11
"""
from alembic import op
import sqlalchemy as sa
 
revision = 'rootwork_states_001'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None
 
 
def upgrade():
    op.create_table(
        'rootwork_states',
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('data', sa.Text(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
 
 
def downgrade():
    op.drop_table('rootwork_states')