"""
User, Environment, and Company models for multi-tenant architecture.
Hierarchy: User → Environment → Company
Provides data isolation per company while sharing templates and settings across companies.
"""
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, ForeignKey, Boolean, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db import Base


class User(Base):
    """
    User account - for activity tracking and future authentication.
    Currently operates with a single default user.
    """
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=True, index=True)
    name = Column(String(255), nullable=False)
    
    # For future auth
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    environments = relationship("Environment", back_populates="owner", cascade="all, delete-orphan")
    companies = relationship("Company", back_populates="owner", cascade="all, delete-orphan")
    activity_logs = relationship("UserActivityLog", back_populates="user", cascade="all, delete-orphan")


class Environment(Base):
    """
    Environment/Workspace - groups companies for isolation.
    Use case: Separate workspace per client to avoid showing other clients' companies.
    """
    __tablename__ = "environments"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    color = Column(String(7), nullable=True)  # Hex color for UI
    icon = Column(String(50), nullable=True)  # Icon name for UI
    
    # Soft delete support
    is_active = Column(Boolean, default=True)
    deleted_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    owner = relationship("User", back_populates="environments")
    # companies = relationship("Company", back_populates="environment", cascade="all, delete-orphan")


class Company(Base):
    """
    Company/Project - isolated workspace for a client.
    All data (prospects, datasets, knowledge base) is scoped to a company.
    Belongs to an Environment for additional isolation.
    """
    __tablename__ = "companies"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    environment_id = Column(Integer, ForeignKey("environments.id", ondelete="SET NULL"), nullable=True, index=True)
    
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    website = Column(String(255), nullable=True)
    logo_url = Column(String(500), nullable=True)
    color = Column(String(7), nullable=True)  # Hex color for UI (e.g., #3B82F6)
    
    # Soft delete support
    is_active = Column(Boolean, default=True)
    deleted_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    owner = relationship("User", back_populates="companies")
    # environment = relationship("Environment", back_populates="companies")
    activity_logs = relationship("UserActivityLog", back_populates="company", cascade="all, delete-orphan")
    
    # Data relationships (will be added via backref in respective models)
    datasets = relationship("Dataset", back_populates="company", cascade="all, delete-orphan")
    folders = relationship("Folder", back_populates="company", cascade="all, delete-orphan")
    prospects = relationship("Prospect", back_populates="company", cascade="all, delete-orphan")
    
    # Knowledge Base relationships
    documents = relationship("Document", back_populates="company", cascade="all, delete-orphan")
    document_folders = relationship("DocumentFolder", back_populates="company", cascade="all, delete-orphan")
    company_profile = relationship("CompanyProfile", back_populates="company", uselist=False, cascade="all, delete-orphan")
    products = relationship("Product", back_populates="company", cascade="all, delete-orphan")
    segments = relationship("Segment", back_populates="company", cascade="all, delete-orphan")
    segment_columns = relationship("SegmentColumn", back_populates="company", cascade="all, delete-orphan")
    competitors = relationship("Competitor", back_populates="company", cascade="all, delete-orphan")
    case_studies = relationship("CaseStudy", back_populates="company", cascade="all, delete-orphan")
    voice_tones = relationship("VoiceTone", back_populates="company", cascade="all, delete-orphan")
    booking_links = relationship("BookingLink", back_populates="company", cascade="all, delete-orphan")
    blocklist = relationship("Blocklist", back_populates="company", cascade="all, delete-orphan")
    
    # Reply Automation
    reply_automations = relationship("ReplyAutomation", back_populates="company", cascade="all, delete-orphan")
    
    # CRM
    projects = relationship("Project", back_populates="company", cascade="all, delete-orphan")
    contacts = relationship("Contact", back_populates="company", cascade="all, delete-orphan")


class UserActivityLog(Base):
    """
    Activity log for tracking all user actions.
    Essential for debugging, auditing, and understanding user behavior.
    """
    __tablename__ = "user_activity_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Action details
    action = Column(String(100), nullable=False)  # create, update, delete, export, import, enrich, view
    entity_type = Column(String(100), nullable=True)  # prospect, dataset, document, company, etc.
    entity_id = Column(Integer, nullable=True)
    
    # Additional context
    details = Column(JSON, nullable=True)  # {"old_value": ..., "new_value": ..., "count": ..., etc.}
    
    # Request metadata
    ip_address = Column(String(45), nullable=True)  # IPv6 compatible
    user_agent = Column(String(500), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    user = relationship("User", back_populates="activity_logs")
    company = relationship("Company", back_populates="activity_logs")
    
    # Indexes for common queries
    __table_args__ = (
        Index('ix_activity_logs_user_company', 'user_id', 'company_id'),
        Index('ix_activity_logs_action_type', 'action', 'entity_type'),
        Index('ix_activity_logs_created_desc', created_at.desc()),
    )
