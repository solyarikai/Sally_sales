"""Migrate existing data to default user and company

This migration assigns all existing data (with NULL company_id/user_id)
to a default user and company, ensuring data integrity after the
multi-tenant schema changes.

Revision ID: 202601250200
Revises: 202601250100
Create Date: 2026-01-25
"""
from alembic import op
from sqlalchemy import text


revision = '202601250200'
down_revision = '202601250100'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    
    # 1. Create default user if none exists
    result = conn.execute(text("SELECT id FROM users LIMIT 1"))
    user = result.fetchone()
    
    if not user:
        conn.execute(text("""
            INSERT INTO users (name, email, is_active, created_at, updated_at)
            VALUES ('Default User', 'user@leadgen.local', true, NOW(), NOW())
        """))
        result = conn.execute(text("SELECT id FROM users WHERE email = 'user@leadgen.local'"))
        user = result.fetchone()
    
    user_id = user[0]
    
    # 2. Create default company if user has no companies
    result = conn.execute(text(
        "SELECT id FROM companies WHERE user_id = :uid AND deleted_at IS NULL LIMIT 1"
    ), {"uid": user_id})
    company = result.fetchone()
    
    if not company:
        conn.execute(text("""
            INSERT INTO companies (user_id, name, color, is_active, created_at, updated_at)
            VALUES (:uid, 'My Company', '#3B82F6', true, NOW(), NOW())
        """), {"uid": user_id})
        result = conn.execute(text(
            "SELECT id FROM companies WHERE user_id = :uid AND deleted_at IS NULL LIMIT 1"
        ), {"uid": user_id})
        company = result.fetchone()
    
    company_id = company[0]
    
    # 3. Migrate all data with NULL company_id to the default company
    tables_with_company_id = [
        'datasets',
        'folders',
        'prospects',
        'kb_documents',
        'kb_document_folders',
        'kb_company_profile',
        'kb_products',
        'kb_segments',
        'kb_segment_columns',
        'kb_competitors',
        'kb_case_studies',
        'kb_voice_tones',
        'kb_booking_links',
        'kb_blocklist'
    ]
    
    for table in tables_with_company_id:
        # Check if table exists before updating
        result = conn.execute(text(f"""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = '{table}'
            )
        """))
        table_exists = result.scalar()
        
        if table_exists:
            conn.execute(text(f"""
                UPDATE {table} SET company_id = :cid WHERE company_id IS NULL
            """), {"cid": company_id})
    
    # 4. Migrate prompt_templates to default user (non-system templates)
    result = conn.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'prompt_templates'
        )
    """))
    if result.scalar():
        conn.execute(text("""
            UPDATE prompt_templates 
            SET user_id = :uid 
            WHERE user_id IS NULL AND (is_system = false OR is_system IS NULL)
        """), {"uid": user_id})
    
    # 5. Migrate integration_settings to default user
    result = conn.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'integration_settings'
        )
    """))
    if result.scalar():
        conn.execute(text("""
            UPDATE integration_settings 
            SET user_id = :uid 
            WHERE user_id IS NULL
        """), {"uid": user_id})
    
    # 6. Log this migration as an activity
    conn.execute(text("""
        INSERT INTO user_activity_logs (user_id, company_id, action, entity_type, details, created_at)
        VALUES (:uid, :cid, 'migrate', 'system', '{"migration": "202601250200_migrate_existing_data"}'::jsonb, NOW())
    """), {"uid": user_id, "cid": company_id})


def downgrade() -> None:
    # This migration is not fully reversible.
    # The data will remain associated with the default user/company.
    # Manual intervention would be required to restore previous NULL state
    # if that was ever needed (which would break the application).
    pass
