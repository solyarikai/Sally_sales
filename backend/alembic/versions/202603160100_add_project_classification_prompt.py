"""Add classification_prompt column to projects for per-project reply classification.

Allows each project to have custom classification guidance (e.g., Russian polite decline
patterns for easystaff ru). Appended to the default CLASSIFICATION_PROMPT.

Revision ID: 202603160100
Revises: 202603150100
Create Date: 2026-03-16
"""
from alembic import op
import sqlalchemy as sa

revision = "202603160100"
down_revision = "202603150100"
branch_labels = None
depends_on = None


EASYSTAFF_RU_CLASSIFICATION_PROMPT = (
    "This is EasyStaff — a B2B payroll/contractor payments platform. "
    "IMPORTANT: In Russian business culture, polite short replies that acknowledge "
    "your message but express no need are DECLINES, not interest. Examples:\n"
    "- 'Спасибо, пока проблем нет' = not_interested (they have no problems = no need)\n"
    "- 'Сложностей нет, спасибо' = not_interested (no difficulties = no need)\n"
    "- 'Нас всё устраивает' = not_interested (everything suits us = no need)\n"
    "- 'Добрый день, спасибо что написали. Пока проблем нет' = not_interested\n"
    "- 'Пока не требуется' = not_interested\n"
    "These are NOT interested — they are polite ways of saying 'no thank you' in Russian B2B.\n"
    "Only classify as 'interested' if they explicitly ask for details, pricing, a call, "
    "or say 'расскажите подробнее', 'давайте', 'интересно'."
)


def upgrade():
    op.add_column("projects", sa.Column("classification_prompt", sa.Text(), nullable=True))
    # Set easystaff ru (project 40) classification prompt
    op.execute(
        f"UPDATE projects SET classification_prompt = "
        f"'{EASYSTAFF_RU_CLASSIFICATION_PROMPT.replace(chr(39), chr(39)+chr(39))}' "
        f"WHERE id = 40"
    )


def downgrade():
    op.drop_column("projects", "classification_prompt")
