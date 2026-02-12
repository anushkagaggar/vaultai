"""rag_document content tracking

Revision ID: 7eb06080284e
Revises: 43013fdb2513
Create Date: 2026-02-12 17:59:29.251050

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '7eb06080284e'
down_revision: Union[str, Sequence[str], None] = '43013fdb2513'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade():
    op.add_column(
        "rag_documents",
        sa.Column("content_hash", sa.String(length=128), nullable=True)
    )

    op.add_column(
        "rag_documents",
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now())
    )

    # Backfill existing rows
    op.execute("""
        UPDATE rag_documents
        SET content_hash = hash
        WHERE content_hash IS NULL;
    """)

    # Make non-nullable AFTER backfill
    op.alter_column("rag_documents", "content_hash", nullable=False)

def downgrade():
    op.drop_column("rag_documents", "updated_at")
    op.drop_column("rag_documents", "content_hash")