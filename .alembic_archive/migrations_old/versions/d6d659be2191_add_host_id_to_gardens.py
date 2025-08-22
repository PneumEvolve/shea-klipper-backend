"""Add host_id to gardens

Revision ID: d6d659be2191
Revises: 599f25844eab
Create Date: 2025-06-19 10:55:31.277934
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "d6d659be2191"
down_revision: Union[str, None] = "599f25844eab"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) add the column only if missing
    op.execute("""
        ALTER TABLE public.gardens
        ADD COLUMN IF NOT EXISTS host_id integer
    """)

    # 2) add the FK only if missing
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM   pg_constraint
            WHERE  conname = 'gardens_host_id_fkey'
        ) THEN
            ALTER TABLE public.gardens
            ADD CONSTRAINT gardens_host_id_fkey
            FOREIGN KEY (host_id) REFERENCES public.users(id);
        END IF;
    END $$;
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE public.gardens DROP CONSTRAINT IF EXISTS gardens_host_id_fkey")
    op.execute("ALTER TABLE public.gardens DROP COLUMN IF EXISTS host_id")