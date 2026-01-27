"""
Knowledge Base Models - Company context for AI personalization
Refactored: Simplified structure with custom segment columns
All models are scoped to a company for data isolation.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Boolean, Enum as SQLEnum, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db import Base
import enum


class DocumentType(str, enum.Enum):
    PITCH_DECK = "pitch_deck"
    CASE_STUDY = "case_study"
    PRICING = "pricing"
    PRODUCT_INFO = "product_info"
    COMPETITOR_ANALYSIS = "competitor_analysis"
    EMAIL_TEMPLATES = "email_templates"
    OTHER = "other"


# ============ Documents with Folders ============

class DocumentFolder(Base):
    """Folders for organizing documents - scoped to company"""
    __tablename__ = "kb_document_folders"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    parent_id = Column(Integer, ForeignKey("kb_document_folders.id"), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    company = relationship("Company", back_populates="document_folders")
    documents = relationship("Document", back_populates="folder")


class Document(Base):
    """Uploaded documents that get parsed into markdown for AI - scoped to company"""
    __tablename__ = "kb_documents"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    original_filename = Column(String(255))
    document_type = Column(SQLEnum(DocumentType), default=DocumentType.OTHER)
    
    # Folder organization
    folder_id = Column(Integer, ForeignKey("kb_document_folders.id"), nullable=True)
    
    # Parsed content in markdown (for AI)
    content_md = Column(Text)
    
    # Raw extracted text
    raw_text = Column(Text)
    
    # Processing status
    status = Column(String(50), default="pending")  # pending, processing, processed, failed
    error_message = Column(Text)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    company = relationship("Company", back_populates="documents")
    folder = relationship("DocumentFolder", back_populates="documents")


# ============ Company Profile (Knowledge Base) ============

class CompanyProfile(Base):
    """
    Company info for Knowledge Base - simplified: just name, website, and auto-generated summary.
    This is the client's company profile for personalization, not the Company entity.
    One per company.
    """
    __tablename__ = "kb_company_profile"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, unique=True, index=True)
    
    name = Column(String(255))
    website = Column(String(255))
    
    # Auto-generated summary from all documents
    summary = Column(Text)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    company = relationship("Company", back_populates="company_profile")


# ============ Products (New) ============

class Product(Base):
    """Products/Services we sell - scoped to company"""
    __tablename__ = "kb_products"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    
    name = Column(String(255), nullable=False)
    description = Column(Text)
    
    # Features list
    features = Column(JSON)  # ["Feature 1", "Feature 2"]
    
    # Pricing info for this product
    pricing = Column(JSON)  # {"price": "$500/mo", "billing": "monthly", "tiers": [...]}
    
    # Target segments
    target_segment_ids = Column(JSON)  # [1, 2, 3]
    
    # For email snippets
    email_snippet = Column(Text)
    
    is_active = Column(Boolean, default=True, index=True)
    deleted_at = Column(DateTime, nullable=True, index=True)
    sort_order = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    company = relationship("Company", back_populates="products")


# ============ Segments (Table-like with Custom Columns) ============

class SegmentColumn(Base):
    """Custom columns for segments table - scoped to company"""
    __tablename__ = "kb_segment_columns"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    
    name = Column(String(100), nullable=False)  # Column key (snake_case)
    display_name = Column(String(255), nullable=False)  # Display name
    column_type = Column(String(50), default="text")  # text, number, list, rich_text, case_select
    is_system = Column(Boolean, default=False)  # System columns can't be deleted
    is_required = Column(Boolean, default=False)
    sort_order = Column(Integer, default=0)
    
    # For list type - predefined options
    options = Column(JSON)  # ["Option 1", "Option 2"]
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    company = relationship("Company", back_populates="segment_columns")


class Segment(Base):
    """
    Target segments with flexible data structure - scoped to company.
    Works like a spreadsheet row - data stored in JSON.
    """
    __tablename__ = "kb_segments"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    
    # All segment data stored as JSON (column_name -> value)
    data = Column(JSON, default=dict)
    
    # Quick access to name (also in data)
    name = Column(String(255), nullable=False, index=True)
    
    is_active = Column(Boolean, default=True, index=True)
    deleted_at = Column(DateTime, nullable=True, index=True)
    sort_order = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    company = relationship("Company", back_populates="segments")


# ============ Competitors ============

class Competitor(Base):
    """Competitor analysis - import from CSV - scoped to company"""
    __tablename__ = "kb_competitors"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    
    name = Column(String(255), nullable=False)
    website = Column(String(255))
    description = Column(Text)
    
    # Competitive analysis
    their_strengths = Column(JSON)  # List
    their_weaknesses = Column(JSON)  # List
    our_advantages = Column(JSON)  # List
    
    # Positioning
    their_positioning = Column(Text)
    price_comparison = Column(Text)
    
    notes = Column(Text)
    
    # Soft delete support
    is_active = Column(Boolean, default=True, index=True)
    deleted_at = Column(DateTime, nullable=True, index=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    company = relationship("Company", back_populates="competitors")


# ============ Case Studies ============

class CaseStudy(Base):
    """Customer success stories - free-form cards - scoped to company"""
    __tablename__ = "kb_case_studies"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    
    # Client info
    client_name = Column(String(255), nullable=False)
    client_website = Column(String(255))
    client_industry = Column(String(255))
    client_size = Column(String(100))
    
    # The story (free-form)
    challenge = Column(Text)
    solution = Column(Text)
    results = Column(Text)
    
    # Metrics
    key_metrics = Column(JSON)  # {"metric": "value"}
    
    # Quotes
    testimonial = Column(Text)
    testimonial_author = Column(String(255))
    testimonial_title = Column(String(255))
    
    # For email snippets
    email_snippet = Column(Text)
    
    is_public = Column(Boolean, default=True)  # Can we mention the name?
    
    # Soft delete support
    is_active = Column(Boolean, default=True, index=True)
    deleted_at = Column(DateTime, nullable=True, index=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    company = relationship("Company", back_populates="case_studies")


# ============ Voice & Tone ============

class VoiceTone(Base):
    """Voice and tone settings for messaging - scoped to company"""
    __tablename__ = "kb_voice_tones"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    
    name = Column(String(255), nullable=False)
    description = Column(Text)
    
    # Style guidelines
    personality_traits = Column(JSON)  # ["professional", "helpful"]
    writing_style = Column(Text)
    
    # Do's and Don'ts
    do_use = Column(JSON)  # Words/phrases to use
    dont_use = Column(JSON)  # Words/phrases to avoid
    
    # Examples
    example_messages = Column(JSON)
    
    # Settings
    formality_level = Column(Integer, default=5)  # 1-10
    emoji_usage = Column(Boolean, default=False)
    
    is_default = Column(Boolean, default=False)
    
    # Soft delete support
    is_active = Column(Boolean, default=True, index=True)
    deleted_at = Column(DateTime, nullable=True, index=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    company = relationship("Company", back_populates="voice_tones")


# ============ Booking Links (Simplified) ============

class BookingLink(Base):
    """Booking links - simplified: name, url, when to use - scoped to company"""
    __tablename__ = "kb_booking_links"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    
    name = Column(String(255), nullable=False)
    url = Column(String(500), nullable=False)
    when_to_use = Column(Text)  # Free-form description
    
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    company = relationship("Company", back_populates="booking_links")


# ============ Blocklist (Extended) ============

class Blocklist(Base):
    """Domains and emails to never contact - scoped to company"""
    __tablename__ = "kb_blocklist"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    
    # Can have domain OR email OR both
    domain = Column(String(255), nullable=True, index=True)
    email = Column(String(255), nullable=True, index=True)
    
    company_name = Column(String(255))
    reason = Column(Text)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    company = relationship("Company", back_populates="blocklist")


# System columns for segments (created on first run)
DEFAULT_SEGMENT_COLUMNS = [
    {"name": "name", "display_name": "Segment Name", "column_type": "text", "is_system": True, "is_required": True, "sort_order": 0},
    {"name": "description", "display_name": "Description", "column_type": "rich_text", "is_system": True, "sort_order": 1},
    {"name": "employee_count", "display_name": "Employee Count", "column_type": "text", "is_system": False, "sort_order": 2},
    {"name": "revenue", "display_name": "Revenue", "column_type": "text", "is_system": False, "sort_order": 3},
    {"name": "target_countries", "display_name": "Target Countries", "column_type": "list", "is_system": False, "sort_order": 4},
    {"name": "target_job_titles", "display_name": "Target Job Titles", "column_type": "list", "is_system": False, "sort_order": 5},
    {"name": "example_companies", "display_name": "Example Companies", "column_type": "list", "is_system": False, "sort_order": 6},
    {"name": "problems_we_solve", "display_name": "Problems We Solve", "column_type": "list", "is_system": False, "sort_order": 7},
    {"name": "what_they_need", "display_name": "What They Need", "column_type": "list", "is_system": False, "sort_order": 8},
    {"name": "our_offer", "display_name": "Our Offer", "column_type": "list", "is_system": False, "sort_order": 9},
    {"name": "differentiators", "display_name": "Differentiators", "column_type": "list", "is_system": False, "sort_order": 10},
    {"name": "social_proof", "display_name": "Social Proof", "column_type": "list", "is_system": False, "sort_order": 11},
    {"name": "case_study_ids", "display_name": "Case Studies", "column_type": "case_select", "is_system": False, "sort_order": 12},
    {"name": "email_sequence", "display_name": "Email Sequence", "column_type": "rich_text", "is_system": False, "sort_order": 13},
    {"name": "pricing", "display_name": "Pricing", "column_type": "rich_text", "is_system": False, "sort_order": 14},
    {"name": "notes", "display_name": "Notes", "column_type": "rich_text", "is_system": False, "sort_order": 15},
]
