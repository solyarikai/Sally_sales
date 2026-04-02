"""Seed OnSocial (project 42) with Calendly config for time slot suggestions.

Revision ID: 202603180200
Revises: 202603180100
Create Date: 2026-03-18
"""
from alembic import op

revision = "202603180200"
down_revision = "202603180100"
branch_labels = None
depends_on = None


def upgrade():
    # OnSocial sales Calendly — single account, English outreach
    op.execute("""
        UPDATE projects SET calendly_config = '{
          "language": "en",
          "members": [
            {
              "id": "onsocial_sales",
              "display_name": "OnSocial Sales",
              "pat_token": "eyJraWQiOiIxY2UxZTEzNjE3ZGNmNzY2YjNjZWJjY2Y4ZGM1YmFmYThhNjVlNjg0MDIzZjdjMzJiZTgzNDliMjM4MDEzNWI0IiwidHlwIjoiUEFUIiwiYWxnIjoiRVMyNTYifQ.eyJpc3MiOiJodHRwczovL2F1dGguY2FsZW5kbHkuY29tIiwiaWF0IjoxNzczODMxODcxLCJqdGkiOiI2YWY4Nzk4Mi0xMjVlLTQxYjktYmNhYi1jYWI0Mjc0NzY2NjUiLCJ1c2VyX3V1aWQiOiI2NTY0YTY3ZC1mYzExLTRlMmYtODQzZS04ZGMzMmRkMWM4NDkiLCJzY29wZSI6ImF2YWlsYWJpbGl0eTpyZWFkIGF2YWlsYWJpbGl0eTp3cml0ZSBldmVudF90eXBlczpyZWFkIGV2ZW50X3R5cGVzOndyaXRlIGxvY2F0aW9uczpyZWFkIHJvdXRpbmdfZm9ybXM6cmVhZCBzaGFyZXM6d3JpdGUgc2NoZWR1bGVkX2V2ZW50czpyZWFkIHNjaGVkdWxlZF9ldmVudHM6d3JpdGUgc2NoZWR1bGluZ19saW5rczp3cml0ZSJ9.aXtpATFIxpGcQs2fe02IeO3TaF2wk7uYcL2fYYfhwLRWzFiv8mR-bEXjO8BFgiolYAg3Rz_zj9qjnY3dXP0JiA",
              "is_default": true
            }
          ]
        }' WHERE id = 42 AND calendly_config IS NULL
    """)


def downgrade():
    op.execute("UPDATE projects SET calendly_config = NULL WHERE id = 42")
