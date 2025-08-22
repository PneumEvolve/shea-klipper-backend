"""reconcile dev schema to prod

Revision ID: 8fe265aae4d5
Revises: 0bbd73b185e2
Create Date: 2025-08-17 22:06:47.072842

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8fe265aae4d5'
down_revision: Union[str, None] = '0bbd73b185e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # --- categories
    op.alter_column('categories', 'type',
        server_default='food', existing_type=sa.String(), existing_nullable=False)

    # --- food_inventory defaults
    op.alter_column('food_inventory', 'quantity',
        server_default='0', existing_type=sa.Integer(), existing_nullable=False)
    op.alter_column('food_inventory', 'desired_quantity',
        server_default='0', existing_type=sa.Integer(), existing_nullable=False)

    # --- forge_votes.created_at default now()
    op.alter_column('forge_votes', 'created_at',
        server_default=sa.text('now()'), existing_type=sa.DateTime(), existing_nullable=True)

    # --- problems: tighten lengths + defaults
    op.alter_column('problems', 'title',
        type_=sa.String(100), existing_type=sa.String(), existing_nullable=False)
    op.alter_column('problems', 'status',
        type_=sa.String(20), existing_type=sa.String(), existing_nullable=True)
    op.alter_column('problems', 'votes_count',
        server_default='0', existing_type=sa.Integer(), existing_nullable=False)
    op.alter_column('problems', 'followers_count',
        server_default='0', existing_type=sa.Integer(), existing_nullable=False)

    # --- seed_events: types + defaults + sequence to BIGINT/JSONB
    # created_at default + not null
    op.alter_column('seed_events', 'created_at',
        server_default=sa.text('now()'), existing_type=sa.DateTime(), existing_nullable=True)
    op.execute("ALTER TABLE seed_events ALTER COLUMN created_at SET NOT NULL")
    # delta to BIGINT
    op.execute("ALTER TABLE seed_events ALTER COLUMN delta TYPE BIGINT USING delta::bigint")
    # metadata to JSONB
    op.execute("ALTER TABLE seed_events ALTER COLUMN metadata TYPE jsonb USING metadata::jsonb")
    # id to BIGINT and sequence to BIGINT
    op.execute("ALTER SEQUENCE IF EXISTS seed_events_id_seq AS BIGINT")
    op.execute("ALTER TABLE seed_events ALTER COLUMN id TYPE BIGINT")

    # --- volunteer_applications: rename & add columns/defaults
    with op.batch_alter_table('volunteer_applications') as batch:
        # rename columns if they still exist under old names
        batch.alter_column('name', new_column_name='volunteer_name', existing_type=sa.String(), existing_nullable=False)
        batch.alter_column('email', new_column_name='volunteer_email', existing_type=sa.String(), existing_nullable=False)
        # add missing columns if not present
        batch.add_column(sa.Column('status', sa.Text(), server_default='Pending'))
        batch.add_column(sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')))

    # --- indexes to match prod (optional but recommended)
    op.execute("CREATE INDEX IF NOT EXISTS ix_seed_events_event_type ON seed_events (event_type)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_seed_events_identity_created ON seed_events (identity, created_at DESC)")

def downgrade():
    pass