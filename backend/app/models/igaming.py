"""
iGaming Contact Database models.

Tables for managing conference contacts (SIGMA, ICE, SBC etc.),
companies aggregated from those contacts, and employees found via Clay/Apollo.
"""
import enum
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, Text, Boolean, Float,
    ForeignKey, Index, Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db import Base
from app.models.mixins import TimestampMixin, SoftDeleteMixin


# ── Enums ──────────────────────────────────────────────────────────────

class BusinessType(str, enum.Enum):
    OPERATOR = "operator"
    AFFILIATE = "affiliate"
    SUPPLIER = "supplier"
    PLATFORM = "platform"
    PAYMENT = "payment"
    MARKETING = "marketing"
    PROFESSIONAL_SERVICES = "professional_services"
    MEDIA = "media"
    REGULATOR = "regulator"
    OTHER = "other"


class IGamingImportStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class EmployeeSource(str, enum.Enum):
    CLAY = "clay"
    APOLLO = "apollo"
    MANUAL = "manual"
    IMPORT = "import"


# ── Normalization map ──────────────────────────────────────────────────

BUSINESS_TYPE_MAP: dict[str, BusinessType] = {
    # Operator variants
    "operator": BusinessType.OPERATOR,
    "OPERATOR": BusinessType.OPERATOR,
    "Operator (team involved in offering betting / games / slots to consumers)": BusinessType.OPERATOR,
    "Operator - Casino/Bookmaker/Sportsbook": BusinessType.OPERATOR,
    "Operator - Lottery": BusinessType.OPERATOR,
    "Operator - Bingo": BusinessType.OPERATOR,
    # Affiliate
    "affiliate": BusinessType.AFFILIATE,
    "AFFILIATE": BusinessType.AFFILIATE,
    "Affiliate": BusinessType.AFFILIATE,
    # Supplier
    "supplier": BusinessType.SUPPLIER,
    "Supplier (product, technology or service)": BusinessType.SUPPLIER,
    "Supplier/Service Provider": BusinessType.SUPPLIER,
    "GAME_PROVIDER": BusinessType.SUPPLIER,
    "Game Provider": BusinessType.SUPPLIER,
    # Platform
    "platform": BusinessType.PLATFORM,
    "PLATFORM": BusinessType.PLATFORM,
    # Payment
    "payment": BusinessType.PAYMENT,
    "PAYMENT": BusinessType.PAYMENT,
    "Payments": BusinessType.PAYMENT,
    # Marketing
    "marketing": BusinessType.MARKETING,
    "MARKETING": BusinessType.MARKETING,
    # Professional services
    "Professional Services (HR, Audit, Legal, Consultancy, Agency)": BusinessType.PROFESSIONAL_SERVICES,
    "professional_services": BusinessType.PROFESSIONAL_SERVICES,
    # Media
    "MEDIA": BusinessType.MEDIA,
    "Media": BusinessType.MEDIA,
    # Regulator
    "Regulator/Government Body": BusinessType.REGULATOR,
    "REGULATOR": BusinessType.REGULATOR,
    # Other / null
    "OTHER": BusinessType.OTHER,
    "Other (please specify in English)": BusinessType.OTHER,
    "organizationType:null": BusinessType.OTHER,
    "": BusinessType.OTHER,
}


def normalize_business_type(raw: str | None) -> BusinessType:
    """Normalize raw typeOfBusiness string to BusinessType enum."""
    if not raw or not raw.strip():
        return BusinessType.OTHER
    raw = raw.strip()
    if raw in BUSINESS_TYPE_MAP:
        return BUSINESS_TYPE_MAP[raw]
    # Fuzzy fallback
    lower = raw.lower()
    if "operator" in lower:
        return BusinessType.OPERATOR
    if "affiliate" in lower:
        return BusinessType.AFFILIATE
    if "supplier" in lower or "provider" in lower or "game_provider" in lower:
        return BusinessType.SUPPLIER
    if "platform" in lower:
        return BusinessType.PLATFORM
    if "payment" in lower:
        return BusinessType.PAYMENT
    if "marketing" in lower:
        return BusinessType.MARKETING
    if "media" in lower:
        return BusinessType.MEDIA
    if "professional" in lower or "legal" in lower or "consult" in lower:
        return BusinessType.PROFESSIONAL_SERVICES
    if "regul" in lower or "government" in lower:
        return BusinessType.REGULATOR
    return BusinessType.OTHER


def normalize_website(raw: str | None) -> str | None:
    """Clean website URL: strip, remove N/A, ensure no trailing slash."""
    if not raw or not raw.strip():
        return None
    val = raw.strip()
    if val.lower() in ("n/a", "na", "-", "none", "null", "n\\a", "n/ a"):
        return None
    # Remove trailing slash
    val = val.rstrip("/")
    # Remove protocol for storage, keep domain clean
    for prefix in ("https://www.", "http://www.", "https://", "http://", "www."):
        if val.lower().startswith(prefix):
            val = val[len(prefix):]
            break
    return val.rstrip("/") or None


# ── Models ─────────────────────────────────────────────────────────────

class IGamingCompany(Base, TimestampMixin):
    """Aggregated company from iGaming contacts. Only companies with website shown in Companies tab."""
    __tablename__ = "igaming_companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(500), nullable=False, index=True)
    name_normalized = Column(String(500), nullable=False, index=True)
    name_aliases = Column(JSONB, nullable=False, default=list)
    website = Column(String(500), nullable=True, index=True)
    business_type = Column(SQLEnum(BusinessType, values_callable=lambda e: [x.value for x in e]), nullable=True, index=True)
    business_type_raw = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    sector = Column(String(255), nullable=True)
    regions = Column(JSONB, nullable=True)
    headquarters = Column(String(255), nullable=True)
    contacts_count = Column(Integer, nullable=False, default=0)
    employees_count = Column(Integer, nullable=False, default=0)

    # Enrichment
    enrichment_data = Column(JSONB, nullable=True)
    clay_enriched_at = Column(DateTime, nullable=True)
    ai_enriched_at = Column(DateTime, nullable=True)

    # Custom AI columns stored as {"col_name": "value", ...}
    custom_fields = Column(JSONB, nullable=False, default=dict)

    # Relationships
    contacts = relationship("IGamingContact", back_populates="company",
                            order_by="desc(IGamingContact.created_at)")
    employees = relationship("IGamingEmployee", back_populates="company",
                             cascade="all, delete-orphan",
                             order_by="desc(IGamingEmployee.created_at)")

    __table_args__ = (
        Index("ix_igaming_companies_name_norm", "name_normalized"),
        Index("ix_igaming_companies_website", "website",
              postgresql_where="website IS NOT NULL"),
        Index("ix_igaming_companies_type", "business_type"),
    )

    @staticmethod
    def normalize_name(name: str) -> str:
        """Lowercase, strip whitespace and common suffixes for matching."""
        import re
        n = name.strip().lower()
        # Remove common suffixes
        for suffix in (" ltd", " ltd.", " inc", " inc.", " llc", " gmbh",
                       " ag", " ab", " plc", " s.a.", " sa", " bv", " b.v.",
                       " limited", " corp", " corp.", " co.", " group"):
            if n.endswith(suffix):
                n = n[:-len(suffix)].strip()
        # Remove extra whitespace
        n = re.sub(r"\s+", " ", n).strip()
        return n


class IGamingContact(Base, TimestampMixin, SoftDeleteMixin):
    """Individual contact from iGaming conference database."""
    __tablename__ = "igaming_contacts"

    id = Column(Integer, primary_key=True, index=True)

    # Identity
    source_id = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True, index=True)
    last_name = Column(String(255), nullable=True, index=True)
    email = Column(String(255), nullable=True, index=True)
    phone = Column(String(100), nullable=True)
    linkedin_url = Column(String(500), nullable=True)
    job_title = Column(String(500), nullable=True)
    bio = Column(Text, nullable=True)
    other_contact = Column(String(500), nullable=True)

    # Company (raw from CSV)
    organization_name = Column(String(500), nullable=True, index=True)
    website_url = Column(String(500), nullable=True)
    business_type_raw = Column(String(500), nullable=True)
    business_type = Column(SQLEnum(BusinessType, values_callable=lambda e: [x.value for x in e]), nullable=True, index=True)

    # Normalized company link
    company_id = Column(Integer, ForeignKey("igaming_companies.id", ondelete="SET NULL"),
                        nullable=True, index=True)

    # Conference / sector data
    source_conference = Column(String(255), nullable=True, index=True)
    source_file = Column(String(500), nullable=True)
    import_id = Column(Integer, ForeignKey("igaming_imports.id", ondelete="SET NULL"),
                       nullable=True, index=True)

    # Sector & geo from CSV
    sector = Column(String(500), nullable=True)
    regions = Column(JSONB, nullable=True)
    new_regions_targeting = Column(JSONB, nullable=True)
    channel = Column(String(255), nullable=True)
    products_services = Column(Text, nullable=True)

    # Flexible
    custom_fields = Column(JSONB, nullable=False, default=dict)
    tags = Column(JSONB, nullable=False, default=list)
    notes = Column(Text, nullable=True)

    # Relationships
    company = relationship("IGamingCompany", back_populates="contacts")

    __table_args__ = (
        Index("ix_igaming_contacts_email", "email",
              postgresql_where="email IS NOT NULL"),
        Index("ix_igaming_contacts_org", "organization_name"),
        Index("ix_igaming_contacts_source", "source_conference"),
        Index("ix_igaming_contacts_company", "company_id"),
        Index("ix_igaming_contacts_name", "first_name", "last_name"),
        Index("ix_igaming_contacts_import", "import_id"),
    )

    @property
    def full_name(self) -> str:
        parts = [p for p in (self.first_name, self.last_name) if p]
        return " ".join(parts) or ""


class IGamingEmployee(Base, TimestampMixin):
    """Employee found via Clay/Apollo for an iGaming company."""
    __tablename__ = "igaming_employees"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("igaming_companies.id", ondelete="CASCADE"),
                        nullable=False, index=True)

    full_name = Column(String(500), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    job_title = Column(String(500), nullable=True)
    email = Column(String(255), nullable=True, index=True)
    linkedin_url = Column(String(500), nullable=True)
    phone = Column(String(100), nullable=True)

    source = Column(SQLEnum(EmployeeSource, values_callable=lambda e: [x.value for x in e]), nullable=False, default=EmployeeSource.MANUAL)
    search_query = Column(Text, nullable=True)
    raw_data = Column(JSONB, nullable=True)

    # Relationships
    company = relationship("IGamingCompany", back_populates="employees")

    __table_args__ = (
        Index("ix_igaming_employees_company", "company_id"),
        Index("ix_igaming_employees_email", "email",
              postgresql_where="email IS NOT NULL"),
    )


class IGamingImport(Base, TimestampMixin):
    """Log of CSV/Excel imports."""
    __tablename__ = "igaming_imports"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(500), nullable=False)
    source_conference = Column(String(255), nullable=True)
    status = Column(SQLEnum(IGamingImportStatus, values_callable=lambda e: [x.value for x in e]), nullable=False,
                    default=IGamingImportStatus.PENDING)

    rows_total = Column(Integer, nullable=False, default=0)
    rows_imported = Column(Integer, nullable=False, default=0)
    rows_skipped = Column(Integer, nullable=False, default=0)
    rows_updated = Column(Integer, nullable=False, default=0)
    companies_created = Column(Integer, nullable=False, default=0)

    column_mapping = Column(JSONB, nullable=True)
    error_log = Column(JSONB, nullable=True)

    # Relationships
    contacts = relationship("IGamingContact", backref="import_log",
                            foreign_keys="IGamingContact.import_id")


class IGamingAIColumn(Base, TimestampMixin):
    """Definition of a custom AI-enriched column."""
    __tablename__ = "igaming_ai_columns"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    target = Column(String(50), nullable=False, default="contact")  # "contact" or "company"
    prompt_template = Column(Text, nullable=False)
    model = Column(String(100), nullable=False, default="gemini-2.5-flash")
    is_active = Column(Boolean, nullable=False, default=True)
    rows_processed = Column(Integer, nullable=False, default=0)
    rows_total = Column(Integer, nullable=False, default=0)
    status = Column(String(50), nullable=False, default="idle")  # idle, running, completed, failed
