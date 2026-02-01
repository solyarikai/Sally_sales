"""Pydantic schemas for Reply Automation feature."""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class ReplyCategoryEnum(str, Enum):
    """Categories for email reply classification."""
    INTERESTED = "interested"
    MEETING_REQUEST = "meeting_request"
    NOT_INTERESTED = "not_interested"
    OUT_OF_OFFICE = "out_of_office"
    WRONG_PERSON = "wrong_person"
    UNSUBSCRIBE = "unsubscribe"
    QUESTION = "question"
    OTHER = "other"


# Reply Automation Schemas
class ReplyAutomationBase(BaseModel):
    """Base schema for reply automation."""
    name: str = Field(..., min_length=1, max_length=255)
    campaign_ids: List[str] = Field(default_factory=list)
    slack_webhook_url: Optional[str] = None
    slack_channel: Optional[str] = None
    google_sheet_id: Optional[str] = None
    google_sheet_name: Optional[str] = None
    auto_classify: bool = True
    auto_generate_reply: bool = True
    classification_prompt: Optional[str] = None  # Custom prompt for classification
    reply_prompt: Optional[str] = None  # Custom prompt for reply generation
    active: bool = True


class ReplyAutomationCreate(ReplyAutomationBase):
    """Schema for creating a reply automation."""
    company_id: Optional[int] = None
    environment_id: Optional[int] = None
    create_google_sheet: bool = False  # If true, create a new Google Sheet
    share_sheet_with_email: Optional[str] = None  # Email to share the sheet with


class ReplyAutomationUpdate(BaseModel):
    """Schema for updating a reply automation."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    campaign_ids: Optional[List[str]] = None
    slack_webhook_url: Optional[str] = None
    slack_channel: Optional[str] = None
    google_sheet_id: Optional[str] = None
    google_sheet_name: Optional[str] = None
    auto_classify: Optional[bool] = None
    auto_generate_reply: Optional[bool] = None
    classification_prompt: Optional[str] = None
    reply_prompt: Optional[str] = None
    active: Optional[bool] = None


class ReplyAutomationResponse(ReplyAutomationBase):
    """Schema for reply automation response."""
    id: int
    company_id: Optional[int] = None
    environment_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    is_active: bool = True
    
    # Monitoring fields
    last_run_at: Optional[datetime] = None
    total_processed: int = 0
    total_errors: int = 0
    last_error: Optional[str] = None
    last_error_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class AutomationMonitoringStats(BaseModel):
    """Detailed monitoring stats for an automation."""
    automation_id: int
    automation_name: str
    active: bool
    
    # Counts
    total_processed: int = 0
    total_errors: int = 0
    
    # Time-based stats
    replies_today: int = 0
    replies_this_week: int = 0
    
    # Status breakdown
    pending: int = 0
    approved: int = 0
    dismissed: int = 0
    
    # Category breakdown
    by_category: dict = Field(default_factory=dict)
    
    # Timestamps
    last_run_at: Optional[datetime] = None
    last_error_at: Optional[datetime] = None
    last_error: Optional[str] = None
    created_at: datetime
    
    # Health status
    health_status: str = "healthy"  # healthy, warning, error


class AutomationMonitoringListResponse(BaseModel):
    """List of automation monitoring stats."""
    automations: List[AutomationMonitoringStats]
    total: int
    
    # Aggregate stats
    total_active: int = 0
    total_paused: int = 0
    total_processed_all: int = 0
    total_errors_all: int = 0


class ReplyAutomationListResponse(BaseModel):
    """Schema for list of reply automations."""
    automations: List[ReplyAutomationResponse]
    total: int


# Processed Reply Schemas
class ProcessedReplyBase(BaseModel):
    """Base schema for processed reply."""
    campaign_id: Optional[str] = None
    campaign_name: Optional[str] = None
    lead_email: str
    lead_first_name: Optional[str] = None
    lead_last_name: Optional[str] = None
    lead_company: Optional[str] = None
    email_subject: Optional[str] = None
    email_body: Optional[str] = None
    reply_text: Optional[str] = None


class ProcessedReplyResponse(ProcessedReplyBase):
    """Schema for processed reply response."""
    id: int
    automation_id: Optional[int] = None
    received_at: Optional[datetime] = None
    
    # Classification
    category: Optional[str] = None
    category_confidence: Optional[str] = None
    classification_reasoning: Optional[str] = None
    
    # Draft
    draft_reply: Optional[str] = None
    draft_subject: Optional[str] = None
    
    # Status
    processed_at: datetime
    sent_to_slack: bool = False
    slack_sent_at: Optional[datetime] = None
    
    # Approval workflow
    approval_status: Optional[str] = None  # pending, approved, dismissed, edited
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    
    # Smartlead inbox link
    inbox_link: Optional[str] = None
    
    created_at: datetime
    
    class Config:
        from_attributes = True


class ProcessedReplyListResponse(BaseModel):
    """Schema for list of processed replies."""
    replies: List[ProcessedReplyResponse]
    total: int
    page: int = 1
    page_size: int = 50


class ProcessedReplyStats(BaseModel):
    """Statistics for processed replies."""
    total: int = 0
    by_category: dict = Field(default_factory=dict)
    by_status: dict = Field(default_factory=dict)  # pending, approved, dismissed counts
    today: int = 0
    this_week: int = 0
    sent_to_slack: int = 0
    pending: int = 0  # Quick access to pending count
    approved: int = 0
    dismissed: int = 0


# Webhook Schema
class SmartleadWebhookPayload(BaseModel):
    """Schema for Smartlead webhook payload."""
    event_type: Optional[str] = None
    campaign_id: Optional[str] = None
    lead_email: Optional[str] = None
    email_subject: Optional[str] = None
    email_body: Optional[str] = None
    reply_text: Optional[str] = None
    received_at: Optional[str] = None
    
    # Lead details from webhook
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company_name: Optional[str] = None
    
    class Config:
        extra = "allow"


# Classification Response
class ClassificationResult(BaseModel):
    """Result of AI classification."""
    category: ReplyCategoryEnum
    confidence: str = "medium"  # high, medium, low
    reasoning: Optional[str] = None


class DraftReplyResult(BaseModel):
    """Result of draft reply generation."""
    subject: Optional[str] = None
    body: str
    tone: Optional[str] = None


# Combined processing result
class ReplyProcessingResult(BaseModel):
    """Combined result of processing a reply."""
    reply_id: int
    classification: Optional[ClassificationResult] = None
    draft: Optional[DraftReplyResult] = None
    slack_notified: bool = False
    error: Optional[str] = None
