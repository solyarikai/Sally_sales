"""Models for Reply Automation feature."""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.db import Base
from app.models.mixins import SoftDeleteMixin, TimestampMixin


class ReplyCategory(str, enum.Enum):
    """Categories for email reply classification."""
    INTERESTED = "interested"
    MEETING_REQUEST = "meeting_request"
    NOT_INTERESTED = "not_interested"
    OUT_OF_OFFICE = "out_of_office"
    WRONG_PERSON = "wrong_person"
    UNSUBSCRIBE = "unsubscribe"
    QUESTION = "question"
    OTHER = "other"


class ReplyAutomation(Base, SoftDeleteMixin, TimestampMixin):
    """Configuration for automated reply processing.
    
    Defines which Smartlead campaigns to monitor and where to send notifications.
    """
    __tablename__ = "reply_automations"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    
    # Company/Environment context
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)
    environment_id = Column(Integer, ForeignKey("environments.id"), nullable=True)
    
    # Campaigns to monitor (stored as JSON array of campaign IDs)
    campaign_ids = Column(JSON, default=list, nullable=False)
    
    # Notification settings
    slack_webhook_url = Column(String(500), nullable=True)
    slack_channel = Column(String(100), nullable=True)
    
    # Google Sheets logging
    google_sheet_id = Column(String(100), nullable=True)
    google_sheet_name = Column(String(255), nullable=True)
    
    # Processing settings
    auto_classify = Column(Boolean, default=True, nullable=False)
    auto_generate_reply = Column(Boolean, default=True, nullable=False)
    
    # Custom prompts (optional - uses defaults if not set)
    classification_prompt = Column(Text, nullable=True)  # Custom classification prompt
    reply_prompt = Column(Text, nullable=True)  # Custom reply generation prompt
    
    # Status
    active = Column(Boolean, default=True, nullable=False)
    
    # Monitoring fields
    last_run_at = Column(DateTime, nullable=True)  # Last time automation processed a reply
    total_processed = Column(Integer, default=0, nullable=False)  # Total replies processed
    total_errors = Column(Integer, default=0, nullable=False)  # Total processing errors
    last_error = Column(Text, nullable=True)  # Last error message
    last_error_at = Column(DateTime, nullable=True)  # Last error timestamp
    
    # Relationships
    company = relationship("Company", back_populates="reply_automations")
    processed_replies = relationship("ProcessedReply", back_populates="automation", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<ReplyAutomation(id={self.id}, name='{self.name}', active={self.active})>"


class ProcessedReply(Base, TimestampMixin):
    """Stored record of a processed email reply.
    
    Contains the original reply, AI classification, draft response, and notification status.
    """
    __tablename__ = "processed_replies"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Link to automation config
    automation_id = Column(Integer, ForeignKey("reply_automations.id"), nullable=True)
    
    # Smartlead context
    campaign_id = Column(String(100), nullable=True, index=True)
    campaign_name = Column(String(255), nullable=True)
    
    # Lead information
    lead_email = Column(String(255), nullable=False, index=True)
    lead_first_name = Column(String(100), nullable=True)
    lead_last_name = Column(String(100), nullable=True)
    lead_company = Column(String(255), nullable=True)
    
    # Original email content
    email_subject = Column(String(500), nullable=True)
    email_body = Column(Text, nullable=True)
    reply_text = Column(Text, nullable=True)  # Just the reply portion
    received_at = Column(DateTime, nullable=True)
    
    # AI Classification
    category = Column(String(50), nullable=True, index=True)
    category_confidence = Column(String(20), nullable=True)  # high, medium, low
    classification_reasoning = Column(Text, nullable=True)
    
    # Generated draft reply
    draft_reply = Column(Text, nullable=True)
    draft_subject = Column(String(500), nullable=True)
    
    # Processing status
    processed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Notification status
    sent_to_slack = Column(Boolean, default=False, nullable=False)
    slack_sent_at = Column(DateTime, nullable=True)
    slack_message_ts = Column(String(50), nullable=True)  # Slack message ID
    
    # Approval workflow
    approval_status = Column(String(50), nullable=True, index=True)  # pending, approved, dismissed, edited
    approved_by = Column(String(100), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    
    # Smartlead inbox link (from webhook: ui_master_inbox_link)
    inbox_link = Column(String(500), nullable=True)
    
    # Google Sheets tracking
    google_sheet_row = Column(Integer, nullable=True)  # Row number in the sheet for updates
    
    # Full webhook payload for debugging
    raw_webhook_data = Column(JSON, nullable=True)
    
    # Relationships
    automation = relationship("ReplyAutomation", back_populates="processed_replies")
    
    def __repr__(self):
        return f"<ProcessedReply(id={self.id}, email='{self.lead_email}', category='{self.category}')>"


class ReplyPromptTemplateModel(Base):
    """Templates for reply classification and generation prompts."""
    __tablename__ = "reply_prompt_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    prompt_type = Column(String(50), nullable=False)  # classification or reply
    prompt_text = Column(Text, nullable=False)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
