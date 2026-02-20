"""Add sheet sync config to projects and sheet tracking to contacts.

Revision ID: 202602200300
Revises: 202602200200
Create Date: 2026-02-20 03:00:00
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '202602200300'
down_revision: Union[str, None] = '202602200200'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Project: sheet_sync_config JSON column
    op.add_column('projects', sa.Column('sheet_sync_config', sa.JSON(), nullable=True))

    # Contact: sheet sync tracking fields
    op.add_column('contacts', sa.Column('sheet_qualification', sa.String(100), nullable=True))
    op.add_column('contacts', sa.Column('sheet_client_comment', sa.String(2000), nullable=True))
    op.add_column('contacts', sa.Column('sheet_row', sa.Integer(), nullable=True))

    # Pre-configure project 40 (EasyStaff RU) with sheet config
    op.execute("""
        UPDATE projects SET sheet_sync_config = '{"enabled": false, "sheet_id": "1gsHVo3bv9WGKgipQ5RTK71tya8xHPdk9r78S_EwAroM", "leads_tab": "Leads", "replies_tab": "Replies"}'::jsonb
        WHERE id = 40 AND sheet_sync_config IS NULL
    """)


def downgrade() -> None:
    op.drop_column('contacts', 'sheet_row')
    op.drop_column('contacts', 'sheet_client_comment')
    op.drop_column('contacts', 'sheet_qualification')
    op.drop_column('projects', 'sheet_sync_config')
