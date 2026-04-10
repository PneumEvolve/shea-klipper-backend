"""Add sms_enabled to stillness_notification_prefs

Revision ID: add_sms_notifs
Revises: add_user_phone_number
Create Date: 2026-04-09
"""
from alembic import op
import sqlalchemy as sa

revision = "add_sms_notifs"
down_revision = "add_user_phone_number"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'stillness_notification_prefs',
        sa.Column('sms_enabled', sa.Boolean(), nullable=False, server_default='true')
    )


def downgrade():
    op.drop_column('stillness_notification_prefs', 'sms_enabled')