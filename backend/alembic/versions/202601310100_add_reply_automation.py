"""Add reply automation tables

Revision ID: 202601310100
Revises: 202601270100_add_soft_delete_fields
Create Date: 2026-01-31 01:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '202601310100'
down_revision = '202601270100_add_soft_delete_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create reply_automations table
    op.create_table(
        'reply_automations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=True),
        sa.Column('environment_id', sa.Integer(), nullable=True),
        sa.Column('campaign_ids', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('slack_webhook_url', sa.String(length=500), nullable=True),
        sa.Column('slack_channel', sa.String(length=100), nullable=True),
        sa.Column('auto_classify', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('auto_generate_reply', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['environment_id'], ['environments.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_reply_automations_id', 'reply_automations', ['id'], unique=False)
    op.create_index('ix_reply_automations_is_active', 'reply_automations', ['is_active'], unique=False)
    op.create_index('ix_reply_automations_deleted_at', 'reply_automations', ['deleted_at'], unique=False)

    # Create processed_replies table
    op.create_table(
        'processed_replies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('automation_id', sa.Integer(), nullable=True),
        sa.Column('campaign_id', sa.String(length=100), nullable=True),
        sa.Column('campaign_name', sa.String(length=255), nullable=True),
        sa.Column('lead_email', sa.String(length=255), nullable=False),
        sa.Column('lead_first_name', sa.String(length=100), nullable=True),
        sa.Column('lead_last_name', sa.String(length=100), nullable=True),
        sa.Column('lead_company', sa.String(length=255), nullable=True),
        sa.Column('email_subject', sa.String(length=500), nullable=True),
        sa.Column('email_body', sa.Text(), nullable=True),
        sa.Column('reply_text', sa.Text(), nullable=True),
        sa.Column('received_at', sa.DateTime(), nullable=True),
        sa.Column('category', sa.String(length=50), nullable=True),
        sa.Column('category_confidence', sa.String(length=20), nullable=True),
        sa.Column('classification_reasoning', sa.Text(), nullable=True),
        sa.Column('draft_reply', sa.Text(), nullable=True),
        sa.Column('draft_subject', sa.String(length=500), nullable=True),
        sa.Column('processed_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('sent_to_slack', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('slack_sent_at', sa.DateTime(), nullable=True),
        sa.Column('slack_message_ts', sa.String(length=50), nullable=True),
        sa.Column('raw_webhook_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['automation_id'], ['reply_automations.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_processed_replies_id', 'processed_replies', ['id'], unique=False)
    op.create_index('ix_processed_replies_campaign_id', 'processed_replies', ['campaign_id'], unique=False)
    op.create_index('ix_processed_replies_lead_email', 'processed_replies', ['lead_email'], unique=False)
    op.create_index('ix_processed_replies_category', 'processed_replies', ['category'], unique=False)


def downgrade() -> None:
    op.drop_table('processed_replies')
    op.drop_table('reply_automations')
