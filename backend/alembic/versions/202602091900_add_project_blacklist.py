"""Add project_blacklist table and backfill from rejected search results.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-09 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'project_blacklist',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('domain', sa.String(255), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('source', sa.String(50), server_default='auto_review'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        'ix_project_blacklist_project_domain',
        'project_blacklist',
        ['project_id', 'domain'],
        unique=True,
    )
    op.create_index(
        'ix_project_blacklist_project_id',
        'project_blacklist',
        ['project_id'],
    )

    # Backfill: insert rejected SearchResults into blacklist
    op.execute("""
        INSERT INTO project_blacklist (project_id, domain, reason, source, created_at)
        SELECT DISTINCT sr.project_id, sr.domain, sr.review_note, 'auto_review', sr.reviewed_at
        FROM search_results sr
        WHERE sr.review_status = 'rejected'
          AND sr.project_id IS NOT NULL
          AND sr.domain IS NOT NULL
        ON CONFLICT (project_id, domain) DO NOTHING
    """)


def downgrade() -> None:
    op.drop_index('ix_project_blacklist_project_id', table_name='project_blacklist')
    op.drop_index('ix_project_blacklist_project_domain', table_name='project_blacklist')
    op.drop_table('project_blacklist')
