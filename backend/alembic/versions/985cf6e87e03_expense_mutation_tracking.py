"""expense mutation tracking

Revision ID: 985cf6e87e03
Revises: 7eb06080284e
Create Date: 2026-02-12 18:50:42.632852

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '985cf6e87e03'
down_revision: Union[str, Sequence[str], None] = '7eb06080284e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column(
        "expenses",
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    )
    op.add_column(
        "expenses",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True)
    )

def downgrade():
    op.drop_column("expenses", "updated_at")
    op.drop_column("expenses", "created_at")
