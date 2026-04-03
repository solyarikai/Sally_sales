"""Outreach Statistics model for tracking plan vs fact by channel/segment."""
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, UniqueConstraint, Index, Text
from sqlalchemy.sql import func
from datetime import date

from app.db import Base


class OutreachStats(Base):
    """
    Stores outreach statistics per channel/segment for a period.

    Auto-calculated from:
    - SmartLead (email campaigns)
    - GetSales (LinkedIn)
    - Calendly (meetings)

    Manual input for:
    - Telegram
    - WhatsApp
    - Custom channels
    """
    __tablename__ = "outreach_stats"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)

    # Period
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)

    # Channel and segment
    channel = Column(String(50), nullable=False)  # linkedin, email, telegram, whatsapp, custom
    segment = Column(String(255), nullable=False)  # hypothesis/segment name

    # Plan (always manual)
    plan_contacts = Column(Integer, default=0)

    # Fact - auto-calculated or manual depending on channel
    contacts_sent = Column(Integer, default=0)        # Invites/emails sent
    contacts_accepted = Column(Integer, default=0)    # LinkedIn accepts (N/A for email)
    replies_count = Column(Integer, default=0)        # Total replies
    positive_replies = Column(Integer, default=0)     # Interested/meeting requests
    meetings_scheduled = Column(Integer, default=0)   # Meetings booked
    meetings_completed = Column(Integer, default=0)   # Meetings that happened

    # Calculated rates (stored for quick access)
    reply_rate = Column(Float, default=0.0)           # replies / sent
    positive_rate = Column(Float, default=0.0)        # positive / replies
    accept_rate = Column(Float, default=0.0)          # accepts / sent (LinkedIn)
    meeting_rate = Column(Float, default=0.0)         # meetings / positive

    # Source tracking
    is_manual = Column(Integer, default=0)  # 1 if manually entered (TG, WA), 0 if auto-calculated
    data_source = Column(String(50), nullable=True)  # smartlead, getsales, calendly, manual

    # Notes
    notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_synced_at = Column(DateTime(timezone=True), nullable=True)  # Last auto-sync time

    __table_args__ = (
        UniqueConstraint(
            "project_id", "period_start", "period_end", "channel", "segment",
            name="uq_outreach_stats_period_channel_segment"
        ),
        Index("ix_outreach_stats_project_period", "project_id", "period_start", "period_end"),
        Index("ix_outreach_stats_channel", "channel"),
    )

    def calculate_rates(self):
        """Recalculate all rates based on current counts."""
        if self.contacts_sent and self.contacts_sent > 0:
            self.reply_rate = round(self.replies_count / self.contacts_sent, 4) if self.replies_count else 0
            self.accept_rate = round(self.contacts_accepted / self.contacts_sent, 4) if self.contacts_accepted else 0
        else:
            self.reply_rate = 0
            self.accept_rate = 0

        if self.replies_count and self.replies_count > 0:
            self.positive_rate = round(self.positive_replies / self.replies_count, 4) if self.positive_replies else 0
        else:
            self.positive_rate = 0

        if self.positive_replies and self.positive_replies > 0:
            self.meeting_rate = round(self.meetings_scheduled / self.positive_replies, 4) if self.meetings_scheduled else 0
        else:
            self.meeting_rate = 0

    def to_dict(self):
        """Convert to dictionary for API response."""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_end": self.period_end.isoformat() if self.period_end else None,
            "channel": self.channel,
            "segment": self.segment,
            "plan_contacts": self.plan_contacts,
            "contacts_sent": self.contacts_sent,
            "contacts_accepted": self.contacts_accepted,
            "replies_count": self.replies_count,
            "positive_replies": self.positive_replies,
            "meetings_scheduled": self.meetings_scheduled,
            "meetings_completed": self.meetings_completed,
            "reply_rate": self.reply_rate,
            "positive_rate": self.positive_rate,
            "accept_rate": self.accept_rate,
            "meeting_rate": self.meeting_rate,
            "is_manual": bool(self.is_manual),
            "data_source": self.data_source,
            "notes": self.notes,
            "last_synced_at": self.last_synced_at.isoformat() if self.last_synced_at else None,
        }
