"""Add project reports tables for Sally Bot reporting system.

Revision ID: 202603171000
Revises: 202603162000
Create Date: 2026-03-17 10:00:00

Tables added:
- project_reports: Daily reports from project leads
- project_plans: Client-facing project plans
- project_progress_items: Plan items for progress tracking
- project_report_subscriptions: Lead/boss subscriptions for report notifications

Columns added:
- projects.report_config: JSON config for evening questions
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '202603171000'
down_revision = '202603162000'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── project_reports: Daily reports from leads ──
    op.create_table(
        'project_reports',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True),

        # Lead info
        sa.Column('lead_chat_id', sa.String(100), nullable=False, index=True),
        sa.Column('lead_username', sa.String(100), nullable=True),
        sa.Column('lead_first_name', sa.String(100), nullable=True),

        # Report content
        sa.Column('report_date', sa.Date(), nullable=False, index=True),
        sa.Column('report_text', sa.Text(), nullable=False),
        sa.Column('ai_summary', sa.Text(), nullable=True),

        # Forwarding status
        sa.Column('forwarded_to_boss', sa.Boolean(), default=False, nullable=False),
        sa.Column('forwarded_at', sa.DateTime(), nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    # Unique: one report per project/lead/date
    op.create_unique_constraint(
        'uq_project_reports_project_lead_date',
        'project_reports',
        ['project_id', 'lead_chat_id', 'report_date']
    )

    # ── project_plans: Plans for clients ──
    op.create_table(
        'project_plans',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True),

        # Uploader info
        sa.Column('uploaded_by_chat_id', sa.String(100), nullable=True),
        sa.Column('uploaded_by_username', sa.String(100), nullable=True),

        # Plan content
        sa.Column('title', sa.String(500), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('content_type', sa.String(20), default='text', nullable=False),  # text | document
        sa.Column('file_id', sa.String(255), nullable=True),  # Telegram file_id for documents

        # Version control
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('version', sa.Integer(), default=1, nullable=False),

        # AI-parsed items from plan
        sa.Column('ai_parsed_items', sa.JSON(), nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), onupdate=sa.func.now()),
    )

    op.create_index('ix_project_plans_active', 'project_plans', ['project_id', 'is_active'])

    # ── project_progress_items: Plan items for tracking ──
    op.create_table(
        'project_progress_items',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('plan_id', sa.Integer(), sa.ForeignKey('project_plans.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True),

        # Item content
        sa.Column('item_text', sa.Text(), nullable=False),
        sa.Column('due_date', sa.Date(), nullable=True),
        sa.Column('priority', sa.String(20), nullable=True),  # high | medium | low
        sa.Column('category', sa.String(100), nullable=True),  # e.g., development, design, testing

        # Status tracking
        sa.Column('status', sa.String(20), default='pending', nullable=False),  # pending | in_progress | completed | blocked
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('completed_by_report_id', sa.Integer(), sa.ForeignKey('project_reports.id', ondelete='SET NULL'), nullable=True),

        # AI confidence in matching report to this item
        sa.Column('ai_match_confidence', sa.Float(), nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), onupdate=sa.func.now()),
    )

    op.create_index('ix_progress_items_status', 'project_progress_items', ['project_id', 'status'])

    # ── project_report_subscriptions: Who sends/receives reports ──
    op.create_table(
        'project_report_subscriptions',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True),

        # Subscriber info
        sa.Column('chat_id', sa.String(100), nullable=False, index=True),
        sa.Column('username', sa.String(100), nullable=True),
        sa.Column('first_name', sa.String(100), nullable=True),

        # Role: lead (submits reports) | boss (receives reports)
        sa.Column('role', sa.String(20), nullable=False),  # lead | boss

        # Schedule config
        sa.Column('report_time', sa.Time(), nullable=True),  # When to ask for report (for leads)
        sa.Column('timezone', sa.String(50), default='Europe/Moscow', nullable=False),

        # Status
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('last_asked_at', sa.DateTime(), nullable=True),
        sa.Column('last_reported_at', sa.DateTime(), nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    # Unique: one subscription per project/chat/role
    op.create_unique_constraint(
        'uq_report_subscriptions_project_chat_role',
        'project_report_subscriptions',
        ['project_id', 'chat_id', 'role']
    )

    op.create_index('ix_report_subs_role', 'project_report_subscriptions', ['role', 'is_active'])

    # ── Add report_config to projects table ──
    op.add_column('projects', sa.Column('report_config', sa.JSON(), nullable=True))


def downgrade() -> None:
    # Drop report_config from projects
    op.drop_column('projects', 'report_config')

    # Drop project_report_subscriptions
    op.drop_index('ix_report_subs_role', table_name='project_report_subscriptions')
    op.drop_constraint('uq_report_subscriptions_project_chat_role', 'project_report_subscriptions', type_='unique')
    op.drop_table('project_report_subscriptions')

    # Drop project_progress_items
    op.drop_index('ix_progress_items_status', table_name='project_progress_items')
    op.drop_table('project_progress_items')

    # Drop project_plans
    op.drop_index('ix_project_plans_active', table_name='project_plans')
    op.drop_table('project_plans')

    # Drop project_reports
    op.drop_constraint('uq_project_reports_project_lead_date', 'project_reports', type_='unique')
    op.drop_table('project_reports')
