from alembic import op
import sqlalchemy as sa

revision = "1c86335c3242"
down_revision = "805df2c6c1f9"
branch_labels = None
depends_on = None

def _scalar(sql, **params):
    conn = op.get_bind()
    return conn.execute(sa.text(sql), params).scalar()

def _exists_table(schema: str, table: str) -> bool:
    return _scalar(
        "select to_regclass(:qname)",
        qname=f"{schema}.{table}"
    ) is not None

def _has_col(table: str, col: str) -> bool:
    return _scalar(
        """
        select 1
        from information_schema.columns
        where table_schema='public' and table_name=:t and column_name=:c
        """,
        t=table, c=col
    ) is not None

def upgrade():
    has_requests = _exists_table("public", "volunteer_requests")
    has_apps = _exists_table("public", "volunteer_applications")

    # 1) If old table exists and new one doesn't, rename it
    if has_requests and not has_apps:
        op.execute("alter table volunteer_requests rename to volunteer_applications;")
        has_apps = True

    # 2) If the table doesn't exist at all, create it with the FINAL schema
    if not has_apps:
        op.create_table(
            "volunteer_applications",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("garden_id", sa.Integer, nullable=True),  # another migration can tighten this later
            sa.Column("volunteer_name", sa.String, nullable=False),
            sa.Column("volunteer_email", sa.String, nullable=True),
            sa.Column("status", sa.String, server_default=sa.text("'Pending'::text")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        )
        return  # done

    # 3) Table exists (either from rename or prior creation) → normalize columns

    # a) name -> volunteer_name (if needed)
    if _has_col("volunteer_applications", "name") and not _has_col("volunteer_applications", "volunteer_name"):
        op.execute("alter table volunteer_applications rename column name to volunteer_name;")
    if not _has_col("volunteer_applications", "volunteer_name"):
        # Add missing column; give a temporary default to satisfy NOT NULL, then drop it.
        op.add_column("volunteer_applications", sa.Column("volunteer_name", sa.String(), nullable=False, server_default=""))
        op.execute("alter table volunteer_applications alter column volunteer_name drop default;")
    else:
        # Ensure it’s VARCHAR
        op.alter_column("volunteer_applications", "volunteer_name", type_=sa.String())

    # b) email -> volunteer_email (if needed)
    if _has_col("volunteer_applications", "email") and not _has_col("volunteer_applications", "volunteer_email"):
        op.execute("alter table volunteer_applications rename column email to volunteer_email;")
    if not _has_col("volunteer_applications", "volunteer_email"):
        op.add_column("volunteer_applications", sa.Column("volunteer_email", sa.String(), nullable=True))
    else:
        op.alter_column("volunteer_applications", "volunteer_email", type_=sa.String(), existing_nullable=True)

    # c) garden_id
    if not _has_col("volunteer_applications", "garden_id"):
        op.add_column("volunteer_applications", sa.Column("garden_id", sa.Integer(), nullable=True))

    # d) status
    if not _has_col("volunteer_applications", "status"):
        op.add_column(
            "volunteer_applications",
            sa.Column("status", sa.String(), server_default=sa.text("'Pending'::text"))
        )

    # e) created_at
    if not _has_col("volunteer_applications", "created_at"):
        op.add_column(
            "volunteer_applications",
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"))
        )

def downgrade():
    # no-op (local bootstrap)
    pass