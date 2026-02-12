"""execution idempotency constraint

Revision ID: 43013fdb2513
Revises: 5092a38859d9
Create Date: 2026-02-12 15:01:57.460555

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '43013fdb2513'
down_revision: Union[str, Sequence[str], None] = '5092a38859d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.execute("""
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_indexes
        WHERE indexname = 'uq_active_execution'
    ) THEN
        CREATE UNIQUE INDEX uq_active_execution
        ON insight_executions (user_id, insight_type, source_hash)
        WHERE status IN ('locked', 'running', 'pending');
    END IF;
END $$;
""")


def downgrade():
    op.execute("DROP INDEX IF EXISTS uq_active_execution;")
