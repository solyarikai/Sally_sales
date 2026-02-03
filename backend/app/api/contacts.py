"""
CRM Contacts API endpoints
Simple flat table with filters - project, segment, status, source
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Body, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, String
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, EmailStr
from datetime import datetime
import csv
import io
import re
import logging

from app.db import get_session
from app.models.contact import Contact, Project, ContactActivity
from app.models import Company
from app.api.companies import get_required_company
from fastapi import Header
from typing import Annotated

async def get_optional_company_id(x_company_id: Annotated[str | None, Header()] = None) -> int | None:
    """Get optional company ID from header - returns None if not provided."""
    if x_company_id:
        try:
            return int(x_company_id)
        except ValueError:
            return None
    return None
from app.services.ai_sdr_service import ai_sdr_service

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/contacts", tags=["Contacts"])


# ============= Pydantic Schemas =============

class ContactBase(BaseModel):
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company_name: Optional[str] = None
    domain: Optional[str] = None
    job_title: Optional[str] = None
    segment: Optional[str] = None
    project_id: Optional[int] = None
    source: str = "manual"
    source_id: Optional[str] = None
    status: str = "lead"
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    smartlead_id: Optional[str] = None
    getsales_id: Optional[str] = None
    has_replied: Optional[bool] = None
    needs_followup: Optional[bool] = None
    campaigns: Optional[List[Dict[str, Any]]] = None


class ContactCreate(ContactBase):
    pass


class ContactUpdate(BaseModel):
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company_name: Optional[str] = None
    domain: Optional[str] = None
    job_title: Optional[str] = None
    segment: Optional[str] = None
    project_id: Optional[int] = None
    source: Optional[str] = None
    status: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    smartlead_id: Optional[str] = None
    getsales_id: Optional[str] = None
    has_replied: Optional[bool] = None
    needs_followup: Optional[bool] = None
    campaigns: Optional[List[Dict[str, Any]]] = None


class ContactResponse(BaseModel):
    id: int
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company_name: Optional[str] = None
    domain: Optional[str] = None
    job_title: Optional[str] = None
    segment: Optional[str] = None
    project_id: Optional[int] = None
    project_name: Optional[str] = None
    source: str
    source_id: Optional[str] = None
    status: str
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    smartlead_id: Optional[str] = None
    getsales_id: Optional[str] = None
    has_replied: Optional[bool] = None
    needs_followup: Optional[bool] = None
    campaigns: Optional[List[Dict[str, Any]]] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ContactListResponse(BaseModel):
    contacts: List[ContactResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ProjectBase(BaseModel):
    name: str
    description: Optional[str] = None
    target_industries: Optional[str] = None
    target_segments: Optional[str] = None


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    target_industries: Optional[str] = None
    target_segments: Optional[str] = None


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    target_industries: Optional[str] = None
    target_segments: Optional[str] = None
    contact_count: int = 0
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ContactStats(BaseModel):
    total: int
    by_status: Dict[str, int]
    by_segment: Dict[str, int]
    by_source: Dict[str, int]
    by_project: Dict[str, int]


class ProjectContactAnalysis(BaseModel):
    """Detailed contact analysis for a project - all done with Python/SQL, no AI."""
    project_id: int
    project_name: str
    total_contacts: int
    
    # Breakdowns
    by_segment: Dict[str, int]
    by_status: Dict[str, int]
    by_source: Dict[str, int]
    
    # Company analysis
    unique_companies: int
    top_companies: List[Dict[str, Any]]  # name, count, domain
    
    # Role analysis
    unique_job_titles: int
    top_job_titles: List[Dict[str, Any]]  # title, count
    
    # Location analysis
    unique_locations: int
    top_locations: List[Dict[str, Any]]  # location, count
    
    # Domain analysis
    unique_domains: int
    top_domains: List[Dict[str, Any]]  # domain, count


# ============= Status and Segment Constants =============

CONTACT_STATUSES = ["lead", "contacted", "replied", "qualified", "customer", "lost"]
CONTACT_SOURCES = ["manual", "smartlead", "apollo", "csv", "api"]
DEFAULT_SEGMENTS = ["iGaming", "B2B SaaS", "FinTech", "E-commerce", "Healthcare", "Other"]


# ============= Contacts Endpoints =============

@router.get("", response_model=ContactListResponse)
async def list_contacts(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    search: Optional[str] = Query(None),
    # Filters
    project_id: Optional[int] = Query(None),
    segment: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    has_replied: Optional[bool] = Query(None, description="Filter by replied status"),
    has_smartlead: Optional[bool] = Query(None, description="Filter contacts with Smartlead history"),
    has_getsales: Optional[bool] = Query(None, description="Filter contacts with GetSales history"),
    campaign: Optional[str] = Query(None, description="Filter by campaign name (partial match)"),
    needs_followup: Optional[bool] = Query(None, description="Filter contacts needing follow-up (no reply in 3+ days)"),
    session: AsyncSession = Depends(get_session),
    company_id: int | None = Depends(get_optional_company_id),
):
    """Get paginated list of contacts with filters"""
    
    # Base query
    query = select(Contact).where(
        and_(
            Contact.company_id == company_id if company_id else True,
            Contact.deleted_at.is_(None)
        )
    )
    
    # Apply filters
    if project_id:
        query = query.where(Contact.project_id == project_id)
    if segment:
        query = query.where(Contact.segment == segment)
    if status:
        query = query.where(Contact.status == status)
    if source:
        query = query.where(Contact.source == source)
    if has_replied is not None:
        query = query.where(Contact.has_replied == has_replied)
    if has_smartlead is True:
        # Contacts with Smartlead ID (uploaded to Smartlead)
        query = query.where(Contact.smartlead_id.isnot(None))
    elif has_smartlead is False:
        query = query.where(Contact.smartlead_id.is_(None))
    if has_getsales is True:
        # Contacts with GetSales ID (uploaded to GetSales)
        query = query.where(Contact.getsales_id.isnot(None))
    elif has_getsales is False:
        query = query.where(Contact.getsales_id.is_(None))
    if campaign:
        # Filter by campaign name using JSON contains
        query = query.where(
            Contact.campaigns.cast(String).ilike(f'%{campaign}%')
        )
    if needs_followup is True:
        # Contacts that haven't replied and were synced more than 3 days ago
        from datetime import timedelta
        three_days_ago = datetime.utcnow() - timedelta(days=3)
        query = query.where(
            and_(
                Contact.has_replied == False,
                Contact.last_synced_at < three_days_ago
            )
        )
    
    # Search
    if search:
        search_term = f"%{search}%"
        query = query.where(
            or_(
                Contact.email.ilike(search_term),
                Contact.first_name.ilike(search_term),
                Contact.last_name.ilike(search_term),
                Contact.company_name.ilike(search_term),
                Contact.domain.ilike(search_term),
            )
        )
    
    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0
    
    # Sorting
    sort_column = getattr(Contact, sort_by, Contact.created_at)
    if sort_order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())
    
    # Pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    
    result = await session.execute(query)
    contacts = result.scalars().all()
    
    # Enrich with project names
    project_ids = list(set(c.project_id for c in contacts if c.project_id))
    project_names = {}
    if project_ids:
        proj_result = await session.execute(
            select(Project).where(Project.id.in_(project_ids))
        )
        for proj in proj_result.scalars().all():
            project_names[proj.id] = proj.name
    
    # Build response
    contact_responses = []
    for contact in contacts:
        response = ContactResponse.model_validate(contact)
        if contact.project_id:
            response.project_name = project_names.get(contact.project_id)
        contact_responses.append(response)
    
    total_pages = (total + page_size - 1) // page_size
    
    return ContactListResponse(
        contacts=contact_responses,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get("/stats", response_model=ContactStats)
async def get_contact_stats(
    session: AsyncSession = Depends(get_session),
    company_id: int | None = Depends(get_optional_company_id),
):
    """Get contact statistics"""
    
    base_filter = and_(Contact.company_id == company_id if company_id else True, Contact.deleted_at.is_(None))
    
    # Total count
    total_result = await session.execute(
        select(func.count()).where(base_filter)
    )
    total = total_result.scalar() or 0
    
    # By status
    status_result = await session.execute(
        select(Contact.status, func.count())
        .where(base_filter)
        .group_by(Contact.status)
    )
    by_status = {row[0]: row[1] for row in status_result.all() if row[0]}
    
    # By segment
    segment_result = await session.execute(
        select(Contact.segment, func.count())
        .where(base_filter)
        .group_by(Contact.segment)
    )
    by_segment = {row[0] or "Unassigned": row[1] for row in segment_result.all()}
    
    # By source
    source_result = await session.execute(
        select(Contact.source, func.count())
        .where(base_filter)
        .group_by(Contact.source)
    )
    by_source = {row[0]: row[1] for row in source_result.all() if row[0]}
    
    # By project
    project_result = await session.execute(
        select(Project.name, func.count(Contact.id))
        .select_from(Contact)
        .outerjoin(Project, Contact.project_id == Project.id)
        .where(base_filter)
        .group_by(Project.name)
    )
    by_project = {row[0] or "Unassigned": row[1] for row in project_result.all()}
    
    return ContactStats(
        total=total,
        by_status=by_status,
        by_segment=by_segment,
        by_source=by_source,
        by_project=by_project,
    )


@router.get("/filters")
async def get_filter_options(
    session: AsyncSession = Depends(get_session),
    company_id: int | None = Depends(get_optional_company_id),
):
    """Get available filter options for dropdowns"""
    
    base_filter = and_(Contact.company_id == company_id if company_id else True, Contact.deleted_at.is_(None))
    
    # Get unique segments
    segments_result = await session.execute(
        select(Contact.segment).where(base_filter).distinct()
    )
    segments = [r[0] for r in segments_result.all() if r[0]]
    
    # Get unique sources
    sources_result = await session.execute(
        select(Contact.source).where(base_filter).distinct()
    )
    sources = [r[0] for r in sources_result.all() if r[0]]
    
    # Get projects
    projects_result = await session.execute(
        select(Project.id, Project.name)
        .where(and_(Project.company_id == company.id, Project.deleted_at.is_(None)))
        .order_by(Project.name)
    )
    projects = [{"id": r[0], "name": r[1]} for r in projects_result.all()]
    
    return {
        "statuses": CONTACT_STATUSES,
        "sources": sources if sources else CONTACT_SOURCES,
        "segments": segments if segments else DEFAULT_SEGMENTS,
        "projects": projects,
    }

@router.get("/campaigns")
async def get_campaigns_list(
    session: AsyncSession = Depends(get_session),
    source: Optional[str] = Query(None, description="Filter by source: smartlead or getsales"),
):
    """
    Get list of unique campaign names for autocomplete.
    """
    # Query all contacts with campaigns
    result = await session.execute(
        select(Contact.campaigns).where(
            and_(
                Contact.campaigns.isnot(None),
                Contact.deleted_at.is_(None)
            )
        )
    )
    
    # Extract unique campaign names
    campaigns_set = set()
    for row in result.scalars():
        if row:
            for camp in row:
                name = camp.get("name")
                camp_source = camp.get("source")
                if name:
                    if source is None or camp_source == source:
                        campaigns_set.add((name, camp_source))
    
    # Sort and return
    campaigns = [
        {"name": name, "source": src}
        for name, src in sorted(campaigns_set, key=lambda x: x[0])
    ]
    
    return {"campaigns": campaigns, "total": len(campaigns)}




@router.post("", response_model=ContactResponse)
async def create_contact(
    contact: ContactCreate,
    session: AsyncSession = Depends(get_session),
    company_id: int | None = Depends(get_optional_company_id),
):
    """Create a new contact"""
    
    # Check for duplicate email
    existing = await session.execute(
        select(Contact).where(
            and_(
                Contact.company_id == company_id if company_id else True,
                Contact.email == contact.email,
                Contact.deleted_at.is_(None)
            )
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Contact with this email already exists")
    
    db_contact = Contact(
        company_id=company_id or 1,
        **contact.model_dump()
    )
    session.add(db_contact)
    await session.commit()
    await session.refresh(db_contact)
    
    return ContactResponse.model_validate(db_contact)


@router.get("/{contact_id}", response_model=ContactResponse)
async def get_contact(
    contact_id: int,
    session: AsyncSession = Depends(get_session),
    company_id: int | None = Depends(get_optional_company_id),
):
    """Get a single contact"""
    
    result = await session.execute(
        select(Contact).where(
            and_(
                Contact.id == contact_id,
                Contact.company_id == company_id if company_id else True,
                Contact.deleted_at.is_(None)
            )
        )
    )
    contact = result.scalar_one_or_none()
    
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    response = ContactResponse.model_validate(contact)
    
    # Add project name
    if contact.project_id:
        proj_result = await session.execute(
            select(Project.name).where(Project.id == contact.project_id)
        )
        response.project_name = proj_result.scalar()
    
    return response


@router.patch("/{contact_id}", response_model=ContactResponse)
async def update_contact(
    contact_id: int,
    updates: ContactUpdate,
    session: AsyncSession = Depends(get_session),
    company_id: int | None = Depends(get_optional_company_id),
):
    """Update a contact"""
    
    result = await session.execute(
        select(Contact).where(
            and_(
                Contact.id == contact_id,
                Contact.company_id == company_id if company_id else True,
                Contact.deleted_at.is_(None)
            )
        )
    )
    contact = result.scalar_one_or_none()
    
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    update_data = updates.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(contact, key, value)
    
    contact.updated_at = datetime.utcnow()
    await session.commit()
    await session.refresh(contact)
    
    return ContactResponse.model_validate(contact)


@router.delete("/{contact_id}")
async def delete_contact(
    contact_id: int,
    session: AsyncSession = Depends(get_session),
    company_id: int | None = Depends(get_optional_company_id),
):
    """Soft delete a contact"""
    
    result = await session.execute(
        select(Contact).where(
            and_(
                Contact.id == contact_id,
                Contact.company_id == company_id if company_id else True,
                Contact.deleted_at.is_(None)
            )
        )
    )
    contact = result.scalar_one_or_none()
    
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    contact.deleted_at = datetime.utcnow()
    await session.commit()
    
    return {"success": True}


@router.delete("")
async def delete_multiple_contacts(
    contact_ids: List[int] = Body(...),
    session: AsyncSession = Depends(get_session),
    company_id: int | None = Depends(get_optional_company_id),
):
    """Soft delete multiple contacts"""
    
    result = await session.execute(
        select(Contact).where(
            and_(
                Contact.id.in_(contact_ids),
                Contact.company_id == company_id if company_id else True,
                Contact.deleted_at.is_(None)
            )
        )
    )
    contacts = result.scalars().all()
    
    deleted = 0
    for contact in contacts:
        contact.deleted_at = datetime.utcnow()
        deleted += 1
    
    await session.commit()
    
    return {"success": True, "deleted": deleted}


@router.post("/bulk", response_model=Dict[str, Any])
async def bulk_create_contacts(
    contacts: List[ContactCreate] = Body(...),
    session: AsyncSession = Depends(get_session),
    company_id: int | None = Depends(get_optional_company_id),
):
    """Bulk create contacts"""
    
    created = 0
    skipped = 0
    errors = []
    
    for idx, contact_data in enumerate(contacts):
        try:
            # Check for duplicate
            existing = await session.execute(
                select(Contact.id).where(
                    and_(
                        Contact.company_id == company_id if company_id else True,
                        Contact.email == contact_data.email,
                        Contact.deleted_at.is_(None)
                    )
                )
            )
            if existing.scalar_one_or_none():
                skipped += 1
                continue
            
            db_contact = Contact(
                company_id=company_id or 1,
                **contact_data.model_dump()
            )
            session.add(db_contact)
            created += 1
            
        except Exception as e:
            errors.append(f"Row {idx}: {str(e)}")
    
    await session.commit()
    
    return {
        "success": True,
        "created": created,
        "skipped": skipped,
        "errors": errors[:10]
    }


@router.post("/import/merged", response_model=Dict[str, Any])
async def import_merged_contacts(
    contacts: List[dict] = Body(...),
    session: AsyncSession = Depends(get_session),
    company_id: int | None = Depends(get_optional_company_id),
):
    """Import contacts from merged Smartlead+GetSales JSON"""
    
    imported = 0
    skipped = 0
    errors = []
    
    for contact_data in contacts:
        try:
            email = contact_data.get("email")
            if not email:
                skipped += 1
                continue
            
            # Check if exists
            existing = await session.execute(
                select(Contact).where(
                    and_(
                        Contact.company_id == company_id if company_id else True,
                        Contact.email == email,
                        Contact.deleted_at.is_(None)
                    )
                )
            )
            
            if existing.scalar_one_or_none():
                skipped += 1
                continue
            
            # Determine status based on replied field
            status = "replied" if contact_data.get("replied") else "lead"
            
            # Determine source
            sources = contact_data.get("sources", [])
            if "smartlead" in sources and "getsales" in sources:
                source = "smartlead+getsales"
            elif "smartlead" in sources:
                source = "smartlead"
            elif "getsales" in sources:
                source = "getsales"
            else:
                source = "import"
            
            # Create contact
            contact = Contact(
                company_id=company_id or 1,
                email=email,
                first_name=contact_data.get("first_name"),
                last_name=contact_data.get("last_name"),
                company_name=contact_data.get("company"),
                job_title=contact_data.get("title"),
                phone=contact_data.get("phone"),
                linkedin_url=contact_data.get("linkedin"),
                location=contact_data.get("location"),
                source=source,
                status=status
            )
            
            session.add(contact)
            imported += 1
            
        except Exception as e:
            errors.append(f"Error importing {contact_data.get('email')}: {str(e)}")
    
    await session.commit()
    
    return {
        "success": True,
        "imported": imported,
        "skipped": skipped,
        "errors": errors[:10]  # Return first 10 errors
    }


class ImportResult(BaseModel):
    """Result of CSV import operation."""
    success: bool
    total_rows: int
    created: int
    skipped: int
    errors: List[str]
    sample_created: List[str]  # First 5 emails created


def validate_email(email: str) -> bool:
    """Basic email validation."""
    if not email or not isinstance(email, str):
        return False
    email = email.strip().lower()
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


@router.post("/import/csv", response_model=ImportResult)
async def import_contacts_csv(
    file: UploadFile = File(...),
    project_id: Optional[int] = Query(None, description="Project ID to assign contacts to"),
    segment: Optional[str] = Query(None, description="Segment to assign to all imported contacts"),
    skip_duplicates: bool = Query(True, description="Skip contacts with duplicate emails"),
    session: AsyncSession = Depends(get_session),
    company_id: int | None = Depends(get_optional_company_id),
):
    """
    Import contacts from a CSV file.
    
    Expected CSV columns (case-insensitive):
    - email (required)
    - first_name / firstname / first name
    - last_name / lastname / last name
    - company / company_name
    - domain
    - job_title / title / position
    - segment (optional - can be set via query param)
    - phone
    - linkedin_url / linkedin
    - location
    - notes
    
    Args:
        file: CSV file to import
        project_id: Optional project to assign all contacts to
        segment: Optional segment to assign to all contacts
        skip_duplicates: If true, skip rows with duplicate emails (default: true)
    
    Returns:
        ImportResult with counts of created, skipped, and errors
    """
    if not file.filename or not file.filename.lower().endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")
    
    # Read file content
    try:
        content = await file.read()
        text_content = content.decode('utf-8-sig')  # Handle BOM
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")
    
    # Parse CSV
    try:
        reader = csv.DictReader(io.StringIO(text_content))
        rows = list(reader)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {str(e)}")
    
    if not rows:
        raise HTTPException(status_code=400, detail="CSV file is empty")
    
    # Map column names (case-insensitive)
    column_mapping = {
        'email': ['email', 'e-mail', 'email_address', 'emailaddress'],
        'first_name': ['first_name', 'firstname', 'first name', 'first'],
        'last_name': ['last_name', 'lastname', 'last name', 'last', 'surname'],
        'company_name': ['company', 'company_name', 'companyname', 'organization', 'org'],
        'domain': ['domain', 'website', 'company_domain'],
        'job_title': ['job_title', 'jobtitle', 'title', 'position', 'role'],
        'segment': ['segment', 'industry', 'vertical'],
        'phone': ['phone', 'phone_number', 'phonenumber', 'mobile', 'tel'],
        'linkedin_url': ['linkedin_url', 'linkedin', 'linkedin_profile', 'linkedinurl'],
        'location': ['location', 'city', 'country', 'region', 'address'],
        'notes': ['notes', 'note', 'comments', 'comment'],
    }
    
    # Detect columns
    available_columns = {col.lower().strip(): col for col in (rows[0].keys() if rows else [])}
    field_to_csv_col = {}
    
    for field, aliases in column_mapping.items():
        for alias in aliases:
            if alias.lower() in available_columns:
                field_to_csv_col[field] = available_columns[alias.lower()]
                break
    
    if 'email' not in field_to_csv_col:
        raise HTTPException(
            status_code=400, 
            detail=f"CSV must have an 'email' column. Found columns: {list(available_columns.values())}"
        )
    
    logger.info(f"CSV import: {len(rows)} rows, columns mapped: {field_to_csv_col}")
    
    # Get existing emails for duplicate check
    existing_emails = set()
    if skip_duplicates:
        existing_result = await session.execute(
            select(Contact.email).where(
                and_(
                    Contact.company_id == company_id if company_id else True,
                    Contact.deleted_at.is_(None)
                )
            )
        )
        existing_emails = {row[0].lower() for row in existing_result.all() if row[0]}
    
    # Process rows
    created = 0
    skipped = 0
    errors = []
    sample_created = []
    
    for idx, row in enumerate(rows, start=2):  # Start at 2 (1 is header)
        try:
            # Get email
            email_col = field_to_csv_col['email']
            email = row.get(email_col, '').strip().lower()
            
            if not email:
                errors.append(f"Row {idx}: Empty email")
                continue
            
            if not validate_email(email):
                errors.append(f"Row {idx}: Invalid email format '{email}'")
                continue
            
            # Check duplicate
            if skip_duplicates and email in existing_emails:
                skipped += 1
                continue
            
            # Extract fields
            contact_data = {
                'email': email,
                'source': 'csv',
                'status': 'lead',
            }
            
            for field, csv_col in field_to_csv_col.items():
                if field != 'email':
                    value = row.get(csv_col, '').strip()
                    if value:
                        contact_data[field] = value
            
            # Override segment if provided in query
            if segment:
                contact_data['segment'] = segment
            
            # Override project_id if provided
            if project_id:
                contact_data['project_id'] = project_id
            
            # Create contact
            db_contact = Contact(
                company_id=company_id or 1,
                **contact_data
            )
            session.add(db_contact)
            existing_emails.add(email)  # Track to avoid duplicates within same file
            created += 1
            
            if len(sample_created) < 5:
                sample_created.append(email)
            
        except Exception as e:
            errors.append(f"Row {idx}: {str(e)}")
            if len(errors) > 100:
                errors.append("... (more errors truncated)")
                break
    
    # Commit all changes
    await session.commit()
    
    logger.info(f"CSV import complete: {created} created, {skipped} skipped, {len(errors)} errors")
    
    return ImportResult(
        success=created > 0 or (created == 0 and skipped > 0),
        total_rows=len(rows),
        created=created,
        skipped=skipped,
        errors=errors[:20],  # Limit errors in response
        sample_created=sample_created,
    )


@router.get("/import/template")
async def get_import_template():
    """Download a CSV template for importing contacts."""
    template_content = """email,first_name,last_name,company,domain,job_title,segment,phone,linkedin_url,location,notes
john@example.com,John,Doe,Acme Corp,acme.com,CEO,B2B SaaS,+1234567890,https://linkedin.com/in/johndoe,New York,Important lead
jane@company.com,Jane,Smith,Tech Inc,techinc.com,CTO,FinTech,,,San Francisco,Follow up next week
"""
    return StreamingResponse(
        iter([template_content]),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=contacts_import_template.csv"
        }
    )


@router.post("/export/csv")
async def export_contacts_csv(
    contact_ids: Optional[List[int]] = Body(None),
    session: AsyncSession = Depends(get_session),
    company_id: int | None = Depends(get_optional_company_id),
):
    """Export contacts as CSV"""
    
    query = select(Contact).where(
        and_(
            Contact.company_id == company_id if company_id else True,
            Contact.deleted_at.is_(None)
        )
    )
    
    if contact_ids:
        query = query.where(Contact.id.in_(contact_ids))
    
    result = await session.execute(query)
    contacts = result.scalars().all()
    
    if not contacts:
        raise HTTPException(status_code=404, detail="No contacts to export")
    
    # Create CSV
    output = io.StringIO()
    columns = [
        "email", "first_name", "last_name", "company_name", "domain",
        "job_title", "segment", "source", "status", "phone",
        "linkedin_url", "location", "notes"
    ]
    
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    
    for contact in contacts:
        row = {col: getattr(contact, col, "") or "" for col in columns}
        writer.writerow(row)
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=contacts.csv"
        }
    )


# ============= Projects Endpoints =============

@router.get("/projects/list", response_model=List[ProjectResponse])
async def list_projects(
    session: AsyncSession = Depends(get_session),
    company_id: int | None = Depends(get_optional_company_id),
):
    """List all projects with contact counts"""
    
    result = await session.execute(
        select(Project)
        .where(and_(Project.company_id == company.id, Project.deleted_at.is_(None)))
        .order_by(Project.name)
    )
    projects = result.scalars().all()
    
    # Get contact counts
    project_responses = []
    for project in projects:
        count_result = await session.execute(
            select(func.count()).where(
                and_(Contact.project_id == project.id, Contact.deleted_at.is_(None))
            )
        )
        contact_count = count_result.scalar() or 0
        
        response = ProjectResponse(
            id=project.id,
            name=project.name,
            description=project.description,
            target_industries=project.target_industries,
            target_segments=project.target_segments,
            contact_count=contact_count,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )
        project_responses.append(response)
    
    return project_responses


@router.post("/projects", response_model=ProjectResponse)
async def create_project(
    project: ProjectCreate,
    session: AsyncSession = Depends(get_session),
    company_id: int | None = Depends(get_optional_company_id),
):
    """Create a new project"""
    
    db_project = Project(
        company_id=company_id or 1,
        **project.model_dump()
    )
    session.add(db_project)
    await session.commit()
    await session.refresh(db_project)
    
    return ProjectResponse(
        id=db_project.id,
        name=db_project.name,
        description=db_project.description,
        target_industries=db_project.target_industries,
        target_segments=db_project.target_segments,
        contact_count=0,
        created_at=db_project.created_at,
        updated_at=db_project.updated_at,
    )


@router.patch("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    updates: ProjectUpdate,
    session: AsyncSession = Depends(get_session),
    company_id: int | None = Depends(get_optional_company_id),
):
    """Update a project"""
    
    result = await session.execute(
        select(Project).where(
            and_(
                Project.id == project_id,
                Project.company_id == company.id,
                Project.deleted_at.is_(None)
            )
        )
    )
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    update_data = updates.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(project, key, value)
    
    project.updated_at = datetime.utcnow()
    await session.commit()
    await session.refresh(project)
    
    # Get contact count
    count_result = await session.execute(
        select(func.count()).where(
            and_(Contact.project_id == project.id, Contact.deleted_at.is_(None))
        )
    )
    contact_count = count_result.scalar() or 0
    
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        target_industries=project.target_industries,
        target_segments=project.target_segments,
        contact_count=contact_count,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: int,
    session: AsyncSession = Depends(get_session),
    company_id: int | None = Depends(get_optional_company_id),
):
    """Soft delete a project (contacts keep project_id but project is hidden)"""
    
    result = await session.execute(
        select(Project).where(
            and_(
                Project.id == project_id,
                Project.company_id == company.id,
                Project.deleted_at.is_(None)
            )
        )
    )
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project.deleted_at = datetime.utcnow()
    await session.commit()
    
    return {"success": True}


# ============= AI SDR Endpoints =============

class AISDRProjectResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    target_industries: Optional[str] = None
    target_segments: Optional[str] = None
    contact_count: int = 0
    tam_analysis: Optional[str] = None
    gtm_plan: Optional[str] = None
    pitch_templates: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


async def _get_project_with_contacts(
    project_id: int,
    session: AsyncSession,
    company: Company,
) -> tuple:
    """Helper to get project and its contacts."""
    result = await session.execute(
        select(Project).where(
            and_(
                Project.id == project_id,
                Project.company_id == company.id,
                Project.deleted_at.is_(None)
            )
        )
    )
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get project contacts
    contacts_result = await session.execute(
        select(Contact).where(
            and_(Contact.project_id == project_id, Contact.deleted_at.is_(None))
        )
    )
    contacts = contacts_result.scalars().all()
    
    # Convert to dicts for AI service
    contact_dicts = [
        {
            "email": c.email,
            "first_name": c.first_name,
            "last_name": c.last_name,
            "company_name": c.company_name,
            "domain": c.domain,
            "job_title": c.job_title,
            "segment": c.segment,
            "status": c.status,
            "location": c.location,
        }
        for c in contacts
    ]
    
    return project, contact_dicts


@router.get("/projects/{project_id}/analyze", response_model=ProjectContactAnalysis)
async def analyze_project_contacts(
    project_id: int,
    session: AsyncSession = Depends(get_session),
    company_id: int | None = Depends(get_optional_company_id),
):
    """
    Analyze contacts for a project using Python/SQL aggregations.
    
    NO AI calls - pure data analysis using code.
    Returns breakdowns by segment, status, company, job title, location, domain.
    """
    # Get project
    result = await session.execute(
        select(Project).where(
            and_(
                Project.id == project_id,
                Project.company_id == company.id,
                Project.deleted_at.is_(None)
            )
        )
    )
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get project contacts
    contacts_result = await session.execute(
        select(Contact).where(
            and_(Contact.project_id == project_id, Contact.deleted_at.is_(None))
        )
    )
    contacts = contacts_result.scalars().all()
    
    # Analyze with Python - no AI needed!
    total = len(contacts)
    
    # By segment
    by_segment: Dict[str, int] = {}
    for c in contacts:
        seg = c.segment or "Unassigned"
        by_segment[seg] = by_segment.get(seg, 0) + 1
    
    # By status
    by_status: Dict[str, int] = {}
    for c in contacts:
        status = c.status or "Unknown"
        by_status[status] = by_status.get(status, 0) + 1
    
    # By source
    by_source: Dict[str, int] = {}
    for c in contacts:
        source = c.source or "Unknown"
        by_source[source] = by_source.get(source, 0) + 1
    
    # Company analysis
    companies: Dict[str, Dict[str, Any]] = {}
    for c in contacts:
        company_name = c.company_name or "Unknown"
        if company_name not in companies:
            companies[company_name] = {"name": company_name, "count": 0, "domain": c.domain}
        companies[company_name]["count"] += 1
    
    top_companies = sorted(companies.values(), key=lambda x: x["count"], reverse=True)[:10]
    
    # Job title analysis
    titles: Dict[str, int] = {}
    for c in contacts:
        title = c.job_title or "Unknown"
        titles[title] = titles.get(title, 0) + 1
    
    top_titles = [{"title": k, "count": v} for k, v in sorted(titles.items(), key=lambda x: x[1], reverse=True)[:10]]
    
    # Location analysis
    locations: Dict[str, int] = {}
    for c in contacts:
        loc = c.location or "Unknown"
        locations[loc] = locations.get(loc, 0) + 1
    
    top_locations = [{"location": k, "count": v} for k, v in sorted(locations.items(), key=lambda x: x[1], reverse=True)[:10]]
    
    # Domain analysis
    domains: Dict[str, int] = {}
    for c in contacts:
        domain = c.domain or "Unknown"
        domains[domain] = domains.get(domain, 0) + 1
    
    top_domains = [{"domain": k, "count": v} for k, v in sorted(domains.items(), key=lambda x: x[1], reverse=True)[:10]]
    
    return ProjectContactAnalysis(
        project_id=project.id,
        project_name=project.name,
        total_contacts=total,
        by_segment=by_segment,
        by_status=by_status,
        by_source=by_source,
        unique_companies=len(companies),
        top_companies=top_companies,
        unique_job_titles=len(titles),
        top_job_titles=top_titles,
        unique_locations=len(locations),
        top_locations=top_locations,
        unique_domains=len(domains),
        top_domains=top_domains,
    )


@router.get("/projects/{project_id}/ai-sdr", response_model=AISDRProjectResponse)
async def get_project_ai_sdr(
    project_id: int,
    session: AsyncSession = Depends(get_session),
    company_id: int | None = Depends(get_optional_company_id),
):
    """Get project with all AI SDR generated content."""
    project, contacts = await _get_project_with_contacts(project_id, session, company)
    
    return AISDRProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        target_industries=project.target_industries,
        target_segments=project.target_segments,
        contact_count=len(contacts),
        tam_analysis=project.tam_analysis,
        gtm_plan=project.gtm_plan,
        pitch_templates=project.pitch_templates,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.post("/projects/{project_id}/generate-tam")
async def generate_tam_analysis(
    project_id: int,
    session: AsyncSession = Depends(get_session),
    company_id: int | None = Depends(get_optional_company_id),
):
    """Generate TAM analysis for a project using AI."""
    project, contacts = await _get_project_with_contacts(project_id, session, company)
    
    if not contacts:
        raise HTTPException(
            status_code=400, 
            detail="Project has no contacts. Add contacts before generating TAM analysis."
        )
    
    try:
        tam_analysis = await ai_sdr_service.generate_tam_analysis(
            project_name=project.name,
            target_industries=project.target_industries,
            target_segments=project.target_segments,
            contacts=contacts,
        )
        
        # Save to project
        project.tam_analysis = tam_analysis
        project.updated_at = datetime.utcnow()
        await session.commit()
        
        return {
            "success": True,
            "tam_analysis": tam_analysis,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TAM generation failed: {str(e)}")


@router.post("/projects/{project_id}/generate-gtm")
async def generate_gtm_plan(
    project_id: int,
    session: AsyncSession = Depends(get_session),
    company_id: int | None = Depends(get_optional_company_id),
):
    """Generate GTM plan for a project using AI."""
    project, contacts = await _get_project_with_contacts(project_id, session, company)
    
    if not contacts:
        raise HTTPException(
            status_code=400, 
            detail="Project has no contacts. Add contacts before generating GTM plan."
        )
    
    try:
        gtm_plan = await ai_sdr_service.generate_gtm_plan(
            project_name=project.name,
            target_industries=project.target_industries,
            target_segments=project.target_segments,
            contacts=contacts,
            tam_analysis=project.tam_analysis,  # Use existing TAM if available
        )
        
        # Save to project
        project.gtm_plan = gtm_plan
        project.updated_at = datetime.utcnow()
        await session.commit()
        
        return {
            "success": True,
            "gtm_plan": gtm_plan,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GTM generation failed: {str(e)}")


@router.post("/projects/{project_id}/generate-pitches")
async def generate_pitch_templates(
    project_id: int,
    session: AsyncSession = Depends(get_session),
    company_id: int | None = Depends(get_optional_company_id),
):
    """Generate pitch email templates for a project using AI."""
    project, contacts = await _get_project_with_contacts(project_id, session, company)
    
    if not contacts:
        raise HTTPException(
            status_code=400, 
            detail="Project has no contacts. Add contacts before generating pitch templates."
        )
    
    try:
        pitch_templates = await ai_sdr_service.generate_pitch_templates(
            project_name=project.name,
            target_industries=project.target_industries,
            target_segments=project.target_segments,
            contacts=contacts,
            tam_analysis=project.tam_analysis,
            gtm_plan=project.gtm_plan,
        )
        
        # Save to project
        project.pitch_templates = pitch_templates
        project.updated_at = datetime.utcnow()
        await session.commit()
        
        return {
            "success": True,
            "pitch_templates": pitch_templates,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pitch generation failed: {str(e)}")


@router.post("/projects/{project_id}/generate-all")
async def generate_all_ai_sdr(
    project_id: int,
    session: AsyncSession = Depends(get_session),
    company_id: int | None = Depends(get_optional_company_id),
):
    """Generate all AI SDR content (TAM, GTM, Pitches) for a project."""
    project, contacts = await _get_project_with_contacts(project_id, session, company)
    
    if not contacts:
        raise HTTPException(
            status_code=400, 
            detail="Project has no contacts. Add contacts before generating AI SDR content."
        )
    
    try:
        # Generate TAM first
        tam_analysis = await ai_sdr_service.generate_tam_analysis(
            project_name=project.name,
            target_industries=project.target_industries,
            target_segments=project.target_segments,
            contacts=contacts,
        )
        project.tam_analysis = tam_analysis
        
        # Generate GTM using TAM
        gtm_plan = await ai_sdr_service.generate_gtm_plan(
            project_name=project.name,
            target_industries=project.target_industries,
            target_segments=project.target_segments,
            contacts=contacts,
            tam_analysis=tam_analysis,
        )
        project.gtm_plan = gtm_plan
        
        # Generate pitches using TAM and GTM
        pitch_templates = await ai_sdr_service.generate_pitch_templates(
            project_name=project.name,
            target_industries=project.target_industries,
            target_segments=project.target_segments,
            contacts=contacts,
            tam_analysis=tam_analysis,
            gtm_plan=gtm_plan,
        )
        project.pitch_templates = pitch_templates
        
        project.updated_at = datetime.utcnow()
        await session.commit()
        
        return {
            "success": True,
            "tam_analysis": tam_analysis,
            "gtm_plan": gtm_plan,
            "pitch_templates": pitch_templates,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI SDR generation failed: {str(e)}")


# ============= Contact Activities =============

class ActivityResponse(BaseModel):
    id: int
    contact_id: int
    activity_type: str
    channel: str
    direction: Optional[str]
    source: str
    source_id: Optional[str]
    subject: Optional[str]
    body: Optional[str]
    snippet: Optional[str]
    extra_data: Optional[Dict[str, Any]]
    activity_at: datetime
    created_at: datetime
    
    class Config:
        from_attributes = True


@router.get("/{contact_id}/activities", response_model=List[ActivityResponse])
async def get_contact_activities(
    contact_id: int,
    session: AsyncSession = Depends(get_session),
    channel: Optional[str] = Query(None, description="Filter by channel: email, linkedin"),
    activity_type: Optional[str] = Query(None, description="Filter by activity type"),
    limit: int = Query(100, ge=1, le=500),
):
    """
    Get all activities/communication history for a contact.
    
    Returns activities sorted by activity_at descending (most recent first).
    """
    query = select(ContactActivity).where(
        ContactActivity.contact_id == contact_id
    )
    
    if channel:
        query = query.where(ContactActivity.channel == channel)
    if activity_type:
        query = query.where(ContactActivity.activity_type == activity_type)
    
    query = query.order_by(ContactActivity.activity_at.desc()).limit(limit)
    
    result = await session.execute(query)
    activities = result.scalars().all()
    
    return activities


@router.get("/{contact_id}/history")
async def get_contact_history(
    contact_id: int,
    session: AsyncSession = Depends(get_session),
):
    """
    Get full communication history for a contact, organized by channel.
    
    Returns:
    - email_history: List of email activities from Smartlead
    - linkedin_history: List of LinkedIn activities from GetSales
    - summary: counts and last activity dates
    """
    # Get all activities
    result = await session.execute(
        select(ContactActivity)
        .where(ContactActivity.contact_id == contact_id)
        .order_by(ContactActivity.activity_at.desc())
    )
    activities = result.scalars().all()
    
    email_activities = [a for a in activities if a.channel == "email"]
    linkedin_activities = [a for a in activities if a.channel == "linkedin"]
    
    # Get contact info
    contact_result = await session.execute(
        select(Contact).where(Contact.id == contact_id)
    )
    contact = contact_result.scalar_one_or_none()
    
    return {
        "contact_id": contact_id,
        "email_history": [
            {
                "id": a.id,
                "type": a.activity_type,
                "direction": a.direction,
                "subject": a.subject,
                "body": a.body,
                "snippet": a.snippet,
                "source": a.source,
                "campaign": a.extra_data.get("campaign_name") if a.extra_data else None,
                "timestamp": a.activity_at.isoformat(),
            }
            for a in email_activities
        ],
        "linkedin_history": [
            {
                "id": a.id,
                "type": a.activity_type,
                "direction": a.direction,
                "body": a.body,
                "snippet": a.snippet,
                "source": a.source,
                "automation": a.extra_data.get("automation_name") if a.extra_data else None,
                "timestamp": a.activity_at.isoformat(),
            }
            for a in linkedin_activities
        ],
        "summary": {
            "total_activities": len(activities),
            "email_count": len(email_activities),
            "linkedin_count": len(linkedin_activities),
            "has_email_history": len(email_activities) > 0,
            "has_linkedin_history": len(linkedin_activities) > 0,
            "last_email_activity": email_activities[0].activity_at.isoformat() if email_activities else None,
            "last_linkedin_activity": linkedin_activities[0].activity_at.isoformat() if linkedin_activities else None,
            "smartlead_id": contact.smartlead_id if contact else None,
            "getsales_id": contact.getsales_id if contact else None,
        }
    }
