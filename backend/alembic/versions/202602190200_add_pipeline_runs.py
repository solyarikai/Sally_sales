"""add pipeline_runs, pipeline_phase_logs, cost_events tables

Revision ID: 202602190200
Revises: 202602190100
Create Date: 2026-02-19 02:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '202602190200'
down_revision: Union[str, None] = '202602190100'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types
    pipeline_run_status = sa.Enum(
        'PENDING', 'RUNNING', 'PAUSED', 'STOPPED', 'COMPLETED', 'FAILED',
        name='pipeline_run_status',
    )
    pipeline_run_status.create(op.get_bind(), checkfirst=True)

    pipeline_phase = sa.Enum(
        'SEARCH', 'EXTRACTION', 'ENRICHMENT', 'VERIFICATION', 'CRM_PROMOTE', 'SMARTLEAD_PUSH',
        name='pipeline_phase',
    )
    pipeline_phase.create(op.get_bind(), checkfirst=True)

    pipeline_phase_status = sa.Enum(
        'STARTED', 'COMPLETED', 'FAILED', 'SKIPPED',
        name='pipeline_phase_status',
    )
    pipeline_phase_status.create(op.get_bind(), checkfirst=True)

    # pipeline_runs
    op.create_table(
        'pipeline_runs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('company_id', sa.Integer(), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', pipeline_run_status, nullable=False, server_default='PENDING'),
        sa.Column('current_phase', pipeline_phase, nullable=True),
        sa.Column('config', postgresql.JSONB(), nullable=True),
        sa.Column('progress', postgresql.JSONB(), nullable=True),
        sa.Column('total_cost_usd', sa.Numeric(10, 4), server_default='0'),
        sa.Column('budget_limit_usd', sa.Numeric(10, 4), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_pipeline_runs_project_id', 'pipeline_runs', ['project_id'])

    # pipeline_phase_logs
    op.create_table(
        'pipeline_phase_logs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('pipeline_run_id', sa.Integer(), sa.ForeignKey('pipeline_runs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('phase', pipeline_phase, nullable=False),
        sa.Column('status', pipeline_phase_status, nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('stats', postgresql.JSONB(), nullable=True),
        sa.Column('cost_usd', sa.Numeric(10, 4), server_default='0'),
        sa.Column('error_message', sa.Text(), nullable=True),
    )
    op.create_index('ix_pipeline_phase_logs_run_id', 'pipeline_phase_logs', ['pipeline_run_id'])

    # cost_events
    op.create_table(
        'cost_events',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('pipeline_run_id', sa.Integer(), sa.ForeignKey('pipeline_runs.id', ondelete='SET NULL'), nullable=True),
        sa.Column('service', sa.String(50), nullable=False),
        sa.Column('units', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('cost_usd', sa.Numeric(10, 6), nullable=False, server_default='0'),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_cost_events_project_id', 'cost_events', ['project_id'])


def downgrade() -> None:
    op.drop_table('cost_events')
    op.drop_table('pipeline_phase_logs')
    op.drop_table('pipeline_runs')

    sa.Enum(name='pipeline_phase_status').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='pipeline_phase').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='pipeline_run_status').drop(op.get_bind(), checkfirst=True)
