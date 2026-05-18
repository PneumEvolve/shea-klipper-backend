"""add firefly_rooms
 
Revision ID: add_firefly_rooms
Revises: add_skipped_breathing
Branch_labels: None
Depends_on: None
"""
from alembic import op
import sqlalchemy as sa
 
revision = 'add_firefly_rooms'
down_revision = 'add_skipped_breathing'
branch_labels = None
depends_on = None
 
 
def upgrade():
    op.create_table(
        "firefly_rooms",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("join_code", sa.String(8), nullable=False, unique=True, index=True),
        sa.Column("player1_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("player2_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default="waiting",
        ),  # waiting | active | finished
        sa.Column("map_seed", sa.Integer(), nullable=False),
        sa.Column("final_score", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    )
 
 
def downgrade():
    op.drop_table("firefly_rooms")