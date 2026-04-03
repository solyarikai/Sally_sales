"""Add getsales_senders column to projects for LinkedIn sender filtering.

Revision ID: 202603030300
Revises: 202603030100
Create Date: 2026-03-03
"""
from alembic import op
import sqlalchemy as sa


revision = "202603030300"
down_revision = "202603030100"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("getsales_senders", sa.JSON(), nullable=True))

    # Backfill sender mappings from observed data.
    # Only include senders that are EXCLUSIVE to the project's campaigns
    # (i.e. not shared with other projects' campaigns).
    conn = op.get_bind()

    # Mifort: only the 3 dedicated senders (Anna Reisberg, Lera Yurkoits, Sophia Powell)
    # Excludes Ruslan Zholik (also Inxy) and Lisa Woodard (also Rizzult)
    conn.execute(sa.text("""
        UPDATE projects SET getsales_senders = '["0d22a72e-5e30-4f72-bac7-0fac29fe8121", "430e90e2-adfb-47d6-a986-3b8a75f4c80e", "c58462db-beda-44a5-ba32-12e436d55bba"]'
        WHERE id = 21
    """))


def downgrade() -> None:
    op.drop_column("projects", "getsales_senders")
