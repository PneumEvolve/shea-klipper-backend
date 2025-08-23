"""unify into forge_items with backfill

Revision ID: 68c2c5117903
Revises: c48a982c1c8a
Create Date: 2025-08-22 13:29:40.960152
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "68c2c5117903"
down_revision: Union[str, None] = "c48a982c1c8a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM as PGEnum

def upgrade():
    # define enums but DO NOT .create() them
    kind_enum = PGEnum("problem", "idea", name="forge_item_kind")
    status_enum = PGEnum("open", "in_progress", "done", "archived", name="forge_item_status")

    op.create_table(
        "forge_items",
        sa.Column("id", sa.Integer(), primary_key=True),

        sa.Column("legacy_table", sa.String(), nullable=True),
        sa.Column("legacy_id", sa.Integer(), nullable=True),

        sa.Column("kind",   kind_enum,  nullable=False),
        sa.Column("title",  sa.String(), nullable=False),
        sa.Column("body",   sa.Text(),   nullable=True),

        sa.Column("status", status_enum, nullable=False, server_default="open"),
        sa.Column("domain", sa.String(), nullable=True),
        sa.Column("scope",  sa.String(), nullable=True),
        sa.Column("severity", sa.Integer(), nullable=True),
        sa.Column("notes",  sa.Text(),   nullable=True),
        sa.Column("tags",   sa.String(), nullable=True),
        sa.Column("location", sa.String(), nullable=True),

        sa.Column("created_by_email", sa.String(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),

        sa.Column("votes_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("followers_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pledges_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pledges_done", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_forge_items_kind", "forge_items", ["kind"])
    op.create_index("ix_forge_items_legacy", "forge_items", ["legacy_table", "legacy_id"])
    op.create_index("ix_forge_items_created_at", "forge_items", ["created_at"])

    op.create_table(
        "forge_item_votes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("forge_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("voter_identity", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("item_id", "voter_identity", name="uq_forge_item_vote_one"),
    )

    op.create_table(
        "forge_item_follows",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("forge_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("identity", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("item_id", "identity", name="uq_forge_item_follow_one"),
    )

    op.create_table(
        "forge_pledges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("forge_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("text", sa.String(), nullable=False),
        sa.Column("done", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("done_at", sa.DateTime(), nullable=True),
    )

    # --- Backfill ---
    bind = op.get_bind()
    conn = bind

    conn.exec_driver_sql("""
    INSERT INTO forge_items
    (legacy_table, legacy_id, kind, title, body, status, notes,
     created_by_email, created_at, votes_count)
    SELECT
        'forge_ideas' AS legacy_table,
        fi.id AS legacy_id,
        'idea'::forge_item_kind AS kind,
        fi.title,
        fi.description AS body,
        (CASE
            WHEN fi.status IN ('Done') THEN 'done'
            WHEN fi.status IN ('In Progress','Planning') THEN 'in_progress'
            ELSE 'open'
         END)::forge_item_status AS status,
        fi.notes,
        fi.user_email AS created_by_email,
        fi.created_at,
        COALESCE(fi.votes_count, 0)
    FROM forge_ideas fi
    ORDER BY fi.id
""")

    conn.exec_driver_sql("""
    INSERT INTO forge_items
    (legacy_table, legacy_id, kind, title, body, status, domain, scope, severity,
     created_by_email, created_at, votes_count, followers_count)
    SELECT
        'problems' AS legacy_table,
        p.id AS legacy_id,
        'problem'::forge_item_kind AS kind,
        p.title,
        p.description AS body,
        (CASE
            WHEN p.status IN ('Solved','Archived') THEN 'archived'
            WHEN p.status IN ('In Discovery','Triaged') THEN 'in_progress'
            WHEN p.status IN ('Open') THEN 'open'
            ELSE 'open'
         END)::forge_item_status AS status,
        p.domain,
        p.scope,
        p.severity,
        p.created_by_email,
        p.created_at,
        COALESCE(p.votes_count, 0),
        COALESCE(p.followers_count, 0)
    FROM problems p
    ORDER BY p.id
""")

    conn.exec_driver_sql("""
        INSERT INTO forge_item_votes (item_id, voter_identity, created_at)
        SELECT fi2.id, pv.voter_identity, pv.created_at
        FROM problem_votes pv
        JOIN forge_items fi2 ON fi2.legacy_table = 'problems' AND fi2.legacy_id = pv.problem_id
    """)
    conn.exec_driver_sql("""
        INSERT INTO forge_item_votes (item_id, voter_identity, created_at)
        SELECT fi2.id, fv.user_email, fv.created_at
        FROM forge_votes fv
        JOIN forge_items fi2 ON fi2.legacy_table = 'forge_ideas' AND fi2.legacy_id = fv.idea_id
    """)
    conn.exec_driver_sql("""
        INSERT INTO forge_item_follows (item_id, identity, created_at)
        SELECT fi2.id, pf.identity, pf.created_at
        FROM problem_follows pf
        JOIN forge_items fi2 ON fi2.legacy_table = 'problems' AND fi2.legacy_id = pf.problem_id
    """)

    conn.exec_driver_sql("""
        UPDATE forge_items fi
        SET votes_count = COALESCE((SELECT COUNT(*) FROM forge_item_votes v WHERE v.item_id = fi.id), 0),
            followers_count = COALESCE((SELECT COUNT(*) FROM forge_item_follows f WHERE f.item_id = fi.id), 0);
    """)

def downgrade():
    op.drop_table("forge_pledges")
    op.drop_table("forge_item_follows")
    op.drop_table("forge_item_votes")
    op.drop_index("ix_forge_items_created_at", table_name="forge_items")
    op.drop_index("ix_forge_items_legacy", table_name="forge_items")
    op.drop_index("ix_forge_items_kind", table_name="forge_items")
    op.drop_table("forge_items")

    bind = op.get_bind()
    # drop enums after dropping all dependent tables
    op.execute("DROP TYPE IF EXISTS forge_item_status")
    op.execute("DROP TYPE IF EXISTS forge_item_kind")