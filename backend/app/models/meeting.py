"""
Meeting model — tracks booked meetings from Calendly.

Source of truth is Calendly. Meetings are created via webhook when
invitee.created event fires. TG notification is sent immediately.
"""
from enum import Enum
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Index, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db import Base


class MeetingStatus(str, Enum):
    SCHEDULED = "scheduled"      # Booked, waiting
    COMPLETED = "completed"      # Meeting happened
    NO_SHOW = "no_show"          # Invitee didn't show up
    CANCELLED = "cancelled"      # Cancelled by either party
    RESCHEDULED = "rescheduled"  # Moved to another time


class MeetingOutcome(str, Enum):
    PENDING = "pending"          # Waiting for meeting / result
    QUALIFIED = "qualified"      # Good fit, moving forward
    NOT_FIT = "not_fit"          # Not a match
    FOLLOW_UP = "follow_up"      # Needs another call
    NEGOTIATION = "negotiation"  # In deal negotiation
    CLOSED_WON = "closed_won"    # Deal closed successfully
    CLOSED_LOST = "closed_lost"  # Deal lost


class Meeting(Base):
    """
    Meeting — a scheduled call from Calendly.

    Created automatically from Calendly webhook (invitee.created).
    Linked to project via calendly_config membership.
    """
    __tablename__ = "meetings"

    id = Column(Integer, primary_key=True, index=True)

    # Ownership
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    contact_id = Column(Integer, ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True)

    # Calendly identifiers (for dedup and updates)
    calendly_event_uri = Column(String(500), nullable=True, unique=True, index=True)
    calendly_invitee_uri = Column(String(500), nullable=True)

    # Invitee info (from Calendly payload)
    invitee_name = Column(String(255), nullable=False)
    invitee_email = Column(String(255), nullable=True, index=True)
    invitee_company = Column(String(500), nullable=True)
    invitee_title = Column(String(500), nullable=True)

    # Meeting details
    event_type_name = Column(String(255), nullable=True)  # "30 min intro call"
    scheduled_at = Column(DateTime(timezone=True), nullable=False, index=True)
    duration_minutes = Column(Integer, default=30)
    meeting_link = Column(String(1000), nullable=True)  # Zoom/Google Meet link
    location = Column(String(500), nullable=True)  # "Zoom" / "Google Meet" / physical

    # Host info
    host_name = Column(String(255), nullable=True)
    host_email = Column(String(255), nullable=True)

    # Status tracking
    status = Column(SQLEnum(MeetingStatus), default=MeetingStatus.SCHEDULED, nullable=False)
    outcome = Column(SQLEnum(MeetingOutcome), default=MeetingOutcome.PENDING, nullable=True)

    # Notes
    notes = Column(Text, nullable=True)  # Internal notes
    client_notes = Column(Text, nullable=True)  # Notes visible to client in dashboard
    cancellation_reason = Column(Text, nullable=True)

    # Source tracking
    channel = Column(String(50), nullable=True)  # email, linkedin, telegram — how lead was acquired
    segment = Column(String(255), nullable=True)  # hypothesis/segment name
    campaign_name = Column(String(500), nullable=True)

    # Questions/answers from Calendly form
    invitee_questions = Column(Text, nullable=True)  # JSON or text dump of Q&A

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    cancelled_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    project = relationship("Project", backref="meetings")
    contact = relationship("Contact", backref="meetings")

    __table_args__ = (
        Index("ix_meetings_project_scheduled", "project_id", "scheduled_at"),
        Index("ix_meetings_status", "status"),
        Index("ix_meetings_company_project", "company_id", "project_id"),
    )

    def __repr__(self):
        return f"<Meeting {self.id}: {self.invitee_name} @ {self.scheduled_at}>"
