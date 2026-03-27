"""Merge heads — restore missing revision referenced by 202603180100.

Revision ID: c2d87b5f252e
Revises: 202603162200, 202603171000
"""
from alembic import op

revision = "c2d87b5f252e"
down_revision = ("202603162200", "202603171000")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
