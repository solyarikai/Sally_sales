"""Add outreach_stats table for tracking plan vs fact.

Revision ID: 202603162000
Revises: 202603161900
Create Date: 2026-03-16 20:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '202603162000'
down_revision = '202603161900'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'outreach_stats',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),

        # Ownership
        sa.Column('company_id', sa.Integer(), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True),

        # Period
        sa.Column('period_start', sa.Date(), nullable=False),
        sa.Column('period_end', sa.Date(), nullable=False),

        # Channel and segment
        sa.Column('channel', sa.String(50), nullable=False),
        sa.Column('segment', sa.String(255), nullable=False),

        # Plan
        sa.Column('plan_contacts', sa.Integer(), default=0),

        # Fact
        sa.Column('contacts_sent', sa.Integer(), default=0),
        sa.Column('contacts_accepted', sa.Integer(), default=0),
        sa.Column('replies_count', sa.Integer(), default=0),
        sa.Column('positive_replies', sa.Integer(), default=0),
        sa.Column('meetings_scheduled', sa.Integer(), default=0),
        sa.Column('meetings_completed', sa.Integer(), default=0),

        # Rates
        sa.Column('reply_rate', sa.Float(), default=0.0),
        sa.Column('positive_rate', sa.Float(), default=0.0),
        sa.Column('accept_rate', sa.Float(), default=0.0),
        sa.Column('meeting_rate', sa.Float(), default=0.0),

        # Source tracking
        sa.Column('is_manual', sa.Integer(), default=0),
        sa.Column('data_source', sa.String(50), nullable=True),

        # Notes
        sa.Column('notes', sa.Text(), nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True),
    )

    # Unique constraint
    op.create_unique_constraint(
        'uq_outreach_stats_period_channel_segment',
        'outreach_stats',
        ['project_id', 'period_start', 'period_end', 'channel', 'segment']
    )

    # Indexes
    op.create_index('ix_outreach_stats_project_period', 'outreach_stats', ['project_id', 'period_start', 'period_end'])
    op.create_index('ix_outreach_stats_channel', 'outreach_stats', ['channel'])


def downgrade() -> None:
    op.drop_index('ix_outreach_stats_channel', table_name='outreach_stats')
    op.drop_index('ix_outreach_stats_project_period', table_name='outreach_stats')
    op.drop_constraint('uq_outreach_stats_period_channel_segment', 'outreach_stats', type_='unique')
    op.drop_table('outreach_stats')
