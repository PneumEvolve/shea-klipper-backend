"""add clear and calm tables

Revision ID: xxxx
Revises: <your_current_head>
Create Date: 2026-05-17
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_clear_and_calm'
down_revision = '33985b268c0d'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "cc_sober_starts",
        sa.Column("user_id",    sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "cc_cravings",
        sa.Column("id",               sa.Integer, primary_key=True),
        sa.Column("user_id",          sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("recorded_at",      sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("intensity_before", sa.Integer, nullable=False),
        sa.Column("intensity_after",  sa.Integer, nullable=False),
        sa.Column("reduction",        sa.Integer, nullable=False),
    )
    op.create_table(
        "cc_meditations",
        sa.Column("id",            sa.Integer, primary_key=True),
        sa.Column("user_id",       sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("recorded_at",   sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("duration_secs", sa.Integer, nullable=False),
    )
    op.create_table(
        "cc_gave_in",
        sa.Column("id",          sa.Integer, primary_key=True),
        sa.Column("user_id",     sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("cc_gave_in")
    op.drop_table("cc_meditations")
    op.drop_table("cc_cravings")
    op.drop_table("cc_sober_starts")