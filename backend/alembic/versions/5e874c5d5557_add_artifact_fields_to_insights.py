"""add_artifact_fields_to_insights

Revision ID: 5e874c5d5557
Revises: fefac23e694f
Create Date: 2026-02-16 15:40:04.997274

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5e874c5d5557'
down_revision: Union[str, Sequence[str], None] = 'fefac23e694f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
