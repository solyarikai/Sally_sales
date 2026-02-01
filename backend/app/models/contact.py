"""
CRM Contact and Project Models.

Simple, flat contact management with optional project grouping.
One table for all contacts from all sources, with filters.
"""
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Index, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db import Base
from app.models.mixins import SoftDeleteMixin, TimestampMixin


class Project(Base, SoftDeleteMixin, TimestampMixin):
    """
    Project - groups contacts for specific outreach campaigns.
    
    Each project can have:
    - Target industries/segments
    - Associated contacts
    - Generated TAM analysis (future: AI SDR)
    - Generated GTM plan (future: AI SDR)
    """
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    
    # Basic info
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Target criteria (for AI SDR later)
    target_industries = Column(Text, nullable=True)  # JSON-like string of industries
    target_segments = Column(Text, nullable=True)    # JSON-like string of segments
    
    # Generated content (for AI SDR later)
    tam_analysis = Column(Text, nullable=True)       # Total Addressable Market analysis
    gtm_plan = Column(Text, nullable=True)           # Go-to-market plan
    pitch_templates = Column(Text, nullable=True)    # JSON-like string of templates
    
    # Relationships
    company = relationship("Company", back_populates="projects")
    contacts = relationship("Contact", back_populates="project", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('ix_projects_company_name', 'company_id', 'name'),
    )


class Contact(Base, SoftDeleteMixin, TimestampMixin):
    """
    Contact - single unified table for all contacts from all sources.
    
    Simple structure:
    - id, email, first_name, last_name
    - company, domain, job_title
    - segment (business segment like "iGaming", "B2B SaaS")
    - project_id (which project this contact belongs to)
    - source (smartlead, apollo, manual, csv)
    - status (lead, contacted, replied, qualified)
    """
    __tablename__ = "contacts"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    
    # Core contact info
    email = Column(String(255), nullable=False, index=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    
    # Company info
    company_name = Column(String(500), nullable=True)
    domain = Column(String(255), nullable=True, index=True)
    job_title = Column(String(500), nullable=True)
    
    # Categorization - simple string fields for easy filtering
    segment = Column(String(255), nullable=True, index=True)      # e.g., "iGaming", "B2B SaaS", "FinTech"
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Source tracking
    source = Column(String(50), nullable=False, default="manual", index=True)  # smartlead, apollo, manual, csv
    source_id = Column(String(255), nullable=True)  # Original ID from source system
    
    # Status tracking
    status = Column(String(50), nullable=False, default="lead", index=True)  # lead, contacted, replied, qualified
    
    # Additional info
    phone = Column(String(100), nullable=True)
    linkedin_url = Column(String(500), nullable=True)
    location = Column(String(500), nullable=True)
    notes = Column(Text, nullable=True)
    
    # Relationships
    company = relationship("Company", back_populates="contacts")
    project = relationship("Project", back_populates="contacts")
    
    # Indexes for common queries
    __table_args__ = (
        Index('ix_contacts_company_email', 'company_id', 'email'),
        Index('ix_contacts_company_status', 'company_id', 'status'),
        Index('ix_contacts_company_segment', 'company_id', 'segment'),
        Index('ix_contacts_company_source', 'company_id', 'source'),
        Index('ix_contacts_company_project', 'company_id', 'project_id'),
        Index('ix_contacts_search', 'first_name', 'last_name', 'company_name'),
    )
