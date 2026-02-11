"""add_insight_executions

Revision ID: df5b60d7d667
Revises: b0595376faa1
Create Date: 2026-02-11 18:13:13.718531

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'df5b60d7d667'
down_revision: Union[str, Sequence[str], None] = 'b0595376faa1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():

    op.create_table(
        "insight_executions",

        sa.Column("id", sa.Integer, primary_key=True),

        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("insight_type", sa.String(50), nullable=False),

        sa.Column("pipeline_version", sa.String(20)),
        sa.Column("prompt_template_version", sa.String(20)),
        sa.Column("model_version", sa.String(50)),
        sa.Column("embedding_version", sa.String(50)),

        sa.Column("analytics_snapshot", sa.JSON),
        sa.Column("rag_snapshot", sa.JSON),
        sa.Column("prompt_snapshot", sa.Text),

        sa.Column("status", sa.String(20), nullable=False),

        sa.Column("source_hash", sa.String(64), nullable=False),

        sa.Column("cancel_requested", sa.Boolean, server_default="false"),

        sa.Column("error_code", sa.String(50)),
        sa.Column("error_message", sa.Text),

        sa.Column("started_at", sa.DateTime),
        sa.Column("completed_at", sa.DateTime),
    )


    op.create_index(
        "uq_active_execution",
        "insight_executions",
        ["user_id", "insight_type", "source_hash"],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('pending','running','locked')"
        )
    )


def downgrade():

    op.drop_index("uq_active_execution", table_name="insight_executions")
    op.drop_table("insight_executions")
