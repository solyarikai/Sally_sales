"""Add campaign launch tracking and SDR email field.

Revision ID: 202603161800
Revises: 202603160200
Create Date: 2026-03-16 18:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '202603161800'
down_revision = '202603160200'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Campaign table: track launch state
    op.add_column('campaigns', sa.Column('previous_status', sa.String(50), nullable=True))
    op.add_column('campaigns', sa.Column('launched_at', sa.DateTime, nullable=True))
    op.add_column('campaigns', sa.Column('launch_notified', sa.Boolean, server_default='false', nullable=False))

    # Project table: SDR email for test notifications
    op.add_column('projects', sa.Column('sdr_email', sa.String(255), nullable=True))

    # Data migration: mark all existing ACTIVE campaigns as already notified
    # This prevents sending notifications for campaigns that were launched before this feature
    op.execute("""
        UPDATE campaigns
        SET launch_notified = true,
            previous_status = status
        WHERE status = 'active'
    """)


def downgrade() -> None:
    op.drop_column('projects', 'sdr_email')
    op.drop_column('campaigns', 'launch_notified')
    op.drop_column('campaigns', 'launched_at')
    op.drop_column('campaigns', 'previous_status')
