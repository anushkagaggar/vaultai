"""add_llm_output_to_executions

Revision ID: c37233012897
Revises: 985cf6e87e03
Create Date: 2026-02-12 23:42:38.398629

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c37233012897'
down_revision: Union[str, Sequence[str], None] = '985cf6e87e03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade():
    op.add_column(
        "insight_executions",
        sa.Column("llm_output", sa.Text, nullable=True)
    )

def downgrade():
    op.drop_column("insight_executions", "llm_output")