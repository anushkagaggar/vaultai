"""add_rag_documents_table

Revision ID: b0595376faa1
Revises: 78fadfb8f26d
Create Date: 2026-02-09 14:58:16.011613

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b0595376faa1'
down_revision: Union[str, Sequence[str], None] = '78fadfb8f26d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


from alembic import op
import sqlalchemy as sa


def upgrade():

    op.create_table(
        "rag_documents",

        sa.Column("id", sa.Integer, primary_key=True),

        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False
        ),

        sa.Column("filename", sa.String(255), nullable=False),

        sa.Column("version", sa.Integer, nullable=False),

        sa.Column("trust_level", sa.Float, nullable=False),

        sa.Column("hash", sa.String(128), nullable=False),

        sa.Column("active", sa.Boolean, default=True),

        sa.Column("uploaded_at", sa.DateTime, server_default=sa.func.now())
    )


def downgrade():
    op.drop_table("rag_documents")

