"""
Campaign Audit Log — tracks all changes to project campaign_filters.

Every add/remove of a campaign from a project is logged here, whether
done manually (UI), via AI rule feedback, or God Panel assignment.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime

from app.db import Base


class CampaignAuditLog(Base):
    """One log entry per campaign assignment change."""
    __tablename__ = "campaign_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    action = Column(String(20), nullable=False)      # add, remove, bulk_set
    campaign_name = Column(String(500), nullable=True)  # individual campaign (null for bulk_set)
    source = Column(String(50), nullable=False)       # manual, ai_feedback, god_panel
    learning_log_id = Column(Integer, ForeignKey("learning_logs.id", ondelete="SET NULL"), nullable=True)
    details = Column(Text, nullable=True)             # human-readable context
    campaigns_before = Column(JSONB, nullable=True)   # snapshot before change
    campaigns_after = Column(JSONB, nullable=True)    # snapshot after change
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_cal_project_created", "project_id", "created_at"),
    )
