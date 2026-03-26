"""add telegram outreach tables

Revision ID: 202603250100
Revises: 202603150200
Create Date: 2026-03-25 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '202603250100'
down_revision: Union[str, None] = '202603150200'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Enum values
tg_account_status_values = ('active', 'paused', 'spamblocked', 'dead', 'frozen')
tg_spamblock_type_values = ('none', 'temporary', 'permanent')
tg_proxy_protocol_values = ('http', 'socks5', 'mtproto')
tg_campaign_status_values = ('draft', 'active', 'paused', 'completed')
tg_recipient_status_values = ('pending', 'in_sequence', 'replied', 'completed', 'failed', 'bounced')
tg_message_status_values = ('sent', 'failed', 'spamblocked')


def upgrade() -> None:
    # ── Create enum types ──────────────────────────────────────────────
    op.execute("CREATE TYPE tgaccountstatus AS ENUM ('active', 'paused', 'spamblocked', 'dead', 'frozen')")
    op.execute("CREATE TYPE tgspamblocktype AS ENUM ('none', 'temporary', 'permanent')")
    op.execute("CREATE TYPE tgproxyprotocol AS ENUM ('http', 'socks5', 'mtproto')")
    op.execute("CREATE TYPE tgcampaignstatus AS ENUM ('draft', 'active', 'paused', 'completed')")
    op.execute("CREATE TYPE tgrecipientstatus AS ENUM ('pending', 'in_sequence', 'replied', 'completed', 'failed', 'bounced')")
    op.execute("CREATE TYPE tgmessagestatus AS ENUM ('sent', 'failed', 'spamblocked')")

    tg_account_status_enum = postgresql.ENUM(*tg_account_status_values, name='tgaccountstatus', create_type=False)
    tg_spamblock_type_enum = postgresql.ENUM(*tg_spamblock_type_values, name='tgspamblocktype', create_type=False)
    tg_proxy_protocol_enum = postgresql.ENUM(*tg_proxy_protocol_values, name='tgproxyprotocol', create_type=False)
    tg_campaign_status_enum = postgresql.ENUM(*tg_campaign_status_values, name='tgcampaignstatus', create_type=False)
    tg_recipient_status_enum = postgresql.ENUM(*tg_recipient_status_values, name='tgrecipientstatus', create_type=False)
    tg_message_status_enum = postgresql.ENUM(*tg_message_status_values, name='tgmessagestatus', create_type=False)

    # ── tg_proxy_groups ────────────────────────────────────────────────
    op.create_table('tg_proxy_groups',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('country', sa.String(length=50), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_tg_proxy_groups_id', 'tg_proxy_groups', ['id'])

    # ── tg_proxies ─────────────────────────────────────────────────────
    op.create_table('tg_proxies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('proxy_group_id', sa.Integer(), nullable=False),
        sa.Column('host', sa.String(length=255), nullable=False),
        sa.Column('port', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=100), nullable=True),
        sa.Column('password', sa.String(length=100), nullable=True),
        sa.Column('protocol', tg_proxy_protocol_enum, nullable=False, server_default='http'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('last_checked_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['proxy_group_id'], ['tg_proxy_groups.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_tg_proxies_id', 'tg_proxies', ['id'])
    op.create_index('ix_tg_proxies_group', 'tg_proxies', ['proxy_group_id'])

    # ── tg_account_tags ────────────────────────────────────────────────
    op.create_table('tg_account_tags',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False, unique=True),
        sa.Column('color', sa.String(length=20), nullable=False, server_default='#6366f1'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_tg_account_tags_id', 'tg_account_tags', ['id'])

    # ── tg_accounts ────────────────────────────────────────────────────
    op.create_table('tg_accounts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('phone', sa.String(length=20), nullable=False),
        sa.Column('username', sa.String(length=100), nullable=True),
        sa.Column('first_name', sa.String(length=100), nullable=True),
        sa.Column('last_name', sa.String(length=100), nullable=True),
        sa.Column('bio', sa.Text(), nullable=True),
        sa.Column('profile_photo_path', sa.String(length=500), nullable=True),
        sa.Column('api_id', sa.Integer(), nullable=True),
        sa.Column('api_hash', sa.String(length=100), nullable=True),
        sa.Column('device_model', sa.String(length=100), nullable=True, server_default='Samsung SM-G998B'),
        sa.Column('system_version', sa.String(length=50), nullable=True, server_default='SDK 33'),
        sa.Column('app_version', sa.String(length=50), nullable=True, server_default='10.6.2'),
        sa.Column('lang_code', sa.String(length=10), nullable=True, server_default='en'),
        sa.Column('system_lang_code', sa.String(length=10), nullable=True, server_default='en-US'),
        sa.Column('two_fa_password', sa.String(length=255), nullable=True),
        sa.Column('session_file', sa.String(length=500), nullable=True),
        sa.Column('proxy_group_id', sa.Integer(), nullable=True),
        sa.Column('assigned_proxy_id', sa.Integer(), nullable=True),
        sa.Column('status', tg_account_status_enum, nullable=False, server_default='active'),
        sa.Column('spamblock_type', tg_spamblock_type_enum, nullable=False, server_default='none'),
        sa.Column('daily_message_limit', sa.Integer(), nullable=False, server_default='10'),
        sa.Column('messages_sent_today', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_messages_sent', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_connected_at', sa.DateTime(), nullable=True),
        sa.Column('last_checked_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['proxy_group_id'], ['tg_proxy_groups.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['assigned_proxy_id'], ['tg_proxies.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_tg_accounts_id', 'tg_accounts', ['id'])
    op.create_index('ix_tg_accounts_phone', 'tg_accounts', ['phone'], unique=True)
    op.create_index('ix_tg_accounts_status', 'tg_accounts', ['status'])
    op.create_index('ix_tg_accounts_proxy_group', 'tg_accounts', ['proxy_group_id'])

    # ── tg_account_tag_links ───────────────────────────────────────────
    op.create_table('tg_account_tag_links',
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('tag_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['account_id'], ['tg_accounts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tag_id'], ['tg_account_tags.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('account_id', 'tag_id'),
    )

    # ── tg_campaigns ───────────────────────────────────────────────────
    op.create_table('tg_campaigns',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('status', tg_campaign_status_enum, nullable=False, server_default='draft'),
        sa.Column('daily_message_limit', sa.Integer(), nullable=True),
        sa.Column('timezone', sa.String(length=50), nullable=False, server_default='Europe/Moscow'),
        sa.Column('send_from_hour', sa.Integer(), nullable=False, server_default='9'),
        sa.Column('send_to_hour', sa.Integer(), nullable=False, server_default='18'),
        sa.Column('delay_between_sends_min', sa.Integer(), nullable=False, server_default='11'),
        sa.Column('delay_between_sends_max', sa.Integer(), nullable=False, server_default='25'),
        sa.Column('delay_randomness_percent', sa.Integer(), nullable=False, server_default='20'),
        sa.Column('spamblock_errors_to_skip', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('messages_sent_today', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_messages_sent', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_recipients', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_tg_campaigns_id', 'tg_campaigns', ['id'])
    op.create_index('ix_tg_campaigns_status', 'tg_campaigns', ['status'])

    # ── tg_campaign_accounts ───────────────────────────────────────────
    op.create_table('tg_campaign_accounts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('campaign_id', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('consecutive_spamblock_errors', sa.Integer(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['campaign_id'], ['tg_campaigns.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['account_id'], ['tg_accounts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('campaign_id', 'account_id', name='uq_tg_campaign_account'),
    )
    op.create_index('ix_tg_campaign_accounts_id', 'tg_campaign_accounts', ['id'])
    op.create_index('ix_tg_campaign_accounts_campaign', 'tg_campaign_accounts', ['campaign_id'])
    op.create_index('ix_tg_campaign_accounts_account', 'tg_campaign_accounts', ['account_id'])

    # ── tg_recipients ──────────────────────────────────────────────────
    op.create_table('tg_recipients',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('campaign_id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=100), nullable=False),
        sa.Column('first_name', sa.String(length=100), nullable=True),
        sa.Column('company_name', sa.String(length=255), nullable=True),
        sa.Column('custom_variables', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('status', tg_recipient_status_enum, nullable=False, server_default='pending'),
        sa.Column('current_step', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('assigned_account_id', sa.Integer(), nullable=True),
        sa.Column('next_message_at', sa.DateTime(), nullable=True),
        sa.Column('last_message_sent_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['campaign_id'], ['tg_campaigns.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['assigned_account_id'], ['tg_accounts.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_tg_recipients_id', 'tg_recipients', ['id'])
    op.create_index('ix_tg_recipients_campaign_status', 'tg_recipients', ['campaign_id', 'status'])
    op.create_index('ix_tg_recipients_next_msg', 'tg_recipients', ['next_message_at'],
                     postgresql_where=sa.text('next_message_at IS NOT NULL'))

    # ── tg_sequences ───────────────────────────────────────────────────
    op.create_table('tg_sequences',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('campaign_id', sa.Integer(), nullable=False, unique=True),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['campaign_id'], ['tg_campaigns.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_tg_sequences_id', 'tg_sequences', ['id'])

    # ── tg_sequence_steps ──────────────────────────────────────────────
    op.create_table('tg_sequence_steps',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('sequence_id', sa.Integer(), nullable=False),
        sa.Column('step_order', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('delay_days', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['sequence_id'], ['tg_sequences.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('sequence_id', 'step_order', name='uq_tg_sequence_step_order'),
    )
    op.create_index('ix_tg_sequence_steps_id', 'tg_sequence_steps', ['id'])
    op.create_index('ix_tg_sequence_steps_sequence', 'tg_sequence_steps', ['sequence_id'])

    # ── tg_step_variants ───────────────────────────────────────────────
    op.create_table('tg_step_variants',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('step_id', sa.Integer(), nullable=False),
        sa.Column('variant_label', sa.String(length=5), nullable=False, server_default='A'),
        sa.Column('message_text', sa.Text(), nullable=False, server_default=''),
        sa.Column('weight_percent', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['step_id'], ['tg_sequence_steps.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_tg_step_variants_id', 'tg_step_variants', ['id'])
    op.create_index('ix_tg_step_variants_step', 'tg_step_variants', ['step_id'])

    # ── tg_outreach_messages ───────────────────────────────────────────
    op.create_table('tg_outreach_messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('campaign_id', sa.Integer(), nullable=False),
        sa.Column('recipient_id', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=True),
        sa.Column('step_id', sa.Integer(), nullable=True),
        sa.Column('variant_id', sa.Integer(), nullable=True),
        sa.Column('rendered_text', sa.Text(), nullable=False),
        sa.Column('status', tg_message_status_enum, nullable=False, server_default='sent'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('sent_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['campaign_id'], ['tg_campaigns.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['recipient_id'], ['tg_recipients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['account_id'], ['tg_accounts.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['step_id'], ['tg_sequence_steps.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['variant_id'], ['tg_step_variants.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_tg_outreach_messages_id', 'tg_outreach_messages', ['id'])
    op.create_index('ix_tg_outreach_messages_campaign', 'tg_outreach_messages', ['campaign_id'])
    op.create_index('ix_tg_outreach_messages_recipient', 'tg_outreach_messages', ['recipient_id'])
    op.create_index('ix_tg_outreach_messages_account', 'tg_outreach_messages', ['account_id'])
    op.create_index('ix_tg_outreach_messages_sent', 'tg_outreach_messages', ['sent_at'])


def downgrade() -> None:
    op.drop_table('tg_outreach_messages')
    op.drop_table('tg_step_variants')
    op.drop_table('tg_sequence_steps')
    op.drop_table('tg_sequences')
    op.drop_table('tg_recipients')
    op.drop_table('tg_campaign_accounts')
    op.drop_table('tg_campaigns')
    op.drop_table('tg_account_tag_links')
    op.drop_table('tg_accounts')
    op.drop_table('tg_account_tags')
    op.drop_table('tg_proxies')
    op.drop_table('tg_proxy_groups')

    op.execute("DROP TYPE IF EXISTS tgmessagestatus")
    op.execute("DROP TYPE IF EXISTS tgrecipientstatus")
    op.execute("DROP TYPE IF EXISTS tgcampaignstatus")
    op.execute("DROP TYPE IF EXISTS tgproxyprotocol")
    op.execute("DROP TYPE IF EXISTS tgspamblocktype")
    op.execute("DROP TYPE IF EXISTS tgaccountstatus")
