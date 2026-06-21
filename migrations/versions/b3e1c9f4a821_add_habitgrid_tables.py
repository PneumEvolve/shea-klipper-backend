"""add habitgrid tables

Revision ID: b3e1c9f4a821
Revises: ah8l353j14g9
Create Date: 2026-06-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b3e1c9f4a821'
down_revision: Union[str, None] = 'ah8l353j14g9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'habit_colors',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.String(), nullable=False),
        sa.Column('hex', sa.String(length=9), nullable=False),
        sa.Column('label', sa.String(), nullable=False, server_default=''),
        sa.Column('order_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'client_id', name='uq_habit_color_user_client_id'),
    )
    op.create_index(op.f('ix_habit_colors_id'), 'habit_colors', ['id'], unique=False)
    op.create_index(op.f('ix_habit_colors_user_id'), 'habit_colors', ['user_id'], unique=False)

    op.create_table(
        'habits',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('order_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('archived', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'client_id', name='uq_habit_user_client_id'),
    )
    op.create_index(op.f('ix_habits_id'), 'habits', ['id'], unique=False)
    op.create_index(op.f('ix_habits_user_id'), 'habits', ['user_id'], unique=False)

    op.create_table(
        'goals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.String(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('target_date', sa.Date(), nullable=True),
        sa.Column('advance_mode', sa.String(length=8), nullable=False, server_default='manual'),
        sa.Column('current_stage_client_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'client_id', name='uq_goal_user_client_id'),
    )
    op.create_index(op.f('ix_goals_id'), 'goals', ['id'], unique=False)
    op.create_index(op.f('ix_goals_user_id'), 'goals', ['user_id'], unique=False)

    op.create_table(
        'habit_marks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('habit_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('color_client_id', sa.String(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['habit_id'], ['habits.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('habit_id', 'date', name='uq_habit_mark_habit_date'),
    )
    op.create_index(op.f('ix_habit_marks_id'), 'habit_marks', ['id'], unique=False)
    op.create_index(op.f('ix_habit_marks_habit_id'), 'habit_marks', ['habit_id'], unique=False)
    op.create_index(op.f('ix_habit_marks_user_id'), 'habit_marks', ['user_id'], unique=False)

    op.create_table(
        'goal_stages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('goal_id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.String(), nullable=False),
        sa.Column('label', sa.String(), nullable=False),
        sa.Column('criteria', sa.String(), nullable=False, server_default=''),
        sa.Column('start_date', sa.Date(), nullable=True),
        sa.Column('order_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['goal_id'], ['goals.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('goal_id', 'client_id', name='uq_goal_stage_goal_client_id'),
    )
    op.create_index(op.f('ix_goal_stages_id'), 'goal_stages', ['id'], unique=False)
    op.create_index(op.f('ix_goal_stages_goal_id'), 'goal_stages', ['goal_id'], unique=False)

    op.create_table(
        'habit_goal_links',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('habit_id', sa.Integer(), nullable=False),
        sa.Column('goal_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['habit_id'], ['habits.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['goal_id'], ['goals.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('habit_id', 'goal_id', name='uq_habit_goal_link'),
    )
    op.create_index(op.f('ix_habit_goal_links_id'), 'habit_goal_links', ['id'], unique=False)
    op.create_index(op.f('ix_habit_goal_links_habit_id'), 'habit_goal_links', ['habit_id'], unique=False)
    op.create_index(op.f('ix_habit_goal_links_goal_id'), 'habit_goal_links', ['goal_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_habit_goal_links_goal_id'), table_name='habit_goal_links')
    op.drop_index(op.f('ix_habit_goal_links_habit_id'), table_name='habit_goal_links')
    op.drop_index(op.f('ix_habit_goal_links_id'), table_name='habit_goal_links')
    op.drop_table('habit_goal_links')

    op.drop_index(op.f('ix_goal_stages_goal_id'), table_name='goal_stages')
    op.drop_index(op.f('ix_goal_stages_id'), table_name='goal_stages')
    op.drop_table('goal_stages')

    op.drop_index(op.f('ix_habit_marks_user_id'), table_name='habit_marks')
    op.drop_index(op.f('ix_habit_marks_habit_id'), table_name='habit_marks')
    op.drop_index(op.f('ix_habit_marks_id'), table_name='habit_marks')
    op.drop_table('habit_marks')

    op.drop_index(op.f('ix_goals_user_id'), table_name='goals')
    op.drop_index(op.f('ix_goals_id'), table_name='goals')
    op.drop_table('goals')

    op.drop_index(op.f('ix_habits_user_id'), table_name='habits')
    op.drop_index(op.f('ix_habits_id'), table_name='habits')
    op.drop_table('habits')

    op.drop_index(op.f('ix_habit_colors_user_id'), table_name='habit_colors')
    op.drop_index(op.f('ix_habit_colors_id'), table_name='habit_colors')
    op.drop_table('habit_colors')