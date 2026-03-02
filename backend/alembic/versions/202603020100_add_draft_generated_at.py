"""Add draft_generated_at column to processed_replies

Revision ID: 202603020100
Revises: 202603010100
Create Date: 2026-03-02 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "202603020100"
down_revision: Union[str, None] = "202603010100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "processed_replies",
        sa.Column("draft_generated_at", sa.DateTime(), nullable=True),
    )
    # Backfill: set draft_generated_at = processed_at for existing replies that have a draft
    op.execute(
        "UPDATE processed_replies SET draft_generated_at = processed_at WHERE draft_reply IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_column("processed_replies", "draft_generated_at")
