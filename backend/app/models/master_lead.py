from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Index
from datetime import datetime
from app.db import Base


class MasterLead(Base):
    """
    Centralized lead database - stores all leads from various sources
    with standardized fields and deduplication support.
    """
    __tablename__ = "master_leads"
    
    id = Column(Integer, primary_key=True, index=True)
    
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
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Composite index for name+company dedup
    __table_args__ = (
        Index('ix_master_leads_name_company', 'first_name', 'last_name', 'company_name'),
        Index('ix_master_leads_full_name_company', 'full_name', 'company_name'),
    )
