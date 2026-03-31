"""
iGaming contacts API router.

Endpoints for contacts, companies, employees, imports, and AI columns.
"""
import logging
import math
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from pydantic import BaseModel
from sqlalchemy import select, func, and_, or_, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.db import get_session
from app.models.igaming import (
    IGamingContact, IGamingCompany, IGamingEmployee, IGamingImport,
    IGamingAIColumn, BusinessType,
)
from app.schemas.igaming import (
    IGamingContactResponse, IGamingContactListResponse, IGamingContactUpdate,
    IGamingCompanyResponse, IGamingCompanyListResponse, IGamingCompanyUpdate,
    IGamingEmployeeResponse, IGamingEmployeeListResponse,
    IGamingImportUploadResponse, IGamingImportStartRequest, IGamingImportResponse,
    IGamingAIColumnCreate, IGamingAIColumnResponse,
    IGamingStatsResponse,
)
from app.services.igaming_import_service import upload_file, run_import, run_autofill, proper_case
from app.services.igaming_llm_service import run_ai_column, get_progress as get_ai_progress
from app.services.igaming_employee_service import (
    search_employees_apollo, search_employees_clay,
    get_search_progress,
)
from app.services.igaming_website_finder import (
    find_websites, get_progress as get_website_progress,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/igaming", tags=["iGaming"])


# ── Stats ──────────────────────────────────────────────────────────────

@router.get("/stats", response_model=IGamingStatsResponse)
async def get_stats(session: AsyncSession = Depends(get_session)):
    """Dashboard stats for iGaming module."""
    total_contacts = (await session.execute(
        select(func.count(IGamingContact.id)).where(IGamingContact.is_active == True)
    )).scalar() or 0

    total_companies = (await session.execute(
        select(func.count(IGamingCompany.id))
    )).scalar() or 0

    total_employees = (await session.execute(
        select(func.count(IGamingEmployee.id))
    )).scalar() or 0

    contacts_with_email = (await session.execute(
        select(func.count(IGamingContact.id)).where(
            and_(IGamingContact.is_active == True, IGamingContact.email.isnot(None))
        )
    )).scalar() or 0

    contacts_with_linkedin = (await session.execute(
        select(func.count(IGamingContact.id)).where(
            and_(IGamingContact.is_active == True, IGamingContact.linkedin_url.isnot(None))
        )
    )).scalar() or 0

    companies_with_website = (await session.execute(
        select(func.count(IGamingCompany.id)).where(IGamingCompany.website.isnot(None))
    )).scalar() or 0

    # Top conferences
    conf_result = await session.execute(
        select(
            IGamingContact.source_conference,
            func.count(IGamingContact.id).label("count")
        ).where(
            and_(
                IGamingContact.is_active == True,
                IGamingContact.source_conference.isnot(None),
            )
        ).group_by(IGamingContact.source_conference)
        .order_by(desc("count"))
        .limit(10)
    )
    top_conferences = [{"name": r[0], "count": r[1]} for r in conf_result.all()]

    # Top business types
    type_result = await session.execute(
        select(
            IGamingContact.business_type,
            func.count(IGamingContact.id).label("count")
        ).where(
            and_(
                IGamingContact.is_active == True,
                IGamingContact.business_type.isnot(None),
            )
        ).group_by(IGamingContact.business_type)
        .order_by(desc("count"))
        .limit(10)
    )
    top_types = [{"name": r[0].value if r[0] else "other", "count": r[1]} for r in type_result.all()]

    # Recent imports
    imports_result = await session.execute(
        select(IGamingImport).order_by(desc(IGamingImport.created_at)).limit(5)
    )
    recent_imports = imports_result.scalars().all()

    return IGamingStatsResponse(
        total_contacts=total_contacts,
        total_companies=total_companies,
        total_employees=total_employees,
        contacts_with_email=contacts_with_email,
        contacts_with_linkedin=contacts_with_linkedin,
        companies_with_website=companies_with_website,
        top_conferences=top_conferences,
        top_business_types=top_types,
        recent_imports=[IGamingImportResponse.model_validate(i) for i in recent_imports],
    )


# ── Contacts CRUD ─────────────────────────────────────────────────────

@router.get("/contacts", response_model=IGamingContactListResponse)
async def list_contacts(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    search: Optional[str] = Query(None),
    business_type: Optional[str] = Query(None),
    source_conference: Optional[str] = Query(None),
    has_email: Optional[bool] = Query(None),
    has_linkedin: Optional[bool] = Query(None),
    company_id: Optional[int] = Query(None),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    tags: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """List contacts with filtering, sorting, pagination."""
    query = select(IGamingContact).where(IGamingContact.is_active == True)
    count_query = select(func.count(IGamingContact.id)).where(IGamingContact.is_active == True)

    # Filters
    if search:
        like = f"%{search}%"
        search_filter = or_(
            IGamingContact.first_name.ilike(like),
            IGamingContact.last_name.ilike(like),
            IGamingContact.email.ilike(like),
            IGamingContact.organization_name.ilike(like),
            IGamingContact.job_title.ilike(like),
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    if business_type:
        types = [t.strip() for t in business_type.split(",")]
        query = query.where(IGamingContact.business_type.in_(types))
        count_query = count_query.where(IGamingContact.business_type.in_(types))

    if source_conference:
        confs = [c.strip() for c in source_conference.split(",")]
        query = query.where(IGamingContact.source_conference.in_(confs))
        count_query = count_query.where(IGamingContact.source_conference.in_(confs))

    if has_email is not None:
        cond = IGamingContact.email.isnot(None) if has_email else IGamingContact.email.is_(None)
        query = query.where(cond)
        count_query = count_query.where(cond)

    if has_linkedin is not None:
        cond = IGamingContact.linkedin_url.isnot(None) if has_linkedin else IGamingContact.linkedin_url.is_(None)
        query = query.where(cond)
        count_query = count_query.where(cond)

    if company_id:
        query = query.where(IGamingContact.company_id == company_id)
        count_query = count_query.where(IGamingContact.company_id == company_id)

    # Total count
    total = (await session.execute(count_query)).scalar() or 0
    total_pages = math.ceil(total / page_size) if total > 0 else 1

    # Sorting
    sort_col = getattr(IGamingContact, sort_by, IGamingContact.created_at)
    order = desc(sort_col) if sort_order == "desc" else asc(sort_col)
    query = query.order_by(order)

    # Pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    # Join company for response
    query = query.options(joinedload(IGamingContact.company))

    result = await session.execute(query)
    contacts = result.unique().scalars().all()

    # Build response with company data
    contact_responses = []
    for c in contacts:
        resp = IGamingContactResponse.model_validate(c)
        if c.company:
            resp.company_name = c.company.name
            resp.company_website = c.company.website
        contact_responses.append(resp)

    return IGamingContactListResponse(
        contacts=contact_responses,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/contacts/{contact_id}", response_model=IGamingContactResponse)
async def get_contact(contact_id: int, session: AsyncSession = Depends(get_session)):
    """Get single contact."""
    result = await session.execute(
        select(IGamingContact)
        .options(joinedload(IGamingContact.company))
        .where(and_(IGamingContact.id == contact_id, IGamingContact.is_active == True))
    )
    contact = result.unique().scalar_one_or_none()
    if not contact:
        raise HTTPException(404, "Contact not found")
    resp = IGamingContactResponse.model_validate(contact)
    if contact.company:
        resp.company_name = contact.company.name
        resp.company_website = contact.company.website
    return resp


@router.patch("/contacts/{contact_id}", response_model=IGamingContactResponse)
async def update_contact(
    contact_id: int,
    data: IGamingContactUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update contact (inline edit from AG Grid)."""
    result = await session.execute(
        select(IGamingContact)
        .options(joinedload(IGamingContact.company))
        .where(and_(IGamingContact.id == contact_id, IGamingContact.is_active == True))
    )
    contact = result.unique().scalar_one_or_none()
    if not contact:
        raise HTTPException(404, "Contact not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(contact, field, value)

    await session.flush()
    resp = IGamingContactResponse.model_validate(contact)
    if contact.company:
        resp.company_name = contact.company.name
        resp.company_website = contact.company.website
    return resp


@router.delete("/contacts/{contact_id}", status_code=204)
async def delete_contact(contact_id: int, session: AsyncSession = Depends(get_session)):
    """Soft delete contact."""
    result = await session.execute(
        select(IGamingContact).where(
            and_(IGamingContact.id == contact_id, IGamingContact.is_active == True)
        )
    )
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(404, "Contact not found")
    contact.soft_delete()
    await session.flush()


@router.post("/contacts/batch-delete", status_code=200)
async def batch_delete_contacts(
    contact_ids: list[int],
    session: AsyncSession = Depends(get_session),
):
    """Soft delete multiple contacts."""
    result = await session.execute(
        select(IGamingContact).where(
            and_(IGamingContact.id.in_(contact_ids), IGamingContact.is_active == True)
        )
    )
    contacts = result.scalars().all()
    for c in contacts:
        c.soft_delete()
    await session.flush()
    return {"deleted": len(contacts)}


@router.post("/contacts/batch-tag", status_code=200)
async def batch_tag_contacts(
    contact_ids: list[int],
    tag: str = Query(...),
    session: AsyncSession = Depends(get_session),
):
    """Add tag to multiple contacts."""
    result = await session.execute(
        select(IGamingContact).where(
            and_(IGamingContact.id.in_(contact_ids), IGamingContact.is_active == True)
        )
    )
    contacts = result.scalars().all()
    for c in contacts:
        tags = list(c.tags or [])
        if tag not in tags:
            tags.append(tag)
            c.tags = tags
    await session.flush()
    return {"tagged": len(contacts)}


@router.post("/contacts/fix-names")
async def fix_contact_names(session: AsyncSession = Depends(get_session)):
    """Apply PROPER case to all first_name and last_name in igaming_contacts."""
    result = await session.execute(
        select(IGamingContact).where(
            and_(IGamingContact.is_active == True,
                 or_(IGamingContact.first_name.isnot(None), IGamingContact.last_name.isnot(None)))
        )
    )
    contacts = result.scalars().all()

    updated = 0
    for c in contacts:
        changed = False
        if c.first_name:
            fixed = proper_case(c.first_name)
            if fixed != c.first_name:
                c.first_name = fixed
                changed = True
        if c.last_name:
            fixed = proper_case(c.last_name)
            if fixed != c.last_name:
                c.last_name = fixed
                changed = True
        if changed:
            updated += 1

    await session.flush()
    return {"updated": updated, "total_checked": len(contacts)}


# ── Companies CRUD ─────────────────────────────────────────────────────

@router.get("/companies", response_model=IGamingCompanyListResponse)
async def list_companies(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    search: Optional[str] = Query(None),
    business_type: Optional[str] = Query(None),
    has_website: Optional[bool] = Query(None),
    sort_by: str = Query("contacts_count"),
    sort_order: str = Query("desc"),
    session: AsyncSession = Depends(get_session),
):
    """List companies with filtering."""
    query = select(IGamingCompany)
    count_query = select(func.count(IGamingCompany.id))

    if search:
        like = f"%{search}%"
        sf = or_(
            IGamingCompany.name.ilike(like),
            IGamingCompany.website.ilike(like),
            IGamingCompany.description.ilike(like),
        )
        query = query.where(sf)
        count_query = count_query.where(sf)

    if business_type:
        types = [t.strip() for t in business_type.split(",")]
        query = query.where(IGamingCompany.business_type.in_(types))
        count_query = count_query.where(IGamingCompany.business_type.in_(types))

    if has_website is True:
        query = query.where(IGamingCompany.website.isnot(None))
        count_query = count_query.where(IGamingCompany.website.isnot(None))
    elif has_website is False:
        query = query.where(IGamingCompany.website.is_(None))
        count_query = count_query.where(IGamingCompany.website.is_(None))

    total = (await session.execute(count_query)).scalar() or 0
    total_pages = math.ceil(total / page_size) if total > 0 else 1

    sort_col = getattr(IGamingCompany, sort_by, IGamingCompany.contacts_count)
    order = desc(sort_col) if sort_order == "desc" else asc(sort_col)
    query = query.order_by(order)

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await session.execute(query)
    companies = result.scalars().all()

    return IGamingCompanyListResponse(
        companies=[IGamingCompanyResponse.model_validate(c) for c in companies],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/companies/{company_id}", response_model=IGamingCompanyResponse)
async def get_company(company_id: int, session: AsyncSession = Depends(get_session)):
    """Get single company."""
    result = await session.execute(
        select(IGamingCompany).where(IGamingCompany.id == company_id)
    )
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(404, "Company not found")
    return IGamingCompanyResponse.model_validate(company)


@router.patch("/companies/{company_id}", response_model=IGamingCompanyResponse)
async def update_company(
    company_id: int,
    data: IGamingCompanyUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update company."""
    result = await session.execute(
        select(IGamingCompany).where(IGamingCompany.id == company_id)
    )
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(404, "Company not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(company, field, value)
    await session.flush()
    return IGamingCompanyResponse.model_validate(company)


@router.post("/companies/merge", status_code=200)
async def merge_companies(
    source_id: int = Query(..., description="Company to merge FROM (will be deleted)"),
    target_id: int = Query(..., description="Company to merge INTO"),
    session: AsyncSession = Depends(get_session),
):
    """Merge two companies: move all contacts from source to target, delete source."""
    source = (await session.execute(
        select(IGamingCompany).where(IGamingCompany.id == source_id)
    )).scalar_one_or_none()
    target = (await session.execute(
        select(IGamingCompany).where(IGamingCompany.id == target_id)
    )).scalar_one_or_none()

    if not source or not target:
        raise HTTPException(404, "Company not found")

    # Move contacts
    contacts = (await session.execute(
        select(IGamingContact).where(IGamingContact.company_id == source_id)
    )).scalars().all()

    for c in contacts:
        c.company_id = target_id

    # Move employees
    employees = (await session.execute(
        select(IGamingEmployee).where(IGamingEmployee.company_id == source_id)
    )).scalars().all()
    for e in employees:
        e.company_id = target_id

    # Merge aliases
    aliases = list(target.name_aliases or [])
    if source.name not in aliases:
        aliases.append(source.name)
    for a in (source.name_aliases or []):
        if a not in aliases:
            aliases.append(a)
    target.name_aliases = aliases

    # Fill missing data on target
    if not target.website and source.website:
        target.website = source.website
    if not target.business_type and source.business_type:
        target.business_type = source.business_type
    if not target.description and source.description:
        target.description = source.description

    # Update count
    target.contacts_count = (target.contacts_count or 0) + (source.contacts_count or 0)
    target.employees_count = (target.employees_count or 0) + (source.employees_count or 0)

    # Delete source
    await session.delete(source)
    await session.flush()

    return {"merged": True, "contacts_moved": len(contacts), "employees_moved": len(employees)}


class FindWebsitesRequest(BaseModel):
    company_ids: Optional[list[int]] = None
    limit: int = 100


@router.post("/companies/find-websites")
async def find_company_websites(
    data: FindWebsitesRequest = FindWebsitesRequest(),
    session: AsyncSession = Depends(get_session),
):
    """Find websites for companies without domains via Yandex Search + Gemini AI."""
    import uuid
    task_id = str(uuid.uuid4())[:8]
    try:
        result = await find_websites(
            session=session,
            company_ids=data.company_ids,
            limit=data.limit,
            task_id=task_id,
        )
        return {**result, "task_id": task_id}
    except RuntimeError as e:
        raise HTTPException(503, str(e))


@router.get("/companies/find-websites/progress/{task_id}")
async def get_find_websites_progress(task_id: str):
    """Get progress of website finder task."""
    return get_website_progress(task_id)


# ── Employees ──────────────────────────────────────────────────────────

@router.get("/employees", response_model=IGamingEmployeeListResponse)
async def list_employees(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    search: Optional[str] = Query(None),
    company_id: Optional[int] = Query(None),
    source: Optional[str] = Query(None),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    session: AsyncSession = Depends(get_session),
):
    """List employees with filtering."""
    query = select(IGamingEmployee).options(joinedload(IGamingEmployee.company))
    count_query = select(func.count(IGamingEmployee.id))

    if search:
        like = f"%{search}%"
        sf = or_(
            IGamingEmployee.full_name.ilike(like),
            IGamingEmployee.email.ilike(like),
            IGamingEmployee.job_title.ilike(like),
        )
        query = query.where(sf)
        count_query = count_query.where(sf)

    if company_id:
        query = query.where(IGamingEmployee.company_id == company_id)
        count_query = count_query.where(IGamingEmployee.company_id == company_id)

    if source:
        query = query.where(IGamingEmployee.source == source)
        count_query = count_query.where(IGamingEmployee.source == source)

    total = (await session.execute(count_query)).scalar() or 0
    total_pages = math.ceil(total / page_size) if total > 0 else 1

    sort_col = getattr(IGamingEmployee, sort_by, IGamingEmployee.created_at)
    order = desc(sort_col) if sort_order == "desc" else asc(sort_col)
    query = query.order_by(order)

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await session.execute(query)
    employees = result.unique().scalars().all()

    emp_responses = []
    for e in employees:
        resp = IGamingEmployeeResponse.model_validate(e)
        if e.company:
            resp.company_name = e.company.name
            resp.company_website = e.company.website
        emp_responses.append(resp)

    return IGamingEmployeeListResponse(
        employees=emp_responses,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


# ── Import ─────────────────────────────────────────────────────────────

@router.post("/import/upload", response_model=IGamingImportUploadResponse)
async def upload_csv(file: UploadFile = File(...)):
    """Upload CSV file, get preview and column list."""
    if not file.filename:
        raise HTTPException(400, "No filename")

    content = await file.read()
    if len(content) > 100 * 1024 * 1024:  # 100MB limit
        raise HTTPException(400, "File too large (max 100MB)")

    result = await upload_file(content, file.filename)
    return IGamingImportUploadResponse(**result)


@router.post("/import/start", response_model=IGamingImportResponse)
async def start_import(
    data: IGamingImportStartRequest,
    session: AsyncSession = Depends(get_session),
):
    """Start import with column mapping."""
    try:
        import_log = await run_import(
            session=session,
            file_id=data.file_id,
            column_mapping=data.column_mapping,
            source_conference=data.source_conference,
            update_existing=data.update_existing,
        )
        return IGamingImportResponse.model_validate(import_log)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/imports", response_model=list[IGamingImportResponse])
async def list_imports(session: AsyncSession = Depends(get_session)):
    """List all imports."""
    result = await session.execute(
        select(IGamingImport).order_by(desc(IGamingImport.created_at)).limit(50)
    )
    return [IGamingImportResponse.model_validate(i) for i in result.scalars().all()]


# ── Autofill ───────────────────────────────────────────────────────────

@router.post("/autofill/run")
async def run_autofill_endpoint(session: AsyncSession = Depends(get_session)):
    """Run auto-fill: populate missing website/type from other contacts in same company."""
    stats = await run_autofill(session)
    return stats


# ── Filter options (for frontend dropdowns) ────────────────────────────

@router.get("/filters/conferences")
async def get_conferences(session: AsyncSession = Depends(get_session)):
    """Get list of unique conferences for filter dropdown."""
    result = await session.execute(
        select(
            IGamingContact.source_conference,
            func.count(IGamingContact.id).label("count")
        ).where(
            IGamingContact.source_conference.isnot(None)
        ).group_by(IGamingContact.source_conference)
        .order_by(desc("count"))
    )
    return [{"value": r[0], "count": r[1]} for r in result.all()]


@router.get("/filters/business-types")
async def get_business_types(session: AsyncSession = Depends(get_session)):
    """Get list of business types for filter dropdown."""
    result = await session.execute(
        select(
            IGamingContact.business_type,
            func.count(IGamingContact.id).label("count")
        ).where(
            IGamingContact.business_type.isnot(None)
        ).group_by(IGamingContact.business_type)
        .order_by(desc("count"))
    )
    return [{"value": r[0].value if r[0] else "other", "count": r[1]} for r in result.all()]


@router.get("/filters/sectors")
async def get_sectors(session: AsyncSession = Depends(get_session)):
    """Get list of unique sectors."""
    result = await session.execute(
        select(
            IGamingContact.sector,
            func.count(IGamingContact.id).label("count")
        ).where(
            IGamingContact.sector.isnot(None)
        ).group_by(IGamingContact.sector)
        .order_by(desc("count"))
        .limit(50)
    )
    return [{"value": r[0], "count": r[1]} for r in result.all()]


# ── AI Columns ─────────────────────────────────────────────────────────

class AIColumnRunRequest(BaseModel):
    filter_params: Optional[dict] = None


@router.post("/ai-columns", response_model=IGamingAIColumnResponse, status_code=201)
async def create_ai_column(
    data: IGamingAIColumnCreate,
    session: AsyncSession = Depends(get_session),
):
    """Create a new AI enrichment column definition."""
    col = IGamingAIColumn(
        name=data.name,
        target=data.target,
        prompt_template=data.prompt_template,
        model=data.model,
    )
    session.add(col)
    await session.flush()
    return IGamingAIColumnResponse.model_validate(col)


@router.get("/ai-columns", response_model=list[IGamingAIColumnResponse])
async def list_ai_columns(session: AsyncSession = Depends(get_session)):
    """List all AI columns."""
    result = await session.execute(
        select(IGamingAIColumn).where(IGamingAIColumn.is_active == True)
        .order_by(desc(IGamingAIColumn.created_at))
    )
    return [IGamingAIColumnResponse.model_validate(c) for c in result.scalars().all()]


@router.delete("/ai-columns/{column_id}", status_code=204)
async def delete_ai_column(column_id: int, session: AsyncSession = Depends(get_session)):
    """Delete an AI column."""
    result = await session.execute(
        select(IGamingAIColumn).where(IGamingAIColumn.id == column_id)
    )
    col = result.scalar_one_or_none()
    if not col:
        raise HTTPException(404, "AI column not found")
    col.is_active = False
    await session.flush()


@router.post("/ai-columns/{column_id}/run")
async def run_ai_column_endpoint(
    column_id: int,
    data: AIColumnRunRequest = AIColumnRunRequest(),
    session: AsyncSession = Depends(get_session),
):
    """Run AI enrichment for a column. Processes rows with the LLM."""
    try:
        result = await run_ai_column(session, column_id, data.filter_params)
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(503, str(e))


@router.get("/ai-columns/{column_id}/progress")
async def get_ai_column_progress(column_id: int):
    """Get progress of running AI column enrichment."""
    return get_ai_progress(column_id)


# ── Employee Search ────────────────────────────────────────────────────

class EmployeeSearchRequest(BaseModel):
    company_ids: list[int]
    titles: list[str] = []
    limit_per_company: int = 5
    source: str = "apollo"  # "apollo" or "clay"
    clay_webhook_url: Optional[str] = None


@router.post("/employees/search")
async def search_employees(
    data: EmployeeSearchRequest,
    session: AsyncSession = Depends(get_session),
):
    """Search for employees at selected companies via Apollo or Clay."""
    import uuid
    task_id = str(uuid.uuid4())[:8]

    if data.source == "apollo":
        try:
            result = await search_employees_apollo(
                session=session,
                company_ids=data.company_ids,
                titles=data.titles,
                limit_per_company=data.limit_per_company,
                task_id=task_id,
            )
            return {**result, "task_id": task_id}
        except RuntimeError as e:
            raise HTTPException(503, str(e))
    elif data.source == "clay":
        if not data.clay_webhook_url:
            raise HTTPException(400, "clay_webhook_url is required for Clay source")
        result = await search_employees_clay(
            session=session,
            company_ids=data.company_ids,
            titles=data.titles,
            webhook_url=data.clay_webhook_url,
            task_id=task_id,
        )
        return {**result, "task_id": task_id}
    else:
        raise HTTPException(400, f"Unknown source: {data.source}")


@router.get("/employees/search/progress/{task_id}")
async def get_employee_search_progress(task_id: str):
    """Get progress of employee search task."""
    return get_search_progress(task_id)
