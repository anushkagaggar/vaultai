"""add plans table

Revision ID: 639c88a0d535
Revises: 5e874c5d5557
Create Date: 2026-03-01 15:35:08.857558

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '639c88a0d535'
down_revision: Union[str, Sequence[str], None] = '5e874c5d5557'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'plans',
        sa.Column('id',                 sa.Integer(),    nullable=False),
        sa.Column('user_id',            sa.Integer(),    nullable=False),
        sa.Column('plan_type',          sa.String(20),   nullable=False),
        sa.Column('source_hash',        sa.String(64),   nullable=False),
        sa.Column('pipeline_version',   sa.String(20),   nullable=False),
        sa.Column('status',             sa.String(20),   nullable=False),
        sa.Column('degraded',           sa.Boolean(),    nullable=False, default=False),
        sa.Column('projected_outcomes', sa.JSON(),       nullable=True),
        sa.Column('assumptions',        sa.JSON(),       nullable=True),
        sa.Column('explanation',        sa.Text(),       nullable=True),
        sa.Column('graph_trace',        sa.JSON(),       nullable=True),
        sa.Column('audit_payload',      sa.JSON(),       nullable=True),
        sa.Column('confidence',         sa.JSON(),       nullable=True),
        sa.Column('created_at',         sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id', name=op.f('plans_pkey')),
        sa.UniqueConstraint('user_id', 'plan_type', 'source_hash',
                            name='uq_plan_user_type_hash'),
    )
    op.create_index(op.f('ix_plans_id'),      'plans', ['id'],      unique=False)
    op.create_index(op.f('ix_plans_user_id'), 'plans', ['user_id'], unique=False)
    op.create_index('idx_plans_user_hash',    'plans', ['user_id', 'source_hash'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_plans_user_hash',         table_name='plans')
    op.drop_index(op.f('ix_plans_user_id'),      table_name='plans')
    op.drop_index(op.f('ix_plans_id'),           table_name='plans')
    op.drop_table('plans')