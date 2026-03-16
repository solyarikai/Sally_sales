"""Reply Intelligence — structured classification of reply conversations."""
from sqlalchemy import Column, Integer, String, SmallInteger, Text, DateTime, ForeignKey, Index
from datetime import datetime

from app.db import Base


class ReplyAnalysis(Base):
    """Structured analysis of a processed reply — offer, intent, warmth, segment."""
    __tablename__ = "reply_analysis"

    id = Column(Integer, primary_key=True, index=True)
    processed_reply_id = Column(Integer, ForeignKey("processed_replies.id", ondelete="CASCADE"), unique=True, nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)

    # Which INXY product did the lead respond to?
    offer_responded_to = Column(String(20), nullable=True)  # paygate | payout | otc | general

    # What is the lead's intent?
    intent = Column(String(30), nullable=True, index=True)
    # WARM: send_info | schedule_call | interested_vague | redirect_colleague
    # QUESTION: pricing | how_it_works | compliance | specific_use_case | adjacent_demand
    # OBJECTION: not_relevant | no_crypto | not_now | have_solution | regulatory | hard_no | spam_complaint
    # NOISE: empty | auto_response | bounce | gibberish | wrong_person_forward

    # Warmth 1-5
    warmth_score = Column(SmallInteger, nullable=True, index=True)

    # Target segment the campaign was aimed at
    campaign_segment = Column(String(30), nullable=True)

    # Type of outreach that triggered this
    sequence_type = Column(String(20), nullable=True)  # cold_email | cold_linkedin | conference_followup | personalized

    # Language of the reply
    language = Column(String(5), nullable=True)

    # AI reasoning
    reasoning = Column(Text, nullable=True)
    analyzed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    analyzer_model = Column(String(50), nullable=True)

    __table_args__ = (
        Index("ix_reply_analysis_project", "project_id"),
        Index("ix_reply_analysis_offer", "offer_responded_to"),
        Index("ix_reply_analysis_warmth", "warmth_score"),
    )

    def __repr__(self):
        return f"<ReplyAnalysis(id={self.id}, intent={self.intent}, warmth={self.warmth_score})>"
