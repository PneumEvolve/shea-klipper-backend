"""add stillness notifications sent table
 
Revision ID: add_stillness_notifications
Revises: add_shared_stillness
Create Date: 2026-04-06
"""
from alembic import op
import sqlalchemy as sa
 
revision = "add_stillness_notifications"
down_revision = "add_shared_stillness"
branch_labels = None
depends_on = None
 
 
def upgrade():
    op.create_table(
        "stillness_notifications_sent",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "group_id",
            sa.Integer(),
            sa.ForeignKey("stillness_groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # The UTC date this notification was sent for — prevents double-sending
        # for the same group+user on the same calendar day
        sa.Column("sent_for_date", sa.Date(), nullable=False),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "group_id", "user_id", "sent_for_date",
            name="uq_stillness_notification",
        ),
    )
 
 
def downgrade():
    op.drop_table("stillness_notifications_sent")