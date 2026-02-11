"""add_step_failed_to_executions

Revision ID: 5092a38859d9
Revises: df5b60d7d667
Create Date: 2026-02-11 18:28:51.218232

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5092a38859d9'
down_revision: Union[str, Sequence[str], None] = 'df5b60d7d667'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column(
        "insight_executions",
        sa.Column("step_failed", sa.String(50), nullable=True)
    )

def downgrade():
    op.drop_column("insight_executions", "step_failed")