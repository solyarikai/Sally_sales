"""add performance indexes

Revision ID: 202602010300
Revises: 202602010200
Create Date: 2026-02-01 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '202602010300'
down_revision = '202602010200'
branch_labels = None
depends_on = None


def upgrade():
    # Use raw SQL with IF NOT EXISTS for idempotent index creation
    connection = op.get_bind()
    
    # Contacts table indexes for filtering and search
    connection.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_contacts_company_id_deleted_at ON contacts (company_id, deleted_at)"))
    connection.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_contacts_project_id ON contacts (project_id)"))
    connection.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_contacts_segment ON contacts (segment)"))
    connection.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_contacts_status ON contacts (status)"))
    connection.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_contacts_source ON contacts (source)"))
    
    # ProcessedReply table indexes for dashboard queries
    connection.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_processed_replies_automation_id ON processed_replies (automation_id)"))
    connection.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_processed_replies_processed_at ON processed_replies (processed_at)"))
    connection.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_processed_replies_approval_status ON processed_replies (approval_status)"))
    
    # ReplyAutomation indexes
    connection.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_reply_automations_active ON reply_automations (active)"))
    connection.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_reply_automations_is_active ON reply_automations (is_active)"))
    
    # Projects table indexes
    connection.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_projects_company_id_deleted_at ON projects (company_id, deleted_at)"))


def downgrade():
    connection = op.get_bind()
    
    connection.execute(sa.text("DROP INDEX IF EXISTS ix_projects_company_id_deleted_at"))
    connection.execute(sa.text("DROP INDEX IF EXISTS ix_reply_automations_is_active"))
    connection.execute(sa.text("DROP INDEX IF EXISTS ix_reply_automations_active"))
    connection.execute(sa.text("DROP INDEX IF EXISTS ix_processed_replies_approval_status"))
    connection.execute(sa.text("DROP INDEX IF EXISTS ix_processed_replies_processed_at"))
    connection.execute(sa.text("DROP INDEX IF EXISTS ix_processed_replies_automation_id"))
    connection.execute(sa.text("DROP INDEX IF EXISTS ix_contacts_source"))
    connection.execute(sa.text("DROP INDEX IF EXISTS ix_contacts_status"))
    connection.execute(sa.text("DROP INDEX IF EXISTS ix_contacts_segment"))
    connection.execute(sa.text("DROP INDEX IF EXISTS ix_contacts_project_id"))
    connection.execute(sa.text("DROP INDEX IF EXISTS ix_contacts_company_id_deleted_at"))
