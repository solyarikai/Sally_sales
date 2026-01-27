"""Refactor knowledge base - new structure

Revision ID: 202601240600
Revises: 202601231900
Create Date: 2026-01-24
"""
from alembic import op
import sqlalchemy as sa


revision = '202601240600'
down_revision = '202601231900'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create document folders table
    op.create_table(
        'kb_document_folders',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('parent_id', sa.Integer(), sa.ForeignKey('kb_document_folders.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    
    # Add folder_id to documents
    op.add_column('kb_documents', sa.Column('folder_id', sa.Integer(), sa.ForeignKey('kb_document_folders.id'), nullable=True))
    
    # Create products table
    op.create_table(
        'kb_products',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('features', sa.JSON(), nullable=True),
        sa.Column('pricing', sa.JSON(), nullable=True),
        sa.Column('target_segment_ids', sa.JSON(), nullable=True),
        sa.Column('email_snippet', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('sort_order', sa.Integer(), default=0),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )
    
    # Create segment columns table
    op.create_table(
        'kb_segment_columns',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('display_name', sa.String(255), nullable=False),
        sa.Column('column_type', sa.String(50), default='text'),
        sa.Column('is_system', sa.Boolean(), default=False),
        sa.Column('is_required', sa.Boolean(), default=False),
        sa.Column('sort_order', sa.Integer(), default=0),
        sa.Column('options', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    
    # Modify segments table - add data column if not exists
    op.add_column('kb_segments', sa.Column('data', sa.JSON(), default=dict, nullable=True))
    op.add_column('kb_segments', sa.Column('sort_order', sa.Integer(), default=0, nullable=True))
    
    # Add email column to blocklist
    op.add_column('kb_blocklist', sa.Column('email', sa.String(255), nullable=True))
    
    # Modify booking_links - simplify
    op.add_column('kb_booking_links', sa.Column('when_to_use', sa.Text(), nullable=True))
    
    # Remove segment_id from case_studies (segments will reference cases now)
    try:
        op.drop_column('kb_case_studies', 'segment_id')
    except:
        pass  # Column might not exist


def downgrade() -> None:
    op.drop_column('kb_booking_links', 'when_to_use')
    op.drop_column('kb_blocklist', 'email')
    op.drop_column('kb_segments', 'data')
    op.drop_column('kb_segments', 'sort_order')
    op.drop_table('kb_segment_columns')
    op.drop_table('kb_products')
    op.drop_column('kb_documents', 'folder_id')
    op.drop_table('kb_document_folders')
