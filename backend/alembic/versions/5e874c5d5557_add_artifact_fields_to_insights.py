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

def upgrade():
    # Add new columns for artifact tracking
    op.add_column('insights', sa.Column('execution_id', sa.Integer(), nullable=True))
    op.add_column('insights', sa.Column('status', sa.String(20), nullable=True))
    op.add_column('insights', sa.Column('pipeline_version', sa.String(20), nullable=True))
    
    # Add foreign key to executions
    op.create_foreign_key(
        'fk_insights_execution',
        'insights',
        'insight_executions',
        ['execution_id'],
        ['id']
    )
    
    # Add unique constraint for (user_id, type, source_hash)
    op.create_unique_constraint(
        'uq_insight_state',
        'insights',
        ['user_id', 'type', 'source_hash']
    )


def downgrade():
    op.drop_constraint('uq_insight_state', 'insights', type_='unique')
    op.drop_constraint('fk_insights_execution', 'insights', type_='foreignkey')
    op.drop_column('insights', 'pipeline_version')
    op.drop_column('insights', 'status')
    op.drop_column('insights', 'execution_id')