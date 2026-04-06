"""add stillness notification prefs
 
Revision ID: add_stillness_notif_prefs
Revises: add_stillness_notifications
Create Date: 2026-04-06
"""
from alembic import op
import sqlalchemy as sa
 
revision = "add_stillness_notif_prefs"
down_revision = "add_stillness_notifications"
branch_labels = None
depends_on = None
 
 
def upgrade():
    op.create_table(
        "stillness_notification_prefs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "group_id",
            sa.Integer(),
            sa.ForeignKey("stillness_groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.UniqueConstraint("user_id", "group_id", name="uq_stillness_notif_pref"),
    )
 
 
def downgrade():
    op.drop_table("stillness_notification_prefs")