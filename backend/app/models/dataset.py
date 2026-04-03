from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, ForeignKey, Boolean, Enum as SQLEnum, Index
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.db import Base


class EnrichmentStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class Folder(Base):
    """Folder for organizing datasets - scoped to company"""
    __tablename__ = "folders"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    parent_id = Column(Integer, ForeignKey("folders.id", ondelete="SET NULL"), nullable=True)
    
    # Soft delete support
    is_active = Column(Boolean, default=True, index=True)
    deleted_at = Column(DateTime, nullable=True, index=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    company = relationship("Company", back_populates="folders")
    datasets = relationship("Dataset", back_populates="folder")
    children = relationship("Folder", back_populates="parent", cascade="all, delete-orphan")
    parent = relationship("Folder", back_populates="children", remote_side=[id])


class Dataset(Base):
    """Represents an imported CSV/Google Sheet dataset - scoped to company"""
    __tablename__ = "datasets"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    source_type = Column(String(50), nullable=False)  # 'csv', 'google_sheets'
    source_url = Column(Text, nullable=True)  # For Google Sheets
    original_filename = Column(String(255), nullable=True)
    folder_id = Column(Integer, ForeignKey("folders.id", ondelete="SET NULL"), nullable=True)
    
    # Column schema stored as JSON
    columns = Column(JSON, nullable=False, default=list)
    
    row_count = Column(Integer, default=0)
    
    # Soft delete support (consistent with other models)
    is_active = Column(Boolean, default=True, index=True)
    deleted_at = Column(DateTime, nullable=True, index=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    company = relationship("Company", back_populates="datasets")
    rows = relationship("DataRow", back_populates="dataset", cascade="all, delete-orphan")
    enrichment_jobs = relationship("EnrichmentJob", back_populates="dataset", cascade="all, delete-orphan")
    folder = relationship("Folder", back_populates="datasets")


class DataRow(Base):
    """Individual row in a dataset"""
    __tablename__ = "data_rows"
    
    id = Column(Integer, primary_key=True, index=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    row_index = Column(Integer, nullable=False)  # Original row position
    
    # All data stored as JSON for flexibility
    data = Column(JSON, nullable=False, default=dict)
    
    # Enriched data stored separately
    enriched_data = Column(JSON, nullable=False, default=dict)
    
    # Status tracking
    enrichment_status = Column(SQLEnum(EnrichmentStatus), default=EnrichmentStatus.PENDING)
    last_enriched_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    dataset = relationship("Dataset", back_populates="rows")


class PromptTemplate(Base):
    """
    Reusable prompt templates for enrichment.
    SHARED across all companies for a user - not company-scoped.
    """
    __tablename__ = "prompt_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True)  # Deprecated, use tags instead
    tags = Column(JSON, nullable=True, default=list)  # List of tags for filtering
    
    # The prompt template with placeholders like {{column_name}}
    prompt_template = Column(Text, nullable=False)
    
    # Expected output column name
    output_column = Column(String(255), nullable=False)
    
    # System prompt for OpenAI
    system_prompt = Column(Text, nullable=True)
    
    is_system = Column(Boolean, default=False)  # Built-in templates
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Index for unique name per user (system templates have no user)
    __table_args__ = (
        Index('ix_prompt_templates_user_name', 'user_id', 'name', unique=True),
    )


class IntegrationSetting(Base):
    """
    Stores integration API keys and settings.
    SHARED across all companies for a user - not company-scoped.
    """
    __tablename__ = "integration_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    integration_name = Column(String(100), nullable=False)  # 'instantly', 'findymail', etc.
    api_key = Column(Text, nullable=True)
    is_connected = Column(Boolean, default=False)
    settings = Column(JSON, nullable=True, default=dict)  # Additional settings
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Unique integration per user
    __table_args__ = (
        Index('ix_integration_settings_user_name', 'user_id', 'integration_name', unique=True),
    )


class EnrichmentJob(Base):
    """Tracks enrichment job progress"""
    __tablename__ = "enrichment_jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    
    # Job configuration
    prompt_template_id = Column(Integer, ForeignKey("prompt_templates.id"), nullable=True)
    custom_prompt = Column(Text, nullable=True)
    output_column = Column(String(255), nullable=False)
    model = Column(String(100), nullable=False)
    
    # Row selection
    selected_row_ids = Column(JSON, nullable=True)  # null = all rows
    
    # Progress tracking
    status = Column(SQLEnum(EnrichmentStatus), default=EnrichmentStatus.PENDING)
    total_rows = Column(Integer, default=0)
    processed_rows = Column(Integer, default=0)
    failed_rows = Column(Integer, default=0)
    
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    dataset = relationship("Dataset", back_populates="enrichment_jobs")
    prompt_template = relationship("PromptTemplate")
