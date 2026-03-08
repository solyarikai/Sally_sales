"""Add Telegram chat monitoring tables

Revision ID: a1b2c3d4e5f7
Revises: f8a3b2c1d4e5
Create Date: 2026-03-08 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f7'
down_revision = None  # standalone — will be stamped manually
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'telegram_chats',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('chat_id', sa.BigInteger(), nullable=False, unique=True, index=True),
        sa.Column('chat_title', sa.String(255)),
        sa.Column('chat_type', sa.String(50)),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id'), nullable=True),
        sa.Column('is_active', sa.Integer(), server_default='1'),
        sa.Column('joined_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('last_message_at', sa.DateTime(), nullable=True),
        sa.Column('message_count', sa.Integer(), server_default='0'),
    )

    op.create_table(
        'telegram_chat_messages',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('chat_id', sa.BigInteger(), nullable=False, index=True),
        sa.Column('message_id', sa.BigInteger(), nullable=False),
        sa.Column('sender_id', sa.BigInteger(), nullable=True),
        sa.Column('sender_name', sa.String(255)),
        sa.Column('sender_username', sa.String(255), nullable=True),
        sa.Column('text', sa.Text(), nullable=True),
        sa.Column('reply_to_message_id', sa.BigInteger(), nullable=True),
        sa.Column('sent_at', sa.DateTime(), nullable=False),
        sa.Column('stored_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('message_type', sa.String(50), server_default='text'),
        sa.Column('raw_data', sa.JSON(), nullable=True),
    )
    op.create_index('ix_tcm_chat_date', 'telegram_chat_messages', ['chat_id', 'sent_at'])

    op.create_table(
        'telegram_chat_insights',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('chat_id', sa.BigInteger(), nullable=False, index=True),
        sa.Column('topic', sa.String(100), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('key_points', sa.JSON(), nullable=True),
        sa.Column('action_items', sa.JSON(), nullable=True),
        sa.Column('message_ids', sa.JSON(), nullable=True),
        sa.Column('first_message_at', sa.DateTime(), nullable=True),
        sa.Column('last_message_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('telegram_chat_insights')
    op.drop_table('telegram_chat_messages')
    op.drop_table('telegram_chats')
