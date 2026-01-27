"""
Knowledge Base Schemas - Refactored
"""
from pydantic import BaseModel
from typing import Optional, List, Any, Dict
from datetime import datetime
from enum import Enum


class DocumentType(str, Enum):
    PITCH_DECK = "pitch_deck"
    CASE_STUDY = "case_study"
    PRICING = "pricing"
    PRODUCT_INFO = "product_info"
    COMPETITOR_ANALYSIS = "competitor_analysis"
    EMAIL_TEMPLATES = "email_templates"
    OTHER = "other"


# ============ Document Folder Schemas ============

class DocumentFolderBase(BaseModel):
    name: str
    parent_id: Optional[int] = None


class DocumentFolderCreate(DocumentFolderBase):
    pass


class DocumentFolderResponse(DocumentFolderBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True


# ============ Document Schemas ============

class DocumentBase(BaseModel):
    name: str
    document_type: DocumentType = DocumentType.OTHER
    folder_id: Optional[int] = None


class DocumentCreate(DocumentBase):
    pass


class DocumentUpdate(BaseModel):
    name: Optional[str] = None
    document_type: Optional[DocumentType] = None
    folder_id: Optional[int] = None


class DocumentResponse(DocumentBase):
    id: int
    original_filename: Optional[str]
    content_md: Optional[str]
    status: str
    error_message: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True


# ============ Company Profile Schemas (Simplified) ============

class CompanyProfileBase(BaseModel):
    name: Optional[str] = None
    website: Optional[str] = None
    summary: Optional[str] = None


class CompanyProfileCreate(CompanyProfileBase):
    pass


class CompanyProfileUpdate(CompanyProfileBase):
    pass


class CompanyProfileResponse(CompanyProfileBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True


# ============ Product Schemas ============

class ProductBase(BaseModel):
    name: str
    description: Optional[str] = None
    features: Optional[List[str]] = None
    pricing: Optional[Dict[str, Any]] = None
    target_segment_ids: Optional[List[int]] = None
    email_snippet: Optional[str] = None
    is_active: bool = True
    sort_order: int = 0


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    features: Optional[List[str]] = None
    pricing: Optional[Dict[str, Any]] = None
    target_segment_ids: Optional[List[int]] = None
    email_snippet: Optional[str] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


class ProductResponse(ProductBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True


# ============ Segment Column Schemas ============

class SegmentColumnBase(BaseModel):
    name: str
    display_name: str
    column_type: str = "text"  # text, number, list, rich_text, case_select
    is_required: bool = False
    sort_order: int = 0
    options: Optional[List[str]] = None


class SegmentColumnCreate(SegmentColumnBase):
    pass


class SegmentColumnUpdate(BaseModel):
    display_name: Optional[str] = None
    column_type: Optional[str] = None
    is_required: Optional[bool] = None
    sort_order: Optional[int] = None
    options: Optional[List[str]] = None


class SegmentColumnResponse(SegmentColumnBase):
    id: int
    is_system: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


# ============ Segment Schemas ============

class SegmentBase(BaseModel):
    name: str
    data: Dict[str, Any] = {}
    is_active: bool = True
    sort_order: int = 0


class SegmentCreate(SegmentBase):
    pass


class SegmentUpdate(BaseModel):
    name: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


class SegmentResponse(SegmentBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True


# ============ Competitor Schemas ============

class CompetitorBase(BaseModel):
    name: str
    website: Optional[str] = None
    description: Optional[str] = None
    their_strengths: Optional[List[str]] = None
    their_weaknesses: Optional[List[str]] = None
    our_advantages: Optional[List[str]] = None
    their_positioning: Optional[str] = None
    price_comparison: Optional[str] = None
    notes: Optional[str] = None


class CompetitorCreate(CompetitorBase):
    pass


class CompetitorUpdate(BaseModel):
    name: Optional[str] = None
    website: Optional[str] = None
    description: Optional[str] = None
    their_strengths: Optional[List[str]] = None
    their_weaknesses: Optional[List[str]] = None
    our_advantages: Optional[List[str]] = None
    their_positioning: Optional[str] = None
    price_comparison: Optional[str] = None
    notes: Optional[str] = None


class CompetitorResponse(CompetitorBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True


# ============ Case Study Schemas ============

class CaseStudyBase(BaseModel):
    client_name: str
    client_website: Optional[str] = None
    client_industry: Optional[str] = None
    client_size: Optional[str] = None
    challenge: Optional[str] = None
    solution: Optional[str] = None
    results: Optional[str] = None
    key_metrics: Optional[Dict[str, str]] = None
    testimonial: Optional[str] = None
    testimonial_author: Optional[str] = None
    testimonial_title: Optional[str] = None
    email_snippet: Optional[str] = None
    is_public: bool = True


class CaseStudyCreate(CaseStudyBase):
    pass


class CaseStudyUpdate(BaseModel):
    client_name: Optional[str] = None
    client_website: Optional[str] = None
    client_industry: Optional[str] = None
    client_size: Optional[str] = None
    challenge: Optional[str] = None
    solution: Optional[str] = None
    results: Optional[str] = None
    key_metrics: Optional[Dict[str, str]] = None
    testimonial: Optional[str] = None
    testimonial_author: Optional[str] = None
    testimonial_title: Optional[str] = None
    email_snippet: Optional[str] = None
    is_public: Optional[bool] = None


class CaseStudyResponse(CaseStudyBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True


# ============ Voice Tone Schemas ============

class VoiceToneBase(BaseModel):
    name: str
    description: Optional[str] = None
    personality_traits: Optional[List[str]] = None
    writing_style: Optional[str] = None
    do_use: Optional[List[str]] = None
    dont_use: Optional[List[str]] = None
    example_messages: Optional[List[str]] = None
    formality_level: int = 5
    emoji_usage: bool = False
    is_default: bool = False


class VoiceToneCreate(VoiceToneBase):
    pass


class VoiceToneUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    personality_traits: Optional[List[str]] = None
    writing_style: Optional[str] = None
    do_use: Optional[List[str]] = None
    dont_use: Optional[List[str]] = None
    example_messages: Optional[List[str]] = None
    formality_level: Optional[int] = None
    emoji_usage: Optional[bool] = None
    is_default: Optional[bool] = None


class VoiceToneResponse(VoiceToneBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True


# ============ Booking Link Schemas (Simplified) ============

class BookingLinkBase(BaseModel):
    name: str
    url: str
    when_to_use: Optional[str] = None
    is_active: bool = True


class BookingLinkCreate(BookingLinkBase):
    pass


class BookingLinkUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    when_to_use: Optional[str] = None
    is_active: Optional[bool] = None


class BookingLinkResponse(BookingLinkBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True


# ============ Blocklist Schemas (Extended) ============

class BlocklistBase(BaseModel):
    domain: Optional[str] = None
    email: Optional[str] = None
    company_name: Optional[str] = None
    reason: Optional[str] = None


class BlocklistCreate(BlocklistBase):
    pass


class BlocklistResponse(BlocklistBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True


# ============ Import/Export Schemas ============

class CSVImportResult(BaseModel):
    success: bool
    imported_count: int
    errors: List[str] = []


class AIImportRequest(BaseModel):
    text: str
    entity_type: str
    save_to_db: bool = False
    parse_multiple: bool = False


class AIImportResponse(BaseModel):
    success: bool
    entity_type: str
    data: Optional[Dict[str, Any]] = None
    saved_ids: Optional[List[int]] = None
    error: Optional[str] = None
    tokens_used: int = 0


# ============ Export Schema ============

class KnowledgeBaseExport(BaseModel):
    company: Optional[CompanyProfileResponse] = None
    products: List[ProductResponse] = []
    segments: List[SegmentResponse] = []
    segment_columns: List[SegmentColumnResponse] = []
    competitors: List[CompetitorResponse] = []
    case_studies: List[CaseStudyResponse] = []
    voice_tones: List[VoiceToneResponse] = []
    booking_links: List[BookingLinkResponse] = []
    blocklist: List[BlocklistResponse] = []
    documents: List[DocumentResponse] = []
