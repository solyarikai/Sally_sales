"""Datamodel evolution: campaigns table, channel_accounts table, clean Contact model.

New tables:
  - campaigns: first-class campaign registry per project
  - channel_accounts: sender identities per platform

Contact changes:
  - ADD provenance (JSON) — renamed from gathering_details
  - ADD platform_state (JSON) — consolidates smartlead_status, getsales_status,
    smartlead_raw, getsales_raw, last_synced_at, campaigns JSON
  - MIGRATE gathering_details → provenance
  - MIGRATE platform-specific columns → platform_state
  - Old columns kept in DB for safety (not dropped)

OperatorTask changes:
  - ADD meeting_at, meeting_link, meeting_outcome, booking_link_id

Revision ID: e1f2a3b4c5d6
Revises: d8e2f3a4b5c6
Create Date: 2026-02-25 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON


# revision identifiers, used by Alembic.
revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, None] = '202602200400'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    campaigns_exists = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.tables WHERE table_name='campaigns'"
    )).scalar()

    if campaigns_exists:
        # ── 1a. ALTER existing campaigns table to match new schema ──
        cols = {r[0] for r in conn.execute(sa.text(
            "SELECT column_name FROM information_schema.columns WHERE table_name='campaigns'"
        )).fetchall()}

        if 'source' in cols and 'platform' not in cols:
            op.alter_column('campaigns', 'source', new_column_name='platform')
        if 'lead_count' in cols and 'leads_count' not in cols:
            op.alter_column('campaigns', 'lead_count', new_column_name='leads_count')

        if 'project_id' not in cols:
            op.add_column('campaigns', sa.Column('project_id', sa.Integer(),
                          sa.ForeignKey('projects.id', ondelete='SET NULL'), nullable=True))
        if 'push_rule_id' not in cols:
            op.add_column('campaigns', sa.Column('push_rule_id', sa.Integer(),
                          sa.ForeignKey('campaign_push_rules.id', ondelete='SET NULL'), nullable=True))
        if 'config' not in cols:
            op.add_column('campaigns', sa.Column('config', JSON, nullable=True))
        if 'leads_count' not in cols and 'lead_count' not in cols:
            op.add_column('campaigns', sa.Column('leads_count', sa.Integer(), server_default='0'))

        # Make external_id nullable (model allows NULL)
        op.alter_column('campaigns', 'external_id', nullable=True)

        # Add server defaults to timestamp columns if missing
        op.alter_column('campaigns', 'created_at', server_default=sa.func.now())
        op.alter_column('campaigns', 'updated_at', server_default=sa.func.now())

        # Add missing indexes (idempotent via IF NOT EXISTS)
        op.execute("CREATE INDEX IF NOT EXISTS ix_campaigns_project ON campaigns (project_id)")
        op.execute("CREATE INDEX IF NOT EXISTS ix_campaigns_company ON campaigns (company_id)")
        op.execute("CREATE INDEX IF NOT EXISTS ix_campaigns_name ON campaigns (name)")
        op.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_campaign_platform_ext
            ON campaigns (platform, external_id)
            WHERE external_id IS NOT NULL
        """)
    else:
        # ── 1b. Create campaigns table from scratch ──
        op.create_table(
            'campaigns',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('company_id', sa.Integer(), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False),
            sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='SET NULL'), nullable=True),
            sa.Column('platform', sa.String(50), nullable=False),
            sa.Column('channel', sa.String(50), nullable=False),
            sa.Column('external_id', sa.String(255), nullable=True),
            sa.Column('name', sa.String(500), nullable=False),
            sa.Column('status', sa.String(50), server_default='active'),
            sa.Column('push_rule_id', sa.Integer(), sa.ForeignKey('campaign_push_rules.id', ondelete='SET NULL'), nullable=True),
            sa.Column('leads_count', sa.Integer(), server_default='0'),
            sa.Column('replied_count', sa.Integer(), server_default='0'),
            sa.Column('config', JSON, nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        )
        op.create_index('ix_campaigns_project', 'campaigns', ['project_id'])
        op.create_index('ix_campaigns_company', 'campaigns', ['company_id'])
        op.create_index('ix_campaigns_name', 'campaigns', ['name'])
        op.execute("""
            CREATE UNIQUE INDEX uq_campaign_platform_ext
            ON campaigns (platform, external_id)
            WHERE external_id IS NOT NULL
        """)

    # ── 2. Create channel_accounts table (if not exists) ──
    ca_exists = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.tables WHERE table_name='channel_accounts'"
    )).scalar()
    if not ca_exists:
        op.create_table(
            'channel_accounts',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('company_id', sa.Integer(), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False),
            sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='SET NULL'), nullable=True),
            sa.Column('platform', sa.String(50), nullable=False),
            sa.Column('channel', sa.String(50), nullable=False),
            sa.Column('external_id', sa.String(255), nullable=False),
            sa.Column('display_name', sa.String(255), nullable=False),
            sa.Column('email', sa.String(255), nullable=True),
            sa.Column('profile_url', sa.String(500), nullable=True),
            sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
            sa.Column('metadata', JSON, nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        )
        op.create_index('ix_ca_project', 'channel_accounts', ['project_id'])
        op.execute("""
            CREATE UNIQUE INDEX uq_channel_account
            ON channel_accounts (platform, external_id)
        """)

    # ── 3. Add new columns to contacts (idempotent) ──
    contact_cols = {r[0] for r in conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns WHERE table_name='contacts'"
    )).fetchall()}
    if 'provenance' not in contact_cols:
        op.add_column('contacts', sa.Column('provenance', JSON, nullable=True))
    if 'platform_state' not in contact_cols:
        op.add_column('contacts', sa.Column('platform_state', JSON, nullable=True))

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_contacts_replied
        ON contacts (last_reply_at)
        WHERE last_reply_at IS NOT NULL
    """)

    # ── 4. Add meeting fields to operator_tasks (idempotent) ──
    task_cols = {r[0] for r in conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns WHERE table_name='operator_tasks'"
    )).fetchall()}
    if 'meeting_at' not in task_cols:
        op.add_column('operator_tasks', sa.Column('meeting_at', sa.DateTime(timezone=True), nullable=True))
    if 'meeting_link' not in task_cols:
        op.add_column('operator_tasks', sa.Column('meeting_link', sa.String(500), nullable=True))
    if 'meeting_outcome' not in task_cols:
        op.add_column('operator_tasks', sa.Column('meeting_outcome', sa.Text(), nullable=True))
    if 'booking_link_id' not in task_cols:
        op.add_column('operator_tasks', sa.Column('booking_link_id', sa.Integer(),
                      sa.ForeignKey('kb_booking_links.id', ondelete='SET NULL'), nullable=True))

    # ── 5. Data migration: gathering_details → provenance ──
    op.execute("""
        UPDATE contacts
        SET provenance = gathering_details
        WHERE gathering_details IS NOT NULL
          AND provenance IS NULL
    """)

    # ── 6. Data migration: build platform_state from old columns ──
    op.execute("""
        UPDATE contacts
        SET platform_state = (
            CASE
                WHEN smartlead_id IS NOT NULL AND getsales_id IS NOT NULL THEN
                    jsonb_build_object(
                        'smartlead', jsonb_build_object(
                            'status', smartlead_status,
                            'last_synced', to_char(last_synced_at, 'YYYY-MM-DD"T"HH24:MI:SS'),
                            'campaigns', COALESCE(
                                (SELECT jsonb_agg(c) FROM jsonb_array_elements(
                                    CASE WHEN campaigns IS NOT NULL AND campaigns::text != 'null'
                                         THEN campaigns::jsonb ELSE '[]'::jsonb END
                                ) c WHERE c->>'source' = 'smartlead'),
                                '[]'::jsonb
                            )
                        ),
                        'getsales', jsonb_build_object(
                            'status', getsales_status,
                            'last_synced', to_char(last_synced_at, 'YYYY-MM-DD"T"HH24:MI:SS'),
                            'campaigns', COALESCE(
                                (SELECT jsonb_agg(c) FROM jsonb_array_elements(
                                    CASE WHEN campaigns IS NOT NULL AND campaigns::text != 'null'
                                         THEN campaigns::jsonb ELSE '[]'::jsonb END
                                ) c WHERE c->>'source' = 'getsales'),
                                '[]'::jsonb
                            )
                        )
                    )
                WHEN smartlead_id IS NOT NULL THEN
                    jsonb_build_object(
                        'smartlead', jsonb_build_object(
                            'status', smartlead_status,
                            'last_synced', to_char(last_synced_at, 'YYYY-MM-DD"T"HH24:MI:SS'),
                            'campaigns', COALESCE(
                                (SELECT jsonb_agg(c) FROM jsonb_array_elements(
                                    CASE WHEN campaigns IS NOT NULL AND campaigns::text != 'null'
                                         THEN campaigns::jsonb ELSE '[]'::jsonb END
                                ) c WHERE c->>'source' = 'smartlead'),
                                '[]'::jsonb
                            )
                        )
                    )
                WHEN getsales_id IS NOT NULL THEN
                    jsonb_build_object(
                        'getsales', jsonb_build_object(
                            'status', getsales_status,
                            'last_synced', to_char(last_synced_at, 'YYYY-MM-DD"T"HH24:MI:SS'),
                            'campaigns', COALESCE(
                                (SELECT jsonb_agg(c) FROM jsonb_array_elements(
                                    CASE WHEN campaigns IS NOT NULL AND campaigns::text != 'null'
                                         THEN campaigns::jsonb ELSE '[]'::jsonb END
                                ) c WHERE c->>'source' = 'getsales'),
                                '[]'::jsonb
                            )
                        )
                    )
                ELSE NULL
            END
        )
        WHERE platform_state IS NULL
          AND (smartlead_id IS NOT NULL OR getsales_id IS NOT NULL)
    """)

    # ── 7. Backfill campaigns table from Contact.campaigns JSON ──
    op.execute("""
        INSERT INTO campaigns (company_id, project_id, platform, channel, external_id, name, status, created_at, updated_at)
        SELECT DISTINCT ON (c_data->>'source', c_data->>'id')
            COALESCE(ct.company_id, 1) as company_id,
            ct.project_id,
            CASE WHEN c_data->>'source' = 'getsales' THEN 'getsales' ELSE 'smartlead' END as platform,
            CASE WHEN c_data->>'source' = 'getsales' THEN 'linkedin' ELSE 'email' END as channel,
            c_data->>'id' as external_id,
            c_data->>'name' as name,
            COALESCE(c_data->>'status', 'active') as status,
            NOW(),
            NOW()
        FROM contacts ct,
             jsonb_array_elements(
                 CASE WHEN ct.campaigns IS NOT NULL AND ct.campaigns::text != 'null'
                      THEN ct.campaigns::jsonb ELSE '[]'::jsonb END
             ) as c_data
        WHERE c_data->>'name' IS NOT NULL
          AND c_data->>'id' IS NOT NULL
          AND ct.deleted_at IS NULL
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    # Remove meeting fields from operator_tasks
    op.drop_column('operator_tasks', 'booking_link_id')
    op.drop_column('operator_tasks', 'meeting_outcome')
    op.drop_column('operator_tasks', 'meeting_link')
    op.drop_column('operator_tasks', 'meeting_at')

    # Remove new contact columns
    op.execute("DROP INDEX IF EXISTS ix_contacts_replied")
    op.drop_column('contacts', 'platform_state')
    op.drop_column('contacts', 'provenance')

    # Drop new tables
    op.drop_table('channel_accounts')
    op.drop_table('campaigns')
