"""add_door_house_appointments

Revision ID: 31bbad557aa9
Revises: 15e7722bf364
Create Date: 2026-09-03 10:03:36.593108

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '31bbad557aa9'
down_revision: Union[str, None] = '15e7722bf364'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column("door_houses", sa.Column("appointment_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "door_houses",
        sa.Column("appointment_completed", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.drop_column("door_houses", "follow_up_date")


def downgrade():
    op.add_column("door_houses", sa.Column("follow_up_date", sa.Date(), nullable=True))
    op.drop_column("door_houses", "appointment_completed")
    op.drop_column("door_houses", "appointment_at")