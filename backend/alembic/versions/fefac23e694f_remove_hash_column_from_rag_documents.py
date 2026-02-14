"""remove_hash_column_from_rag_documents

Revision ID: fefac23e694f
Revises: c37233012897
Create Date: 2026-02-14 23:42:20.753684

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fefac23e694f'
down_revision: Union[str, Sequence[str], None] = 'c37233012897'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Remove the old 'hash' column
    op.drop_column('rag_documents', 'hash')


def downgrade():
    # Restore 'hash' column if needed (optional)
    op.add_column(
        'rag_documents',
        sa.Column('hash', sa.String(64), nullable=True)
    )