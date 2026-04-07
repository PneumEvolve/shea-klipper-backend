"""add phone number to users
 
Revision ID: add_user_phone_number
Revises: add_stillness_notif_prefs
Create Date: 2026-04-07
"""
from alembic import op
import sqlalchemy as sa
 
revision = "add_user_phone_number"
down_revision = "add_stillness_notif_prefs"
branch_labels = None
depends_on = None
 
 
def upgrade():
    op.add_column(
        "users",
        sa.Column("phone_number", sa.String(length=20), nullable=True),
    )
 
 
def downgrade():
    op.drop_column("users", "phone_number")