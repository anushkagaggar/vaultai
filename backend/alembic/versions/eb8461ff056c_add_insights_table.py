"""add_insights_table

Revision ID: eb8461ff056c
Revises: 481531541131
Create Date: 2026-02-06 18:25:24.688524

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'eb8461ff056c'
down_revision: Union[str, Sequence[str], None] = '481531541131'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade():
    op.create_table(
        "insights",

        sa.Column("id", sa.Integer, primary_key=True),

        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False
        ),

        sa.Column("type", sa.String(50), nullable=False),

        sa.Column("summary", sa.Text, nullable=False),

        sa.Column("metrics", sa.JSON, nullable=False),

        sa.Column("confidence", sa.Float, nullable=False),

        sa.Column("source_hash", sa.String(128), nullable=False),

        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.now()
        ),
    )

    op.create_index(
        "idx_insights_user_type",
        "insights",
        ["user_id", "type"]
    )

    op.create_index(
        "idx_insights_source",
        "insights",
        ["source_hash"]
    )


def downgrade():
    op.drop_index("idx_insights_source", table_name="insights")
    op.drop_index("idx_insights_user_type", table_name="insights")

    op.drop_table("insights")

