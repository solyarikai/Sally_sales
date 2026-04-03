"""Project Reporting Models for Sally Bot.

Models for project reports, plans, progress tracking, and subscriptions.
Used by Sally Bot for daily lead reports and client-facing progress updates.
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Date, Time, Float, ForeignKey, JSON, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.db import Base


class ReportRole(str, enum.Enum):
    """Roles for report subscriptions."""
    LEAD = "lead"      # Submits daily reports
    BOSS = "boss"      # Receives forwarded reports


class ProgressStatus(str, enum.Enum):
    """Status for progress items."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"


class ProjectReport(Base):
    """Daily report submitted by project lead via Telegram.

    Leads are asked evening questions about daily progress.
    Reports are stored and optionally forwarded to boss.
    """
    __tablename__ = "project_reports"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)

    # Lead info
    lead_chat_id = Column(String(100), nullable=False, index=True)
    lead_username = Column(String(100), nullable=True)
    lead_first_name = Column(String(100), nullable=True)

    # Report content
    report_date = Column(Date, nullable=False, index=True)
    report_text = Column(Text, nullable=False)
    ai_summary = Column(Text, nullable=True)  # AI-generated summary

    # Forwarding status
    forwarded_to_boss = Column(Boolean, default=False, nullable=False)
    forwarded_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    project = relationship("Project", backref="reports")

    __table_args__ = (
        UniqueConstraint("project_id", "lead_chat_id", "report_date", name="uq_project_reports_project_lead_date"),
        Index("ix_project_reports_date", "project_id", "report_date"),
    )

    def __repr__(self):
        return f"<ProjectReport(id={self.id}, project_id={self.project_id}, date={self.report_date})>"


class ProjectPlan(Base):
    """Project plan uploaded for client-facing progress tracking.

    Plans can be text or documents. AI parses them into actionable items.
    Multiple versions supported via version column.
    """
    __tablename__ = "project_plans"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)

    # Uploader info
    uploaded_by_chat_id = Column(String(100), nullable=True)
    uploaded_by_username = Column(String(100), nullable=True)

    # Plan content
    title = Column(String(500), nullable=True)
    content = Column(Text, nullable=False)
    content_type = Column(String(20), default="text", nullable=False)  # text | document
    file_id = Column(String(255), nullable=True)  # Telegram file_id for documents

    # Version control
    is_active = Column(Boolean, default=True, nullable=False)
    version = Column(Integer, default=1, nullable=False)

    # AI-parsed items from plan
    ai_parsed_items = Column(JSON, nullable=True)  # [{item, due_date, priority, category}]

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    project = relationship("Project", backref="plans")
    progress_items = relationship("ProjectProgressItem", back_populates="plan", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_project_plans_active", "project_id", "is_active"),
    )

    def __repr__(self):
        return f"<ProjectPlan(id={self.id}, project_id={self.project_id}, version={self.version}, active={self.is_active})>"


class ProjectProgressItem(Base):
    """Individual plan item for progress tracking.

    Created by AI when parsing a plan. Status updated when reports mention completion.
    """
    __tablename__ = "project_progress_items"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey("project_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)

    # Item content
    item_text = Column(Text, nullable=False)
    due_date = Column(Date, nullable=True)
    priority = Column(String(20), nullable=True)  # high | medium | low
    category = Column(String(100), nullable=True)  # e.g., development, design, testing

    # Status tracking
    status = Column(String(20), default="pending", nullable=False)  # pending | in_progress | completed | blocked
    completed_at = Column(DateTime, nullable=True)
    completed_by_report_id = Column(Integer, ForeignKey("project_reports.id", ondelete="SET NULL"), nullable=True)

    # AI confidence in matching report to this item
    ai_match_confidence = Column(Float, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    plan = relationship("ProjectPlan", back_populates="progress_items")
    project = relationship("Project", backref="progress_items")
    completed_by_report = relationship("ProjectReport", backref="completed_items")

    __table_args__ = (
        Index("ix_progress_items_status", "project_id", "status"),
    )

    def __repr__(self):
        return f"<ProjectProgressItem(id={self.id}, status={self.status}, text={self.item_text[:50]}...)>"


class ProjectReportSubscription(Base):
    """Subscription for project report notifications.

    Defines who is a lead (submits reports) and who is a boss (receives reports).
    Includes schedule config for evening questions.
    """
    __tablename__ = "project_report_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)

    # Subscriber info
    chat_id = Column(String(100), nullable=False, index=True)
    username = Column(String(100), nullable=True)
    first_name = Column(String(100), nullable=True)

    # Role: lead (submits reports) | boss (receives reports)
    role = Column(String(20), nullable=False)  # lead | boss

    # Schedule config (for leads)
    report_time = Column(Time, nullable=True)  # When to ask for report
    timezone = Column(String(50), default="Europe/Moscow", nullable=False)

    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    last_asked_at = Column(DateTime, nullable=True)
    last_reported_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    project = relationship("Project", backref="report_subscriptions")

    __table_args__ = (
        UniqueConstraint("project_id", "chat_id", "role", name="uq_report_subscriptions_project_chat_role"),
        Index("ix_report_subs_role", "role", "is_active"),
    )

    def __repr__(self):
        return f"<ProjectReportSubscription(id={self.id}, project_id={self.project_id}, role={self.role}, chat_id={self.chat_id})>"
