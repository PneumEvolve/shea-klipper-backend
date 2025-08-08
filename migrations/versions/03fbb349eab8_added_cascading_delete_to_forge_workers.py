from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '03fbb349eab8'
down_revision: Union[str, None] = '4e78a7178583'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Upgrade schema."""
    # Drop the old foreign key constraints for forge_votes and forge_workers
    op.drop_constraint('forge_votes_idea_id_fkey', 'forge_votes', type_='foreignkey')
    op.drop_constraint('forge_workers_idea_id_fkey', 'forge_workers', type_='foreignkey')

    # Add the new foreign key constraints with ON DELETE CASCADE
    op.create_foreign_key(
        'forge_votes_idea_id_fkey_cascade',  # Descriptive name for the constraint
        'forge_votes', 'forge_ideas', ['idea_id'], ['id'], ondelete='CASCADE'
    )
    op.create_foreign_key(
        'forge_workers_idea_id_fkey_cascade',  # Descriptive name for the constraint
        'forge_workers', 'forge_ideas', ['idea_id'], ['id'], ondelete='CASCADE'
    )

def downgrade() -> None:
    """Downgrade schema."""
    # Drop the foreign key constraints with CASCADE
    op.drop_constraint('forge_votes_idea_id_fkey_cascade', 'forge_votes', type_='foreignkey')
    op.drop_constraint('forge_workers_idea_id_fkey_cascade', 'forge_workers', type_='foreignkey')

    # Recreate the original foreign key constraints without CASCADE
    op.create_foreign_key(
        'forge_votes_idea_id_fkey', 'forge_votes', 'forge_ideas', ['idea_id'], ['id']
    )
    op.create_foreign_key(
        'forge_workers_idea_id_fkey', 'forge_workers', 'forge_ideas', ['idea_id'], ['id']
    )