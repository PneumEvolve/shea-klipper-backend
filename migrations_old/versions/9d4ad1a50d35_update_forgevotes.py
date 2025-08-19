"""Update ForgeVotes

Revision ID: 9d4ad1a50d35
Revises: d005c1499a90
Create Date: 2025-08-10 16:43:09.363868

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9d4ad1a50d35'
down_revision: Union[str, None] = 'd005c1499a90'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Drop legacy unique on conversations.name if you intend to allow duplicates during migration
    op.drop_constraint('uq_conversation_name', 'conversations', type_='unique')

    # Add created_at (optional: server default now())
    op.add_column('forge_votes', sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True))

    # Ensure idea_id is NOT NULL (as autogen suggested)
    op.alter_column('forge_votes', 'idea_id',
               existing_type=sa.INTEGER(),
               nullable=False)

    # ---------- BACKFILL START (CRITICAL) ----------
    # 1) For old anonymous rows: move user_id -> user_email as "anon:{user_id}"
    op.execute("""
        UPDATE forge_votes
        SET user_email = 'anon:' || user_id
        WHERE user_email IS NULL AND user_id IS NOT NULL AND user_id <> '';
    """)

    # 2) For any remaining NULL/empty user_email rows, synthesize an identity from the row id
    #    (prevents NOT NULL violation; you can choose a different scheme if you like)
    op.execute("""
        UPDATE forge_votes
        SET user_email = 'anon:migrated:' || id::text
        WHERE (user_email IS NULL OR user_email = '');
    """)
    # ---------- BACKFILL END ----------

    # Now we can safely enforce NOT NULL on user_email
    op.alter_column('forge_votes', 'user_email',
               existing_type=sa.VARCHAR(),
               nullable=False)

    # Create helpful indexes (as autogen suggested)
    op.create_index(op.f('ix_forge_votes_idea_id'), 'forge_votes', ['idea_id'], unique=False)
    op.create_index(op.f('ix_forge_votes_user_email'), 'forge_votes', ['user_email'], unique=False)

    # One vote per (idea_id, user_email)
    op.create_unique_constraint('uq_vote_one_per_identity', 'forge_votes', ['idea_id', 'user_email'])

    # Drop old user_id column after backfill
    op.drop_column('forge_votes', 'user_id')



def downgrade() -> None:
    """Downgrade schema."""
    # Re-add user_id if you need a real downgrade path
    op.add_column('forge_votes', sa.Column('user_id', sa.VARCHAR(), autoincrement=False, nullable=True))

    # Drop unique + indexes
    op.drop_constraint('uq_vote_one_per_identity', 'forge_votes', type_='unique')
    op.drop_index(op.f('ix_forge_votes_user_email'), table_name='forge_votes')
    op.drop_index(op.f('ix_forge_votes_idea_id'), table_name='forge_votes')

    # Make user_email nullable again
    op.alter_column('forge_votes', 'user_email',
               existing_type=sa.VARCHAR(),
               nullable=True)

    # Allow idea_id to be nullable again (matches your autogen)
    op.alter_column('forge_votes', 'idea_id',
               existing_type=sa.INTEGER(),
               nullable=True)

    # Drop created_at (or keep if you prefer)
    op.drop_column('forge_votes', 'created_at')

    # Recreate the old unique on conversations.name if you actually want it back
    op.create_unique_constraint('uq_conversation_name', 'conversations', ['name'])
