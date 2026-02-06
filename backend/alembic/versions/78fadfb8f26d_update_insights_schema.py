"""update_insights_schema

Revision ID: 78fadfb8f26d
Revises: eb8461ff056c
Create Date: 2026-02-06 18:35:26.871539

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '78fadfb8f26d'
down_revision: Union[str, Sequence[str], None] = 'eb8461ff056c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
