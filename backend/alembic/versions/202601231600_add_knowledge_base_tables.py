"""Add knowledge base tables

Revision ID: 202601231600
Revises: 108a107189d6
Create Date: 2026-01-23 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '202601231600'
down_revision: Union[str, None] = '108a107189d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Documents table
    op.create_table(
        'kb_documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('original_filename', sa.String(255), nullable=True),
        sa.Column('document_type', sa.String(50), nullable=True, default='other'),
        sa.Column('content_md', sa.Text(), nullable=True),
        sa.Column('raw_text', sa.Text(), nullable=True),
        sa.Column('status', sa.String(50), nullable=True, default='pending'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_kb_documents_id', 'kb_documents', ['id'])

    # Company Profile table
    op.create_table(
        'kb_company_profile',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('website', sa.String(255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('calendly_link', sa.String(255), nullable=True),
        sa.Column('linkedin_url', sa.String(255), nullable=True),
        sa.Column('tagline', sa.String(500), nullable=True),
        sa.Column('value_proposition', sa.Text(), nullable=True),
        sa.Column('products_services', sa.JSON(), nullable=True),
        sa.Column('pricing_model', sa.Text(), nullable=True),
        sa.Column('pricing_tiers', sa.JSON(), nullable=True),
        sa.Column('key_metrics', sa.JSON(), nullable=True),
        sa.Column('certifications', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Segments table
    op.create_table(
        'kb_segments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('employee_count_min', sa.Integer(), nullable=True),
        sa.Column('employee_count_max', sa.Integer(), nullable=True),
        sa.Column('revenue_min', sa.String(50), nullable=True),
        sa.Column('revenue_max', sa.String(50), nullable=True),
        sa.Column('example_companies', sa.JSON(), nullable=True),
        sa.Column('target_countries', sa.JSON(), nullable=True),
        sa.Column('target_job_titles', sa.JSON(), nullable=True),
        sa.Column('problems_we_solve', sa.JSON(), nullable=True),
        sa.Column('what_they_need', sa.JSON(), nullable=True),
        sa.Column('our_offer', sa.JSON(), nullable=True),
        sa.Column('differentiators', sa.JSON(), nullable=True),
        sa.Column('social_proof', sa.JSON(), nullable=True),
        sa.Column('cases', sa.JSON(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('priority', sa.Integer(), default=0),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_kb_segments_id', 'kb_segments', ['id'])

    # Competitors table
    op.create_table(
        'kb_competitors',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('website', sa.String(255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('their_strengths', sa.JSON(), nullable=True),
        sa.Column('their_weaknesses', sa.JSON(), nullable=True),
        sa.Column('our_advantages', sa.JSON(), nullable=True),
        sa.Column('customers_we_won', sa.JSON(), nullable=True),
        sa.Column('customers_we_lost', sa.JSON(), nullable=True),
        sa.Column('their_positioning', sa.Text(), nullable=True),
        sa.Column('price_comparison', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Case Studies table
    op.create_table(
        'kb_case_studies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('client_name', sa.String(255), nullable=False),
        sa.Column('client_website', sa.String(255), nullable=True),
        sa.Column('client_industry', sa.String(255), nullable=True),
        sa.Column('client_size', sa.String(100), nullable=True),
        sa.Column('challenge', sa.Text(), nullable=True),
        sa.Column('solution', sa.Text(), nullable=True),
        sa.Column('results', sa.Text(), nullable=True),
        sa.Column('key_metrics', sa.JSON(), nullable=True),
        sa.Column('testimonial', sa.Text(), nullable=True),
        sa.Column('testimonial_author', sa.String(255), nullable=True),
        sa.Column('testimonial_title', sa.String(255), nullable=True),
        sa.Column('segment_id', sa.Integer(), sa.ForeignKey('kb_segments.id'), nullable=True),
        sa.Column('email_snippet', sa.Text(), nullable=True),
        sa.Column('is_public', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Voice Tones table
    op.create_table(
        'kb_voice_tones',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('personality_traits', sa.JSON(), nullable=True),
        sa.Column('writing_style', sa.Text(), nullable=True),
        sa.Column('do_use', sa.JSON(), nullable=True),
        sa.Column('dont_use', sa.JSON(), nullable=True),
        sa.Column('example_messages', sa.JSON(), nullable=True),
        sa.Column('formality_level', sa.Integer(), default=5),
        sa.Column('emoji_usage', sa.Boolean(), default=False),
        sa.Column('is_default', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Blocklist table
    op.create_table(
        'kb_blocklist',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('domain', sa.String(255), nullable=False, unique=True),
        sa.Column('company_name', sa.String(255), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('kb_blocklist')
    op.drop_table('kb_voice_tones')
    op.drop_table('kb_case_studies')
    op.drop_table('kb_competitors')
    op.drop_index('ix_kb_segments_id', 'kb_segments')
    op.drop_table('kb_segments')
    op.drop_table('kb_company_profile')
    op.drop_index('ix_kb_documents_id', 'kb_documents')
    op.drop_table('kb_documents')
