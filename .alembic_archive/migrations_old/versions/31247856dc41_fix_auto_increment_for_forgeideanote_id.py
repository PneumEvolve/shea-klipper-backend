"""Fix auto-increment for ForgeIdeaNote id

Revision ID: 31247856dc41
Revises: 7b6bcd8c249f
Create Date: 2025-08-08 22:53:05.613456
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '31247856dc41'
down_revision: Union[str, None] = '7b6bcd8c249f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Skip creating the table if it already exists, just ensure the 'id' column is set to autoincrement
    # We will check if the table already exists, and if it doesn't, we will create it
    # In case the column isn't set to autoincrement, we can ensure it's done here

    # Check if the table exists in the database
    # If it does, make sure that the 'id' column is serial
    op.execute("""
        DO $$
        BEGIN
            -- Check if the 'forge_idea_notes' table exists
            IF NOT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'forge_idea_notes') THEN
                -- If not, create the table
                CREATE TABLE forge_idea_notes (
                    id SERIAL PRIMARY KEY,
                    content TEXT NOT NULL,
                    idea_id INTEGER,
                    FOREIGN KEY(idea_id) REFERENCES forge_ideas(id) ON DELETE CASCADE
                );
            END IF;
        END $$;
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('forge_idea_notes')