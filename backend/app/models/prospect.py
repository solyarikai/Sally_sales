from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Index, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db import Base


class Prospect(Base):
    """
    Centralized prospect database - stores all prospects from various sources
    with standardized fields, deduplication support, and activity tracking.
    Scoped to company for data isolation.
    """
    __tablename__ = "prospects"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    
    # Primary dedup keys
    email = Column(String(255), nullable=True, index=True)
    linkedin_url = Column(String(500), nullable=True, index=True)
    
    # Name fields
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    full_name = Column(String(500), nullable=True)
    
    # Company fields
    company_name = Column(String(500), nullable=True)
    company_domain = Column(String(255), nullable=True)
    company_linkedin = Column(String(500), nullable=True)
    
    # Professional info
    job_title = Column(String(500), nullable=True)
    
    # Contact info
    phone = Column(String(100), nullable=True)
    
    # Location
    location = Column(String(500), nullable=True)
    country = Column(String(100), nullable=True)
    city = Column(String(255), nullable=True)
    
    # Industry & other
    industry = Column(String(255), nullable=True)
    company_size = Column(String(100), nullable=True)
    website = Column(String(500), nullable=True)
    
    # Dynamic fields - all non-standard data goes here
    custom_fields = Column(JSON, nullable=False, default=dict)
    
    # Source tracking - list of {dataset_id, dataset_name, added_at, row_id}
    sources = Column(JSON, nullable=False, default=list)
    
    # Enrichment history - list of {type, timestamp, data}
    enrichment_history = Column(JSON, nullable=False, default=list)
    
    # Status tracking
    is_verified = Column(Integer, default=0)  # 0=unknown, 1=verified, -1=invalid
    
    # Outreach tracking - Email (Instantly, Smartlead, etc.)
    sent_to_email = Column(Boolean, default=False)
    sent_to_email_at = Column(DateTime, nullable=True)
    email_campaign_id = Column(String(255), nullable=True)
    email_campaign_name = Column(String(255), nullable=True)
    email_tool = Column(String(50), nullable=True)  # instantly, smartlead, etc.
    
    # Outreach tracking - LinkedIn
    sent_to_linkedin = Column(Boolean, default=False)
    sent_to_linkedin_at = Column(DateTime, nullable=True)
    linkedin_campaign_id = Column(String(255), nullable=True)
    linkedin_campaign_name = Column(String(255), nullable=True)
    linkedin_tool = Column(String(50), nullable=True)  # expandi, dripify, etc.
    
    # Lead status
    status = Column(String(50), default='new')  # new, contacted, interested, not_interested, qualified, unqualified, converted, blocklist
    status_updated_at = Column(DateTime, nullable=True)
    
    # Segment
    segment_id = Column(Integer, nullable=True)
    segment_name = Column(String(255), nullable=True)
    
    # Organization
    tags = Column(JSON, nullable=False, default=list)
    notes = Column(Text, nullable=True)
    
    # Soft delete support (consistent with other models)
    is_active = Column(Boolean, default=True, index=True)
    deleted_at = Column(DateTime, nullable=True, index=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    company = relationship("Company", back_populates="prospects")
    activities = relationship("ProspectActivity", back_populates="prospect", cascade="all, delete-orphan")
    
    # Indexes (company_id index is created by index=True on column)
    __table_args__ = (
        Index('ix_prospects_company_email', 'company_id', 'email'),
        Index('ix_prospects_name_company', 'first_name', 'last_name', 'company_name'),
        Index('ix_prospects_full_name_company', 'full_name', 'company_name'),
        Index('ix_prospects_sent_email', 'sent_to_email', 'sent_to_email_at'),
        Index('ix_prospects_sent_linkedin', 'sent_to_linkedin', 'sent_to_linkedin_at'),
        Index('ix_prospects_status', 'status'),
        Index('ix_prospects_segment', 'segment_id'),
        Index('ix_prospects_created', 'created_at'),
    )


class ProspectActivity(Base):
    """Activity log for prospects - tracks all actions"""
    __tablename__ = "prospect_activities"
    
    id = Column(Integer, primary_key=True, index=True)
    prospect_id = Column(Integer, ForeignKey("prospects.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Activity details
    activity_type = Column(String(50), nullable=False)  # added, exported, sent_instantly, sent_smartlead, updated, enriched, note_added, tagged
    description = Column(Text, nullable=True)
    activity_data = Column(JSON, nullable=False, default=dict)  # campaign_id, dataset_name, old_value, new_value, etc.
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    prospect = relationship("Prospect", back_populates="activities")
