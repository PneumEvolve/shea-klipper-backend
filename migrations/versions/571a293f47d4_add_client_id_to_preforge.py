from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '571a293f47d4'
down_revision = "0e88b8e0b3c2"  # <-- set to your current head
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("preforge_topics", sa.Column("client_id", sa.String(), nullable=True))
    op.add_column("preforge_items", sa.Column("client_id", sa.String(), nullable=True))

    op.create_unique_constraint(
        "uq_preforge_topic_user_client_id",
        "preforge_topics",
        ["user_id", "client_id"],
    )
    op.create_unique_constraint(
        "uq_preforge_item_topic_client_id",
        "preforge_items",
        ["topic_id", "client_id"],
    )


def downgrade():
    op.drop_constraint("uq_preforge_item_topic_client_id", "preforge_items", type_="unique")
    op.drop_constraint("uq_preforge_topic_user_client_id", "preforge_topics", type_="unique")

    op.drop_column("preforge_items", "client_id")
    op.drop_column("preforge_topics", "client_id")