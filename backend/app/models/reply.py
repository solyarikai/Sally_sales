"""Models for Reply Automation feature."""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON, Index, UniqueConstraint
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
    campaign_name = Column(String(255), nullable=True, index=True)

    # Source tracking
    source = Column(String(50), nullable=True, index=True)   # "smartlead" or "getsales"
    channel = Column(String(50), nullable=True, index=True)   # "email" or "linkedin"

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
    draft_generated_at = Column(DateTime, nullable=True)
    
    # Processing status
    processed_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Notification status
    sent_to_slack = Column(Boolean, default=False, nullable=False)
    slack_sent_at = Column(DateTime, nullable=True)
    slack_message_ts = Column(String(50), nullable=True)  # Slack message ID
    telegram_sent_at = Column(DateTime, nullable=True)  # When Telegram notification was sent
    
    # Approval workflow
    approval_status = Column(String(50), nullable=True, index=True)  # pending, approved, dismissed, edited
    approved_by = Column(String(100), nullable=True)
    approved_at = Column(DateTime, nullable=True)

    # Cohort tracking — denormalized from contact_activities for fast queries
    # Updated when conversation is loaded from SmartLead or when new activity arrives
    last_touched_at = Column(DateTime, nullable=True, index=True)  # latest activity (inbound or outbound) timestamp
    
    # Smartlead inbox link (from webhook: ui_master_inbox_link)
    inbox_link = Column(String(500), nullable=True)
    
    # Google Sheets tracking
    google_sheet_row = Column(Integer, nullable=True)  # Row number in the sheet for updates
    
    # Translation — for messages not in English or Russian
    detected_language = Column(String(10), nullable=True)  # ISO 639-1: en, ru, de, fr, etc.
    translated_body = Column(Text, nullable=True)  # English translation of email_body/reply_text
    translated_draft = Column(Text, nullable=True)  # English translation of draft_reply (if draft is not en/ru)

    # Full webhook payload for debugging
    raw_webhook_data = Column(JSON, nullable=True)

    # Thread cache — pre-fetched at processing time
    smartlead_lead_id = Column(String(100), nullable=True, index=True)
    thread_fetched_at = Column(DateTime, nullable=True)

    # Content-based dedup hash — MD5 of normalized reply body.
    # Prevents duplicate ProcessedReply from concurrent webhook + polling
    # while allowing multiple DIFFERENT replies from the same lead.
    message_hash = Column(String(32), nullable=True, index=True)

    # Relationships
    automation = relationship("ReplyAutomation", back_populates="processed_replies")
    thread_messages = relationship(
        "ThreadMessage", back_populates="reply",
        cascade="all, delete-orphan",
        order_by="ThreadMessage.position",
        lazy="noload",
    )

    __table_args__ = (
        # Content-based dedup: same reply body from same lead in same campaign = duplicate.
        # Different replies from the same lead get their own records + notifications.
        Index('uq_processed_reply_content', 'lead_email', 'campaign_id', 'message_hash', unique=True),
    )

    def __repr__(self):
        return f"<ProcessedReply(id={self.id}, email='{self.lead_email}', category='{self.category}')>"


class ThreadMessage(Base):
    """Cached conversation message from Smartlead message-history API.

    Pre-fetched at reply processing time so the UI reads instantly from DB
    instead of hitting the Smartlead API on every thread click.
    """
    __tablename__ = "thread_messages"

    id = Column(Integer, primary_key=True, index=True)
    reply_id = Column(Integer, ForeignKey("processed_replies.id", ondelete="CASCADE"), nullable=False, index=True)
    direction = Column(String(20), nullable=False)      # inbound / outbound
    channel = Column(String(50), default="email")
    subject = Column(String(500), nullable=True)
    body = Column(Text, nullable=True)
    activity_at = Column(DateTime, nullable=True)
    source = Column(String(50), default="smartlead")
    activity_type = Column(String(50), nullable=True)    # email_sent / email_replied
    position = Column(Integer, nullable=False, default=0)  # ordering index
    created_at = Column(DateTime, default=datetime.utcnow)

    reply = relationship("ProcessedReply", back_populates="thread_messages")

    def __repr__(self):
        return f"<ThreadMessage(id={self.id}, reply_id={self.reply_id}, direction='{self.direction}', pos={self.position})>"


class ReplyCleanupLog(Base):
    """Log of daily needs_reply cleanup runs — tracks which replies were auto-resolved."""
    __tablename__ = "reply_cleanup_logs"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True)
    project_name = Column(String(255), nullable=True)
    replies_checked = Column(Integer, default=0)
    replies_resolved = Column(Integer, default=0)
    resolved_replies = Column(JSON, nullable=True)  # [{reply_id, lead_email, campaign_name}]
    errors = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<ReplyCleanupLog(id={self.id}, project={self.project_name}, resolved={self.replies_resolved})>"


class ReplyPromptTemplateModel(Base):
    """Templates for reply classification and generation prompts."""
    __tablename__ = "reply_prompt_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    prompt_type = Column(String(50), nullable=True)  # Optional tag  # classification or reply
    prompt_text = Column(Text, nullable=False)
    is_default = Column(Boolean, default=False)
    usage_count = Column(Integer, default=0, nullable=False)
    last_used_at = Column(DateTime, nullable=True)
    version = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TelegramRegistration(Base):
    """Maps Telegram @username to chat_id for per-project notifications.

    Populated when a user sends /start to the bot. The project page
    lets operators enter their @username, and the backend resolves it
    to a chat_id from this table.
    """
    __tablename__ = "telegram_registrations"

    id = Column(Integer, primary_key=True, index=True)
    telegram_username = Column(String(100), unique=True, index=True, nullable=False)  # lowercase, no @
    telegram_chat_id = Column(String(100), nullable=False)
    telegram_first_name = Column(String(100), nullable=True)
    registered_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TelegramSubscription(Base):
    """Multi-operator Telegram subscriptions per project.

    Each row = one operator receiving reply notifications for one project.
    An operator can subscribe to multiple projects; a project can have
    multiple subscribers.
    """
    __tablename__ = "telegram_subscriptions"
    __table_args__ = (
        UniqueConstraint("project_id", "chat_id", name="uq_tg_sub_project_chat"),
    )

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    chat_id = Column(String(100), nullable=False, index=True)
    username = Column(String(100), nullable=True)
    first_name = Column(String(100), nullable=True)
    subscribed_at = Column(DateTime, default=datetime.utcnow)


class WebhookEventModel(Base):
    """Store webhook events for history, replay, and automatic recovery."""
    __tablename__ = "webhook_events"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String(50), nullable=False)  # EMAIL_REPLY, EMAIL_SENT, LEAD_CATEGORY_UPDATED, etc.
    campaign_id = Column(String(50), nullable=True)
    lead_email = Column(String(255), nullable=True)
    payload = Column(Text, nullable=False)  # JSON payload
    processed = Column(Boolean, default=False, index=True)
    processed_at = Column(DateTime, nullable=True)
    error = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)  # Number of processing attempts
    next_retry_at = Column(DateTime, nullable=True)  # When to retry next (exponential backoff)
    created_at = Column(DateTime, default=datetime.utcnow)
