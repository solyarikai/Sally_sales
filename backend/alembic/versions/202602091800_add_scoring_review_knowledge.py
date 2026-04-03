"""Add scoring, review, query effectiveness, and project knowledge tables

- search_results: scores (JSON), review_status, review_note, reviewed_at, source_query_id
- search_queries: targets_found, effectiveness_score
- New table: project_search_knowledge

Revision ID: a1b2c3d4e5f6
Revises: f8a3b2c1d4e5
Create Date: 2026-02-09 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f8a3b2c1d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- search_results: add scoring + review columns ---
    op.add_column('search_results', sa.Column('scores', sa.JSON(), nullable=True))
    op.add_column('search_results', sa.Column('review_status', sa.String(20), nullable=True))
    op.add_column('search_results', sa.Column('review_note', sa.Text(), nullable=True))
    op.add_column('search_results', sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('search_results', sa.Column('source_query_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_search_results_source_query_id',
        'search_results', 'search_queries',
        ['source_query_id'], ['id'],
        ondelete='SET NULL',
    )

    # --- search_queries: add effectiveness tracking ---
    op.add_column('search_queries', sa.Column('targets_found', sa.Integer(), server_default='0', nullable=True))
    op.add_column('search_queries', sa.Column('effectiveness_score', sa.Float(), nullable=True))

    # --- project_search_knowledge: new table ---
    op.create_table(
        'project_search_knowledge',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('total_jobs_run', sa.Integer(), server_default='0'),
        sa.Column('total_domains_analyzed', sa.Integer(), server_default='0'),
        sa.Column('total_targets_found', sa.Integer(), server_default='0'),
        sa.Column('total_false_positives', sa.Integer(), server_default='0'),
        sa.Column('good_query_patterns', sa.JSON(), server_default='[]'),
        sa.Column('bad_query_patterns', sa.JSON(), server_default='[]'),
        sa.Column('confirmed_domains', sa.JSON(), server_default='[]'),
        sa.Column('rejected_domains', sa.JSON(), server_default='[]'),
        sa.Column('industry_keywords', sa.JSON(), server_default='[]'),
        sa.Column('anti_keywords', sa.JSON(), server_default='[]'),
        sa.Column('avg_target_confidence', sa.Float(), nullable=True),
        sa.Column('avg_false_positive_confidence', sa.Float(), nullable=True),
        sa.Column('recommended_threshold', sa.Float(), server_default='0.5'),
        sa.Column('custom_exclusion_rules', sa.JSON(), server_default='[]'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_project_search_knowledge_project_id', 'project_search_knowledge', ['project_id'])


def downgrade() -> None:
    op.drop_table('project_search_knowledge')

    op.drop_column('search_queries', 'effectiveness_score')
    op.drop_column('search_queries', 'targets_found')

    op.drop_constraint('fk_search_results_source_query_id', 'search_results', type_='foreignkey')
    op.drop_column('search_results', 'source_query_id')
    op.drop_column('search_results', 'reviewed_at')
    op.drop_column('search_results', 'review_note')
    op.drop_column('search_results', 'review_status')
    op.drop_column('search_results', 'scores')
