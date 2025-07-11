"""Add assigned_to and completed_by to CommunityProjectTask

Revision ID: 1180c8c0bbbc
Revises: 4f7a8b3f4536
Create Date: 2025-07-12 14:06:07.351866

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1180c8c0bbbc'
down_revision: Union[str, None] = '4f7a8b3f4536'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('community_project_tasks', sa.Column('completed_by_user_id', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'community_project_tasks', 'users', ['completed_by_user_id'], ['id'])
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'community_project_tasks', type_='foreignkey')
    op.drop_column('community_project_tasks', 'completed_by_user_id')
    # ### end Alembic commands ###
