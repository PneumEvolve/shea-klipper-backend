from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "15e7722bf364"
down_revision = "add_slalom_scores"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "CREATE TYPE door_house_status AS ENUM "
        "('no_answer', 'not_interested', 'interested', 'follow_up', 'sold')"
    )

    door_house_status_col = postgresql.ENUM(
        "no_answer", "not_interested", "interested", "follow_up", "sold",
        name="door_house_status",
        create_type=False,
    )

    op.create_table(
        "door_neighborhoods",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "name", name="uq_neighborhood_user_name"),
    )

    op.create_table(
        "door_houses",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("neighborhood_id", sa.Integer(), sa.ForeignKey("door_neighborhoods.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("address", sa.String(), nullable=False),
        sa.Column("status", door_house_status_col, nullable=False, server_default="no_answer"),
        sa.Column("service_interest", sa.String(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("follow_up_date", sa.Date(), nullable=True),
        sa.Column("visited_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade():
    op.drop_table("door_houses")
    op.drop_table("door_neighborhoods")
    op.execute("DROP TYPE door_house_status")
