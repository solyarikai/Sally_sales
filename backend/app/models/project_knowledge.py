"""
Project Knowledge — unified, reusable knowledge base per project.

Stores structured knowledge entries grouped by category (icp, search, outreach,
contacts, gtm, notes). Each entry has a JSONB `value` field for flexible data.

Used by chat, search pipeline, and any service that needs project context.
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.db import Base


class ProjectKnowledge(Base):
    """A single knowledge entry for a project, keyed by (category, key)."""
    __tablename__ = "project_knowledge"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    category = Column(String(50), nullable=False)   # icp, search, outreach, contacts, gtm, notes
    key = Column(String(100), nullable=False)        # target_description, exclusions, etc.
    title = Column(String(255), nullable=True)       # human-readable label
    value = Column(JSONB, nullable=False, default=dict)
    source = Column(String(50), default="manual")    # manual, chat, pipeline, sync
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_project_knowledge_project_cat", "project_id", "category"),
        Index("uq_project_knowledge_project_cat_key", "project_id", "category", "key", unique=True),
    )
