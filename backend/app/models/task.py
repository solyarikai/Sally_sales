"""Operator Task model for CRM task management."""
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Index
from datetime import datetime
from app.db import Base
from app.models.mixins import TimestampMixin


class OperatorTask(Base, TimestampMixin):
    """
    OperatorTask — tasks for CRM operators, auto-created or manual.

    Auto-created when contact status changes to 'scheduled':
    - morning_ping: Ping lead on the morning of the meeting day
    - pre_meeting: Reminder before the meeting

    Manual tasks can also be created by operators.
    """
    __tablename__ = "operator_tasks"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    contact_id = Column(Integer, ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True, index=True)

    # Task info
    task_type = Column(String(50), nullable=False, default="manual")  # morning_ping, pre_meeting, follow_up, manual
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)

    # Scheduling
    due_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Status
    status = Column(String(50), nullable=False, default="pending")  # pending, done, skipped

    # Denormalized contact info for quick display
    contact_email = Column(String(255), nullable=True)
    contact_name = Column(String(500), nullable=True)

    __table_args__ = (
        Index('ix_operator_tasks_project_status', 'project_id', 'status'),
        Index('ix_operator_tasks_due', 'due_at', 'status'),
        Index('ix_operator_tasks_contact', 'contact_id'),
    )
