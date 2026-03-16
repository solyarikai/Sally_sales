"""Add meetings table for Calendly integration.

Revision ID: 202603161900
Revises: 202603161800
Create Date: 2026-03-16 19:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '202603161900'
down_revision = '202603161800'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'meetings',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),

        # Ownership
        sa.Column('company_id', sa.Integer(), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('contact_id', sa.Integer(), sa.ForeignKey('contacts.id', ondelete='SET NULL'), nullable=True),

        # Calendly identifiers
        sa.Column('calendly_event_uri', sa.String(500), nullable=True, unique=True, index=True),
        sa.Column('calendly_invitee_uri', sa.String(500), nullable=True),

        # Invitee info
        sa.Column('invitee_name', sa.String(255), nullable=False),
        sa.Column('invitee_email', sa.String(255), nullable=True, index=True),
        sa.Column('invitee_company', sa.String(500), nullable=True),
        sa.Column('invitee_title', sa.String(500), nullable=True),

        # Meeting details
        sa.Column('event_type_name', sa.String(255), nullable=True),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column('duration_minutes', sa.Integer(), default=30),
        sa.Column('meeting_link', sa.String(1000), nullable=True),
        sa.Column('location', sa.String(500), nullable=True),

        # Host info
        sa.Column('host_name', sa.String(255), nullable=True),
        sa.Column('host_email', sa.String(255), nullable=True),

        # Status
        sa.Column('status', sa.String(20), default='scheduled', nullable=False),
        sa.Column('outcome', sa.String(20), nullable=True),

        # Notes
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('client_notes', sa.Text(), nullable=True),
        sa.Column('cancellation_reason', sa.Text(), nullable=True),

        # Source tracking
        sa.Column('channel', sa.String(50), nullable=True),
        sa.Column('segment', sa.String(255), nullable=True),
        sa.Column('campaign_name', sa.String(500), nullable=True),

        # Invitee questions
        sa.Column('invitee_questions', sa.Text(), nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
    )

    # Composite indexes
    op.create_index('ix_meetings_project_scheduled', 'meetings', ['project_id', 'scheduled_at'])
    op.create_index('ix_meetings_status', 'meetings', ['status'])
    op.create_index('ix_meetings_company_project', 'meetings', ['company_id', 'project_id'])


def downgrade() -> None:
    op.drop_index('ix_meetings_company_project', table_name='meetings')
    op.drop_index('ix_meetings_status', table_name='meetings')
    op.drop_index('ix_meetings_project_scheduled', table_name='meetings')
    op.drop_table('meetings')
