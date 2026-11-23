"""arcade room worlds

Revision ID: 93188d25defe
Revises: 45263a2c33c8
Create Date: 2026-11-23 14:31:16.246210

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '93188d25defe'
down_revision: Union[str, None] = '45263a2c33c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column("arcade_rooms", sa.Column("world", sa.JSON(), nullable=True))
    op.add_column("arcade_rooms", sa.Column("world_version", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("arcade_rooms", sa.Column("world_saved_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("arcade_rooms", "world_saved_at")
    op.drop_column("arcade_rooms", "world_version")
    op.drop_column("arcade_rooms", "world")