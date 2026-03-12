"""GTM Strategy Log — stores each AI-generated GTM strategy run."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, ForeignKey, Index
from app.db import Base


class GTMStrategyLog(Base):
    """One entry per GTM strategy generation (manual or scheduled)."""
    __tablename__ = "gtm_strategy_logs"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    trigger = Column(String(50), nullable=False)  # manual, scheduled_morning, scheduled_evening
    model = Column(String(100), nullable=False)   # claude-opus-4-6
    strategy_json = Column(Text, nullable=True)    # the full JSON strategy
    input_summary = Column(Text, nullable=True)    # summary of what was fed to the model
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    cost_usd = Column(String(20), nullable=True)
    status = Column(String(20), nullable=False, default="completed")  # completed, failed
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_gtm_log_project_created", "project_id", "created_at"),
    )
