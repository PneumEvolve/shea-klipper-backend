"""add shared stillness tables
 
Revision ID: add_shared_stillness
Revises: <your_last_revision_id>
Create Date: 2026-04-06
"""
from alembic import op
import sqlalchemy as sa
 
revision = "add_shared_stillness"
down_revision = '94be2ac16995'
branch_labels = None
depends_on = None
 
 
def upgrade():
    op.create_table(
        "stillness_groups",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invite_code", sa.String(length=12), unique=True, nullable=False, index=True),
        sa.Column("daily_time_utc", sa.Time(), nullable=True),  # e.g. 08:00 UTC — null = uses interval
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
 
    op.create_table(
        "stillness_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("stillness_groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("group_id", "user_id", name="uq_stillness_member"),
    )
 
    op.create_table(
        "stillness_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("stillness_groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_seconds", sa.Integer(), default=300, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
 
    op.create_table(
        "stillness_checkins",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("stillness_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("checked_in_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("session_id", "user_id", name="uq_stillness_checkin"),
    )
 
 
def downgrade():
    op.drop_table("stillness_checkins")
    op.drop_table("stillness_sessions")
    op.drop_table("stillness_members")
    op.drop_table("stillness_groups")