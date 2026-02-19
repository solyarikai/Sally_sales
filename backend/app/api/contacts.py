"""
CRM Contacts API endpoints
Simple flat table with filters - project, segment, status, source
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Body, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, String, text as sql_text
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, EmailStr, field_validator
from datetime import datetime
import csv
import io
import re
import asyncio
import logging
import httpx

from app.db import get_session
from app.models.contact import Contact, Project, ContactActivity
from app.services.crm_sync_service import get_getsales_flow_name, parse_campaigns
from app.services.smartlead_service import smartlead_service
from app.core.config import settings
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
    geo: Optional[str] = None
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
    gathering_details: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    @field_validator('campaigns', mode='before')
    @classmethod
    def parse_campaigns_json(cls, v):
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return None
        return v

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
    campaign_filters: Optional[List[str]] = None


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    target_industries: Optional[str] = None
    target_segments: Optional[str] = None
    campaign_filters: Optional[List[str]] = None
    telegram_chat_id: Optional[str] = None  # Resolved chat ID (set automatically)
    telegram_username: Optional[str] = None  # Operator @username for notifications


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    target_industries: Optional[str] = None
    target_segments: Optional[str] = None
    campaign_filters: Optional[List[str]] = None
    telegram_chat_id: Optional[str] = None
    telegram_username: Optional[str] = None
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

async def _build_filtered_query(
    session: AsyncSession,
    company_id: Optional[int],
    project_id: Optional[int] = None,
    segment: Optional[str] = None,
    geo: Optional[str] = None,
    status: Optional[str] = None,
    source: Optional[str] = None,
    has_replied: Optional[bool] = None,
    has_smartlead: Optional[bool] = None,
    has_getsales: Optional[bool] = None,
    campaign: Optional[str] = None,
    campaign_id: Optional[str] = None,
    needs_followup: Optional[bool] = None,
    created_after: Optional[str] = None,
    created_before: Optional[str] = None,
    search: Optional[str] = None,
):
    """Build a filtered Contact query. Shared by list, CSV export, and Google Sheet export."""
    query = select(Contact).where(
        and_(
            Contact.company_id == company_id if company_id else True,
            Contact.deleted_at.is_(None)
        )
    )

    if project_id:
        proj_result = await session.execute(
            select(Project.campaign_filters, Project.name, Project.company_id).where(Project.id == project_id)
        )
        proj_row = proj_result.first()
        if proj_row and company_id and proj_row[2] and proj_row[2] != company_id:
            # Project belongs to a different company — return empty results
            query = query.where(sql_text("1 = 0"))
        proj_campaign_filters = proj_row[0] if proj_row else None
        proj_name = (proj_row[1] if proj_row else "") or ""

        if proj_campaign_filters and len(proj_campaign_filters) > 0:
            import os
            common = os.path.commonprefix(proj_campaign_filters).strip()
            if len(common) < 3 and proj_name and all(
                proj_name.lower() in cf.lower() for cf in proj_campaign_filters
            ):
                common = proj_name

            if len(common) >= 3:
                campaign_clause = sql_text(
                    "(contacts.project_id = :fk_pid OR contacts.campaigns::text ILIKE :cf_prefix)"
                ).bindparams(fk_pid=project_id, cf_prefix=f"%{common}%")
            else:
                prefixes = list(set(cf[:15] for cf in proj_campaign_filters))[:10]
                parts = " OR ".join(
                    f"contacts.campaigns::text ILIKE :cfp_{i}"
                    for i in range(len(prefixes))
                )
                params = {f"cfp_{i}": f"%{p}%" for i, p in enumerate(prefixes)}
                campaign_clause = sql_text(
                    f"(contacts.project_id = :fk_pid OR ({parts}))"
                ).bindparams(fk_pid=project_id, **params)

            query = query.where(campaign_clause)
        else:
            query = query.where(Contact.project_id == project_id)

    if segment:
        segments_list = [s.strip() for s in segment.split(',') if s.strip()]
        if len(segments_list) == 1:
            query = query.where(Contact.segment == segments_list[0])
        else:
            query = query.where(Contact.segment.in_(segments_list))
    if geo:
        query = query.where(Contact.geo == geo)
    if status:
        statuses = [s.strip() for s in status.split(',') if s.strip()]
        if len(statuses) == 1:
            query = query.where(Contact.status == statuses[0])
        elif len(statuses) > 1:
            query = query.where(Contact.status.in_(statuses))
    if source:
        query = query.where(Contact.source == source)
    if has_replied is not None:
        query = query.where(Contact.has_replied == has_replied)
    if has_smartlead is True:
        query = query.where(Contact.smartlead_id.isnot(None))
    elif has_smartlead is False:
        query = query.where(Contact.smartlead_id.is_(None))
    if has_getsales is True:
        query = query.where(Contact.getsales_id.isnot(None))
    elif has_getsales is False:
        query = query.where(Contact.getsales_id.is_(None))
    if campaign_id:
        ids = [i.strip() for i in campaign_id.split(',') if i.strip()]
        if len(ids) == 1:
            query = query.where(
                sql_text("contacts.campaigns::text LIKE :cid_0")
                .bindparams(cid_0=f"%{ids[0]}%")
            )
        else:
            cid_parts = " OR ".join(f"contacts.campaigns::text LIKE :cid_{i}" for i in range(len(ids)))
            cid_params = {f"cid_{i}": f"%{v}%" for i, v in enumerate(ids)}
            query = query.where(sql_text(f"({cid_parts})").bindparams(**cid_params))
    elif campaign:
        names = [n.strip() for n in campaign.split(',') if n.strip()]
        if len(names) == 1:
            query = query.where(
                sql_text("contacts.campaigns::text ILIKE :camp_0")
                .bindparams(camp_0=f"%{names[0]}%")
            )
        elif len(names) > 1:
            camp_parts = " OR ".join(f"contacts.campaigns::text ILIKE :camp_{i}" for i in range(len(names)))
            camp_params = {f"camp_{i}": f"%{n}%" for i, n in enumerate(names)}
            query = query.where(sql_text(f"({camp_parts})").bindparams(**camp_params))
    if needs_followup is True:
        from datetime import timedelta
        three_days_ago = datetime.utcnow() - timedelta(days=3)
        query = query.where(
            and_(
                Contact.has_replied == False,
                Contact.last_synced_at < three_days_ago
            )
        )
    if created_after:
        try:
            dt = datetime.fromisoformat(created_after)
            query = query.where(Contact.created_at >= dt)
        except ValueError:
            pass
    if created_before:
        try:
            dt = datetime.fromisoformat(created_before)
            query = query.where(Contact.created_at <= dt)
        except ValueError:
            pass
    if search:
        search_term = f"%{search}%"
        query = query.where(
            or_(
                Contact.email.ilike(search_term),
                Contact.first_name.ilike(search_term),
                Contact.last_name.ilike(search_term),
                Contact.company_name.ilike(search_term),
                Contact.domain.ilike(search_term),
                Contact.job_title.ilike(search_term),
            )
        )

    return query


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
    geo: Optional[str] = Query(None, description="Filter by geo: RU, Global"),
    status: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    has_replied: Optional[bool] = Query(None, description="Filter by replied status"),
    has_smartlead: Optional[bool] = Query(None, description="Filter contacts with Smartlead history"),
    has_getsales: Optional[bool] = Query(None, description="Filter contacts with GetSales history"),
    campaign: Optional[str] = Query(None, description="Filter by campaign name (partial match)"),
    campaign_id: Optional[str] = Query(None, description="Filter by campaign ID (comma-separated)"),
    needs_followup: Optional[bool] = Query(None, description="Filter contacts needing follow-up (no reply in 3+ days)"),
    created_after: Optional[str] = Query(None, description="Filter contacts created after this date (ISO format, e.g. 2026-02-02)"),
    created_before: Optional[str] = Query(None, description="Filter contacts created before this date (ISO format, e.g. 2026-02-09)"),
    session: AsyncSession = Depends(get_session),
    company_id: int | None = Depends(get_optional_company_id),
):
    """Get paginated list of contacts with filters"""
    query = await _build_filtered_query(
        session, company_id,
        project_id=project_id, segment=segment, geo=geo, status=status, source=source,
        has_replied=has_replied, has_smartlead=has_smartlead, has_getsales=has_getsales,
        campaign=campaign, campaign_id=campaign_id, needs_followup=needs_followup,
        created_after=created_after, created_before=created_before, search=search,
    )
    
    # Count total
    count_query = select(func.count()).select_from(
        select(Contact.id).where(query.whereclause).subquery()
    )
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

    # Get unique geos
    geos_result = await session.execute(
        select(Contact.geo).where(base_filter).distinct()
    )
    geos = [r[0] for r in geos_result.all() if r[0]]

    # Get projects
    projects_result = await session.execute(
        select(Project.id, Project.name)
        .where(and_(Project.company_id == company_id if company_id else True, Project.deleted_at.is_(None)))
        .order_by(Project.name)
    )
    projects = [{"id": r[0], "name": r[1]} for r in projects_result.all()]
    
    return {
        "statuses": CONTACT_STATUSES,
        "sources": sources if sources else CONTACT_SOURCES,
        "segments": segments if segments else DEFAULT_SEGMENTS,
        "geos": geos,
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
            for camp in parse_campaigns(row):
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
    
    data = contact.model_dump(exclude={"needs_followup"}, exclude_none=False)
    db_contact = Contact(
        company_id=company_id or 1,
        **data
    )
    session.add(db_contact)
    await session.commit()
    await session.refresh(db_contact)

    return ContactResponse.model_validate(db_contact)


@router.get("/verify-campaigns")
async def verify_campaigns(
    project_id: int = Query(..., description="Project ID to verify"),
    session: AsyncSession = Depends(get_session),
):
    """Compare DB contact counts per campaign with SmartLead lead counts."""
    from app.models.pipeline import CampaignPushRule

    rules_result = await session.execute(
        select(CampaignPushRule).where(
            and_(CampaignPushRule.project_id == project_id, CampaignPushRule.is_active == True)
        )
    )
    rules = rules_result.scalars().all()
    if not rules:
        raise HTTPException(status_code=404, detail="No active campaign push rules for this project")

    api_key = (
        smartlead_service.api_key
        or getattr(settings, 'SMARTLEAD_API_KEY', None)
        or settings.model_extra.get('smartlead_api_key')
    )
    if not api_key:
        raise HTTPException(status_code=500, detail="SmartLead API key not configured")

    base_url = smartlead_service.base_url or "https://server.smartlead.ai/api/v1"
    results = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        for rule in rules:
            cid = rule.current_campaign_id
            if not cid:
                results.append({
                    "name": rule.name,
                    "campaign_id": None,
                    "db_count": 0,
                    "smartlead_count": None,
                    "db_rule_count": rule.current_campaign_lead_count or 0,
                    "match": False,
                    "error": "No campaign ID set",
                })
                continue

            db_result = await session.execute(
                select(func.count()).select_from(Contact).where(
                    and_(
                        Contact.deleted_at.is_(None),
                        sql_text("contacts.campaigns::text ILIKE :cid").bindparams(cid=f"%{cid}%"),
                    )
                )
            )
            db_count = db_result.scalar() or 0

            sl_count = None
            error = None
            try:
                resp = await client.get(
                    f"{base_url}/campaigns/{cid}/analytics",
                    params={"api_key": api_key},
                )
                if resp.status_code == 200:
                    analytics = resp.json()
                    # SmartLead puts the count in campaign_lead_stats.total
                    lead_stats = analytics.get("campaign_lead_stats") or {}
                    sl_count = lead_stats.get("total") if isinstance(lead_stats, dict) else None
                    if sl_count is None:
                        # Fallback: try total_count (string in analytics)
                        tc = analytics.get("total_count")
                        if tc is not None:
                            try:
                                sl_count = int(tc)
                            except (ValueError, TypeError):
                                pass
                else:
                    error = f"SmartLead API {resp.status_code}"
            except Exception as e:
                error = str(e)[:200]

            results.append({
                "name": rule.name,
                "campaign_id": cid,
                "db_count": db_count,
                "db_rule_count": rule.current_campaign_lead_count or 0,
                "smartlead_count": sl_count,
                "match": sl_count is not None and db_count == sl_count,
                "error": error,
            })

    total_db = sum(r["db_count"] for r in results)
    total_sl = sum(r["smartlead_count"] or 0 for r in results)
    return {
        "campaigns": results,
        "total_db": total_db,
        "total_smartlead": total_sl,
        "all_match": all(r["match"] for r in results),
    }


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


def _format_campaigns(campaigns_raw) -> str:
    """Format campaigns JSON into a readable comma-separated string."""
    camps = parse_campaigns(campaigns_raw) if campaigns_raw else []
    if not camps:
        return ""
    names = []
    for c in camps:
        if isinstance(c, dict):
            names.append(c.get("name", ""))
        elif isinstance(c, str):
            names.append(c)
    return ", ".join(n for n in names if n)


EXPORT_COLUMNS = [
    "email", "first_name", "last_name", "company_name", "domain",
    "job_title", "segment", "source", "status", "campaigns",
    "phone", "linkedin_url", "location", "project_name", "created_at",
]


async def _get_filtered_contacts_for_export(
    session: AsyncSession,
    company_id: Optional[int],
    contact_ids: Optional[List[int]] = None,
    project_id: Optional[int] = None,
    campaign: Optional[str] = None,
    segment: Optional[str] = None,
    geo: Optional[str] = None,
    status: Optional[str] = None,
    source: Optional[str] = None,
    search: Optional[str] = None,
    has_replied: Optional[bool] = None,
    created_after: Optional[str] = None,
    created_before: Optional[str] = None,
):
    """Query contacts using either contact_ids or CRM filters. Returns (contacts, project_names)."""
    if contact_ids:
        query = select(Contact).where(
            and_(
                Contact.company_id == company_id if company_id else True,
                Contact.deleted_at.is_(None),
                Contact.id.in_(contact_ids),
            )
        )
    else:
        query = await _build_filtered_query(
            session, company_id,
            project_id=project_id, campaign=campaign, segment=segment, geo=geo,
            status=status, source=source, search=search,
            has_replied=has_replied, created_after=created_after,
            created_before=created_before,
        )

    query = query.order_by(Contact.created_at.desc())
    result = await session.execute(query)
    contacts = result.scalars().all()

    # Resolve project names
    pids = list(set(c.project_id for c in contacts if c.project_id))
    project_names: Dict[int, str] = {}
    if pids:
        pr = await session.execute(select(Project.id, Project.name).where(Project.id.in_(pids)))
        for row in pr.all():
            project_names[row[0]] = row[1]

    return contacts, project_names


class ExportFiltersBody(BaseModel):
    contact_ids: Optional[List[int]] = None
    project_id: Optional[int] = None
    campaign: Optional[str] = None
    segment: Optional[str] = None
    status: Optional[str] = None
    source: Optional[str] = None
    search: Optional[str] = None
    has_replied: Optional[bool] = None
    created_after: Optional[str] = None
    created_before: Optional[str] = None


@router.post("/export/csv")
async def export_contacts_csv(
    body: ExportFiltersBody = Body(ExportFiltersBody()),
    session: AsyncSession = Depends(get_session),
    company_id: int | None = Depends(get_optional_company_id),
):
    """Export contacts as CSV. Accepts CRM filters or explicit contact_ids."""
    contacts, project_names = await _get_filtered_contacts_for_export(
        session, company_id,
        contact_ids=body.contact_ids, project_id=body.project_id,
        campaign=body.campaign, segment=body.segment, status=body.status,
        source=body.source, search=body.search, has_replied=body.has_replied,
        created_after=body.created_after, created_before=body.created_before,
    )

    if not contacts:
        raise HTTPException(status_code=404, detail="No contacts to export")

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=EXPORT_COLUMNS)
    writer.writeheader()

    for c in contacts:
        row = {}
        for col in EXPORT_COLUMNS:
            if col == "campaigns":
                row[col] = _format_campaigns(c.campaigns)
            elif col == "project_name":
                row[col] = project_names.get(c.project_id, "") if c.project_id else ""
            elif col == "created_at":
                row[col] = c.created_at.strftime("%Y-%m-%d %H:%M") if c.created_at else ""
            else:
                row[col] = getattr(c, col, "") or ""
        writer.writerow(row)

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=contacts.csv"},
    )


@router.post("/export/google-sheet")
async def export_contacts_google_sheet(
    body: ExportFiltersBody = Body(...),
    session: AsyncSession = Depends(get_session),
    company_id: int | None = Depends(get_optional_company_id),
):
    """Export filtered contacts to a new Google Sheet. Returns {url, rows}."""
    from app.services.google_sheets_service import GoogleSheetsService

    contacts, project_names = await _get_filtered_contacts_for_export(
        session, company_id,
        contact_ids=body.contact_ids, project_id=body.project_id,
        campaign=body.campaign, segment=body.segment, status=body.status,
        source=body.source, search=body.search, has_replied=body.has_replied,
        created_after=body.created_after, created_before=body.created_before,
    )

    if not contacts:
        raise HTTPException(status_code=400, detail="No contacts matching filters")

    # Build sheet data: header + rows
    header = [col.replace("_", " ").title() for col in EXPORT_COLUMNS]
    data = [header]
    for c in contacts:
        row = []
        for col in EXPORT_COLUMNS:
            if col == "campaigns":
                row.append(_format_campaigns(c.campaigns))
            elif col == "project_name":
                row.append(project_names.get(c.project_id, "") if c.project_id else "")
            elif col == "created_at":
                row.append(c.created_at.strftime("%Y-%m-%d %H:%M") if c.created_at else "")
            else:
                row.append(str(getattr(c, col, "") or ""))
        data.append(row)

    # Build title
    parts = []
    if body.project_id:
        pname = project_names.get(body.project_id, f"Project {body.project_id}")
        parts.append(pname)
    if body.campaign:
        parts.append(f"campaigns: {body.campaign[:60]}")
    if body.segment:
        parts.append(body.segment)
    filter_desc = " | ".join(parts) if parts else "All"
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    title = f"CRM Export — {filter_desc} — {ts}"

    gs = GoogleSheetsService()
    url = gs.create_and_populate(
        title=title,
        data=data,
        share_with=["pn@getsally.io", "pavel.l@getsally.io", "danuta@getsally.io"],
    )
    if not url:
        raise HTTPException(status_code=500, detail="Google Sheets export failed — check service account credentials")

    return {"url": url, "rows": len(data) - 1}


# ============= Projects Endpoints =============

@router.get("/projects/list-lite")
async def list_projects_lite(
    session: AsyncSession = Depends(get_session),
    company_id: int | None = Depends(get_optional_company_id),
):
    """List all projects without contact counts — instant response for dropdowns."""
    result = await session.execute(
        select(Project.id, Project.name, Project.campaign_filters, Project.telegram_username)
        .where(and_(Project.company_id == company_id if company_id else True, Project.deleted_at.is_(None)))
        .order_by(Project.name)
    )
    return [
        {"id": row[0], "name": row[1], "campaign_filters": row[2] or [], "telegram_username": row[3]}
        for row in result.all()
    ]


@router.get("/projects/names")
async def list_project_names(
    session: AsyncSession = Depends(get_session),
    company_id: int | None = Depends(get_optional_company_id),
):
    """Fast endpoint: return just id+name for dropdowns (no contact counts)."""
    result = await session.execute(
        select(Project.id, Project.name)
        .where(and_(Project.company_id == company_id if company_id else True, Project.deleted_at.is_(None)))
        .order_by(Project.name)
    )
    return [{"id": row.id, "name": row.name} for row in result.all()]


@router.get("/projects/list", response_model=List[ProjectResponse])
async def list_projects(
    session: AsyncSession = Depends(get_session),
    company_id: int | None = Depends(get_optional_company_id),
):
    """List all projects with contact counts"""
    
    result = await session.execute(
        select(Project)
        .where(and_(Project.company_id == company_id if company_id else True, Project.deleted_at.is_(None)))
        .order_by(Project.name)
    )
    projects = result.scalars().all()
    
    # Get contact counts
    project_responses = []
    for project in projects:
        if project.campaign_filters and len(project.campaign_filters) > 0:
            # Dynamic count based on FK OR campaign_filters
            cf_parts = " OR ".join(
                f"contacts.campaigns::text ILIKE :pcf_{i}" for i in range(len(project.campaign_filters))
            )
            cf_params = {f"pcf_{i}": f"%{cf}%" for i, cf in enumerate(project.campaign_filters)}
            count_result = await session.execute(
                sql_text(f"""
                    SELECT COUNT(DISTINCT id) FROM contacts
                    WHERE deleted_at IS NULL
                    AND (project_id = :pid OR ({cf_parts}))
                """).bindparams(pid=project.id, **cf_params)
            )
        else:
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
            campaign_filters=project.campaign_filters,
            telegram_chat_id=project.telegram_chat_id,
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

    # Check for duplicate name
    existing = await session.execute(
        select(Project.id).where(
            Project.company_id == (company_id or 1),
            Project.name == project.name.strip(),
        ).limit(1)
    )
    if existing.scalar():
        raise HTTPException(status_code=409, detail=f"Project '{project.name}' already exists")

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
        campaign_filters=db_project.campaign_filters,
        telegram_chat_id=db_project.telegram_chat_id,
        contact_count=0,
        created_at=db_project.created_at,
        updated_at=db_project.updated_at,
    )


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    session: AsyncSession = Depends(get_session),
    company_id: int | None = Depends(get_optional_company_id),
):
    """Get a single project by ID"""
    result = await session.execute(
        select(Project).where(
            and_(
                Project.id == project_id,
                Project.company_id == company_id if company_id else True,
                Project.deleted_at.is_(None),
            )
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Contact count
    if project.campaign_filters and len(project.campaign_filters) > 0:
        cf_parts = " OR ".join(
            f"contacts.campaigns::text ILIKE :pcf_{i}" for i in range(len(project.campaign_filters))
        )
        cf_params = {f"pcf_{i}": f"%{cf}%" for i, cf in enumerate(project.campaign_filters)}
        count_result = await session.execute(
            sql_text(f"""
                SELECT COUNT(DISTINCT id) FROM contacts
                WHERE deleted_at IS NULL
                AND (project_id = :pid OR ({cf_parts}))
            """).bindparams(pid=project.id, **cf_params)
        )
    else:
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
        campaign_filters=project.campaign_filters,
        telegram_chat_id=project.telegram_chat_id,
        contact_count=contact_count,
        created_at=project.created_at,
        updated_at=project.updated_at,
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
                Project.company_id == company_id if company_id else True,
                Project.deleted_at.is_(None)
            )
        )
    )
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    update_data = updates.model_dump(exclude_unset=True)

    # Resolve telegram_username -> chat_id from registrations table
    if "telegram_username" in update_data:
        username = (update_data["telegram_username"] or "").strip().lstrip("@").lower()
        if username:
            from app.models.reply import TelegramRegistration
            reg_result = await session.execute(
                select(TelegramRegistration).where(
                    TelegramRegistration.telegram_username == username
                )
            )
            reg = reg_result.scalar_one_or_none()
            if reg:
                update_data["telegram_chat_id"] = reg.telegram_chat_id
                update_data["telegram_username"] = username
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Telegram user @{username} has not registered with the bot yet. "
                           f"Ask them to send /start to @impecablebot first."
                )
        else:
            # Clear both fields if username is empty
            update_data["telegram_username"] = None
            update_data["telegram_chat_id"] = None

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
        campaign_filters=project.campaign_filters,
        telegram_chat_id=project.telegram_chat_id,
        telegram_username=project.telegram_username,
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
                Project.company_id == company_id if company_id else True,
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


# ============= Auto-Create Projects + Conversation Analysis =============

@router.post("/projects/auto-create")
async def auto_create_projects_endpoint(
    session: AsyncSession = Depends(get_session),
    company_id: int | None = Depends(get_optional_company_id),
):
    """
    Auto-create projects for 14 agency names based on campaign matching.

    For each agency name, finds campaigns containing that name (case-insensitive)
    and creates a Project with campaign_filters = matching campaign names.
    Skips if project with same name already exists.
    """
    from app.services.project_service import auto_create_projects

    result = await auto_create_projects(session, company_id=company_id or 1)
    await session.commit()
    return result


@router.post("/projects/{project_id}/generate-reply-prompt")
async def generate_reply_prompt_endpoint(
    project_id: int,
    max_conversations: int = Query(10, ge=1, le=50),
    session: AsyncSession = Depends(get_session),
):
    """
    Analyze project conversations and generate an auto-reply prompt template.

    Finds contacts with replies matching project's campaign_filters,
    sends conversation threads to GPT-4o-mini for analysis,
    and stores the resulting prompt template.
    """
    from app.services.conversation_analysis_service import generate_auto_reply_prompt

    result = await generate_auto_reply_prompt(session, project_id, max_conversations)
    if not result:
        raise HTTPException(status_code=404, detail="Project not found")
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    await session.commit()
    return result


@router.get("/projects/{project_id}/conversations-debug")
async def get_conversations_debug(
    project_id: int,
    max_conversations: int = Query(10, ge=1, le=50),
    session: AsyncSession = Depends(get_session),
):
    """
    Get formatted conversation threads for a project (debug/review).

    Shows all message exchanges for contacts with replies in this project.
    """
    from app.services.conversation_analysis_service import (
        get_project_conversations,
        format_conversations_debug,
    )

    conversations = await get_project_conversations(session, project_id, max_conversations)
    if not conversations:
        return {"project_id": project_id, "conversations": [], "formatted": "No conversations found"}

    formatted = format_conversations_debug(conversations)
    return {
        "project_id": project_id,
        "count": len(conversations),
        "conversations": conversations,
        "formatted": formatted,
    }


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
    company_id: int | None = None,
) -> tuple:
    """Helper to get project and its contacts."""
    filters = [
        Project.id == project_id,
        Project.deleted_at.is_(None),
    ]
    if company_id:
        filters.append(Project.company_id == company_id)
    
    result = await session.execute(
        select(Project).where(and_(*filters))
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
                Project.company_id == company_id if company_id else True,
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
    project, contacts = await _get_project_with_contacts(project_id, session, company_id)
    
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
    project, contacts = await _get_project_with_contacts(project_id, session, company_id)
    
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
    project, contacts = await _get_project_with_contacts(project_id, session, company_id)
    
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
    project, contacts = await _get_project_with_contacts(project_id, session, company_id)
    
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
    project, contacts = await _get_project_with_contacts(project_id, session, company_id)
    
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


def _strip_html(html: str) -> str:
    """Strip HTML tags and decode entities to get plain text."""
    if not html:
        return ""
    import html as html_mod
    # Remove style/script blocks
    text = re.sub(r'<(style|script)[^>]*>.*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)
    # Replace <br>, <div>, <p> with newlines
    text = re.sub(r'<br\s*/?>|</div>|</p>', '\n', text, flags=re.IGNORECASE)
    # Remove all remaining tags
    text = re.sub(r'<[^>]+>', '', text)
    # Decode HTML entities
    text = html_mod.unescape(text)
    # Strip quoted reply chains ("On ... wrote:" and everything after)
    text = re.sub(r'\s*On\s+\w{3},\s+\w{3,9}\s+\d{1,2},\s+\d{4}\s+at\s+\d{1,2}:\d{2}\s*[AP]M\s+.*?\s+wrote:.*', '', text, flags=re.DOTALL)
    # Also strip "Sent from my iPhone" etc.
    text = re.sub(r'\s*Sent from my .*', '', text, flags=re.DOTALL)
    # Clean up excessive whitespace/newlines
    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    return text


async def _fetch_smartlead_live_history(email: str) -> list:
    """Fetch complete email history from Smartlead API across all campaigns for a lead."""
    api_key = (
        smartlead_service.api_key
        or getattr(settings, 'SMARTLEAD_API_KEY', None)
        or settings.model_extra.get('smartlead_api_key')
    )
    if not api_key:
        return []

    base_url = smartlead_service.base_url or "https://server.smartlead.ai/api/v1"

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Step 1: Find all campaigns for this email via global leads endpoint
        try:
            resp = await client.get(
                f"{base_url}/leads/",
                params={"api_key": api_key, "email": email}
            )
            if resp.status_code != 200:
                logger.warning(f"Smartlead global leads lookup failed: {resp.status_code}")
                return []
            lead_data = resp.json()
        except Exception as e:
            logger.warning(f"Smartlead global leads lookup error: {e}")
            return []

        # Parse global lead ID and campaign list from response
        # Response: {id: "2916006166", lead_campaign_data: [{campaign_id, campaign_name, ...}]}
        global_lead_id = None
        campaign_entries = []
        if isinstance(lead_data, dict):
            global_lead_id = lead_data.get("id")
            for c in lead_data.get("lead_campaign_data", []):
                cid = c.get("campaign_id")
                cname = c.get("campaign_name", "")
                if cid:
                    campaign_entries.append((str(cid), cname))
        elif isinstance(lead_data, list):
            for entry in lead_data:
                if not global_lead_id:
                    global_lead_id = entry.get("id")
                cid = entry.get("campaign_id")
                cname = entry.get("campaign_name", "")
                if cid:
                    campaign_entries.append((str(cid), cname))

        if not campaign_entries or not global_lead_id:
            return []

        # Step 2: Fetch message history per campaign using global lead ID (parallel, batched)
        all_messages = []

        async def fetch_one(cid: str, cname: str):
            try:
                r = await client.get(
                    f"{base_url}/campaigns/{cid}/leads/{global_lead_id}/message-history",
                    params={"api_key": api_key}
                )
                if r.status_code != 200:
                    return []
                data = r.json()
                msgs = data.get("history", []) if isinstance(data, dict) else data
                result = []
                for msg in msgs:
                    msg_type = (msg.get("type") or "").upper()
                    is_reply = "REPLY" in msg_type
                    raw_body = msg.get("email_body") or msg.get("body") or ""
                    body = _strip_html(raw_body)
                    ts = msg.get("time") or msg.get("timestamp") or ""
                    result.append({
                        "id": abs(hash(f"{cid}-{ts}-{msg_type}")) % (10**9),
                        "type": "email_reply" if is_reply else "email_sent",
                        "direction": "inbound" if is_reply else "outbound",
                        "subject": msg.get("email_subject") or msg.get("subject") or "",
                        "body": body,
                        "snippet": body[:200] if body else None,
                        "channel": "email",
                        "source": "smartlead",
                        "campaign": cname,
                        "timestamp": ts,
                    })
                return result
            except Exception:
                return []

        batch_size = 10
        for i in range(0, len(campaign_entries), batch_size):
            batch = campaign_entries[i:i + batch_size]
            tasks = [fetch_one(cid, cname) for cid, cname in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, list):
                    all_messages.extend(r)

        return all_messages


@router.get("/{contact_id}/sequence-plan")
async def get_contact_sequence_plan(
    contact_id: int,
    session: AsyncSession = Depends(get_session),
):
    """
    Get the email sequence plan for a contact — for each campaign the contact
    is enrolled in, return the sequence steps with sent/scheduled/pending status.
    Uses cached SmartLead API calls to avoid 429s.
    """
    from app.services.smartlead_service import smartlead_service
    import json as _json

    contact_result = await session.execute(
        select(Contact).where(Contact.id == contact_id)
    )
    contact = contact_result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    # Parse campaigns from contact
    campaigns_raw = contact.campaigns
    if isinstance(campaigns_raw, str):
        try:
            campaigns_raw = _json.loads(campaigns_raw)
        except Exception:
            campaigns_raw = []
    if not campaigns_raw or not isinstance(campaigns_raw, list):
        return {"contact_id": contact_id, "campaigns": [], "message": "No campaigns found"}

    # Dedupe campaign IDs
    seen_ids = set()
    unique_campaigns = []
    for camp in campaigns_raw:
        cid = str(camp.get("id", ""))
        if cid and cid not in seen_ids:
            seen_ids.add(cid)
            unique_campaigns.append(camp)

    # Fetch live Smartlead history to figure out which steps were sent
    sent_steps: dict[str, set] = {}  # campaign_id -> set of seq_numbers
    email_history = []
    if contact.email:
        try:
            email_history = await _fetch_smartlead_live_history(contact.email)
        except Exception:
            pass

    # Map sent emails to sequence steps by campaign
    for msg in email_history:
        camp_id = str(msg.get("campaign_id", ""))
        seq_num = msg.get("sequence_number") or msg.get("seq_number")
        if camp_id and seq_num is not None:
            sent_steps.setdefault(camp_id, set()).add(int(seq_num))

    # For each campaign, fetch sequences and mark status
    result_campaigns = []
    for camp in unique_campaigns:
        campaign_id = str(camp.get("id", ""))
        campaign_name = camp.get("name", "")

        steps = []
        try:
            sequences = await smartlead_service.get_campaign_sequences(campaign_id)
            sent_set = sent_steps.get(campaign_id, set())

            for seq in sequences:
                seq_num = seq.get("seq_number", 0)
                # Determine status
                if seq_num in sent_set:
                    status = "sent"
                elif any(n < seq_num for n in sent_set):
                    status = "scheduled"  # earlier steps sent, this one is next
                else:
                    status = "pending"

                # Extract subject and body (handle variants)
                subject = seq.get("subject", "")
                body = seq.get("email_body", "")
                variants = seq.get("sequence_variants") or []
                if variants and isinstance(variants, list):
                    v = variants[0]
                    subject = subject or v.get("subject", "")
                    body = body or v.get("email_body", "")

                steps.append({
                    "seq_number": seq_num,
                    "subject": subject,
                    "body_preview": (body or "")[:200],
                    "status": status,
                })
        except Exception as e:
            logger.warning(f"Failed to fetch sequences for campaign {campaign_id}: {e}")

        result_campaigns.append({
            "campaign_id": campaign_id,
            "campaign_name": campaign_name,
            "source": camp.get("source", "smartlead"),
            "steps": steps,
            "total_steps": len(steps),
            "steps_sent": sum(1 for s in steps if s["status"] == "sent"),
        })

    return {
        "contact_id": contact_id,
        "email": contact.email,
        "campaigns": result_campaigns,
    }


@router.get("/{contact_id}/history")
async def get_contact_history(
    contact_id: int,
    session: AsyncSession = Depends(get_session),
):
    """
    Get full communication history for a contact, organized by channel.
    Fetches live data from Smartlead API for complete cross-campaign history.

    Returns:
    - email_history: List of email activities (live from Smartlead + local DB)
    - linkedin_history: List of LinkedIn activities from GetSales
    - summary: counts and last activity dates
    """
    # Get contact info first
    contact_result = await session.execute(
        select(Contact).where(Contact.id == contact_id)
    )
    contact = contact_result.scalar_one_or_none()

    # Get local DB activities
    result = await session.execute(
        select(ContactActivity)
        .where(ContactActivity.contact_id == contact_id)
        .order_by(ContactActivity.activity_at.desc())
    )
    activities = result.scalars().all()
    linkedin_activities = [a for a in activities if a.channel == "linkedin"]

    # Fetch live Smartlead history if contact has email
    email_history = []
    if contact and contact.email:
        try:
            smartlead_messages = await _fetch_smartlead_live_history(contact.email)
            if smartlead_messages:
                email_history = smartlead_messages
        except Exception as e:
            logger.warning(f"Failed to fetch live Smartlead history for {contact.email}: {e}")

    # Fall back to local DB if Smartlead fetch returned nothing
    if not email_history:
        email_activities = [a for a in activities if a.channel == "email"]
        email_history = [
            {
                "id": a.id,
                "type": a.activity_type,
                "direction": a.direction,
                "subject": a.subject,
                "body": a.body,
                "snippet": a.snippet,
                "channel": "email",
                "source": a.source,
                "campaign": a.extra_data.get("campaign_name") if a.extra_data else None,
                "timestamp": a.activity_at.isoformat(),
            }
            for a in email_activities
        ]

    return {
        "contact_id": contact_id,
        "email_history": email_history,
        "linkedin_history": [
            {
                "id": a.id,
                "type": a.activity_type,
                "direction": a.direction,
                "body": a.body,
                "snippet": a.snippet,
                "channel": "linkedin",
                "source": a.source,
                "automation": get_getsales_flow_name(a.extra_data, contact.campaigns if contact else None),
                "timestamp": a.activity_at.isoformat(),
            }
            for a in linkedin_activities
        ],
        "summary": {
            "total_activities": len(email_history) + len(linkedin_activities),
            "email_count": len(email_history),
            "linkedin_count": len(linkedin_activities),
            "has_email_history": len(email_history) > 0,
            "has_linkedin_history": len(linkedin_activities) > 0,
            "smartlead_id": contact.smartlead_id if contact else None,
            "getsales_id": contact.getsales_id if contact else None,
        }
    }


@router.post("/{contact_id}/generate-reply")
async def generate_reply_for_contact(
    contact_id: int,
    session: AsyncSession = Depends(get_session),
):
    """
    Generate an AI draft reply for a contact based on their latest inbound activity.
    Returns cached version if one exists for the latest reply.
    """
    from app.services.reply_processor import classify_reply, generate_draft_reply
    from app.models.reply import ProcessedReply

    # Get contact
    result = await session.execute(select(Contact).where(Contact.id == contact_id))
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    # Find latest inbound activity (reply)
    activity_result = await session.execute(
        select(ContactActivity)
        .where(
            and_(
                ContactActivity.contact_id == contact_id,
                ContactActivity.direction == "inbound",
            )
        )
        .order_by(ContactActivity.activity_at.desc())
        .limit(1)
    )
    latest_inbound = activity_result.scalar_one_or_none()

    if not latest_inbound:
        return {
            "has_reply": False,
            "message": "No inbound activity found for this contact",
        }

    # Check for cached ProcessedReply by email
    cached_result = await session.execute(
        select(ProcessedReply)
        .where(ProcessedReply.lead_email == contact.email)
        .order_by(ProcessedReply.processed_at.desc())
        .limit(1)
    )
    cached = cached_result.scalar_one_or_none()

    if cached and cached.draft_reply:
        return {
            "has_reply": True,
            "cached": True,
            "category": cached.category,
            "draft_subject": cached.draft_subject,
            "draft_body": cached.draft_reply,
            "channel": latest_inbound.channel,
            "reply_text": cached.reply_text or cached.email_body,
            "contact": {
                "name": f"{contact.first_name or ''} {contact.last_name or ''}".strip(),
                "email": contact.email,
                "company": contact.company_name,
            },
        }

    # Generate fresh classification + draft
    subject = latest_inbound.subject or ""
    body = latest_inbound.body or latest_inbound.snippet or ""

    # Resolve sender identity from project
    _sender_name = None
    _sender_position = None
    _sender_company = None
    if contact.project_id:
        try:
            proj_result = await session.execute(
                select(Project).where(Project.id == contact.project_id)
            )
            proj = proj_result.scalar_one_or_none()
            if proj:
                _sender_name = proj.sender_name
                _sender_position = proj.sender_position
                _sender_company = proj.sender_company
        except Exception:
            pass  # Non-fatal

    try:
        classification = await classify_reply(subject=subject, body=body)
        draft = await generate_draft_reply(
            subject=subject,
            body=body,
            category=classification.get("category", "other"),
            first_name=contact.first_name or "",
            last_name=contact.last_name or "",
            company=contact.company_name or "",
            sender_name=_sender_name,
            sender_position=_sender_position,
            sender_company=_sender_company,
        )
    except Exception as e:
        logger.error(f"Failed to generate reply for contact {contact_id}: {e}")
        return {
            "has_reply": True,
            "cached": False,
            "category": "error",
            "draft_subject": f"Re: {subject}",
            "draft_body": "(Draft generation failed — please write manually)",
            "channel": latest_inbound.channel,
            "reply_text": body,
            "error": str(e),
        }

    return {
        "has_reply": True,
        "cached": False,
        "category": classification.get("category", "other"),
        "draft_subject": draft.get("subject", f"Re: {subject}"),
        "draft_body": draft.get("body", ""),
        "channel": latest_inbound.channel,
        "reply_text": body,
        "contact": {
            "name": f"{contact.first_name or ''} {contact.last_name or ''}".strip(),
            "email": contact.email,
            "company": contact.company_name,
        },
    }


# Status mapping: CRM status -> Smartlead category ID
SMARTLEAD_STATUS_MAPPING = {
    "warm": 1,              # Interested
    "scheduled": 77598,     # Meeting Booked
    "qualified": 77597,     # Qualified
    "not_qualified": 78987, # Not Qualified
    "not_interested": 3,    # Not Interested
    "wrong_person": 7,      # Wrong Person
    "out_of_office": 6,     # Out Of Office
}

SMARTLEAD_PAUSE_ON_STATUS = {"scheduled", "qualified", "not_qualified", "not_interested", "wrong_person"}


class StatusUpdateRequest(BaseModel):
    status: str
    sync_to_smartlead: bool = True
    notes: Optional[str] = None


@router.patch("/{contact_id}/status")
async def update_contact_status(
    contact_id: int,
    request: StatusUpdateRequest,
    session: AsyncSession = Depends(get_session)
):
    """
    Update contact status and sync to Smartlead.
    
    - Updates contact.status in CRM
    - If contact has smartlead_id, updates category in Smartlead API
    """
    import httpx
    import os
    
    # Get contact
    result = await session.execute(select(Contact).where(Contact.id == contact_id))
    contact = result.scalar()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    old_status = contact.status
    contact.status = request.status
    
    # Sync to Smartlead if enabled and contact has smartlead_id
    smartlead_synced = False
    if request.sync_to_smartlead and contact.smartlead_id and request.status in SMARTLEAD_STATUS_MAPPING:
        api_key = os.getenv("SMARTLEAD_API_KEY")
        if api_key:
            category_id = SMARTLEAD_STATUS_MAPPING[request.status]
            pause_lead = request.status in SMARTLEAD_PAUSE_ON_STATUS
            
            # Get campaign ID from contact's campaigns
            campaign_id = None
            if contact.campaigns:
                for c in parse_campaigns(contact.campaigns):
                    if isinstance(c, dict) and c.get("source") == "smartlead":
                        campaign_id = c.get("id")
                        break
            
            if campaign_id:
                try:
                    async with httpx.AsyncClient() as client:
                        resp = await client.post(
                            f"https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/leads/{contact.smartlead_id}/category?api_key={api_key}",
                            json={"category_id": category_id, "pause_lead": pause_lead},
                            timeout=30
                        )
                        smartlead_synced = resp.status_code == 200
                except Exception as e:
                    pass  # Log but don't fail

    # Auto-create tasks when status changes to "scheduled"
    tasks_created = 0
    if request.status == "scheduled" and old_status != "scheduled":
        from app.models.task import OperatorTask
        from datetime import timedelta
        contact_name = f"{contact.first_name or ''} {contact.last_name or ''}".strip() or contact.email

        # Next business day 9:00 AM
        tomorrow = datetime.utcnow().replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)
        # Skip weekends
        while tomorrow.weekday() >= 5:
            tomorrow += timedelta(days=1)

        # Task 1: Morning ping
        morning_task = OperatorTask(
            project_id=contact.project_id,
            contact_id=contact.id,
            task_type="morning_ping",
            title=f"Morning ping — {contact_name}",
            description=f"Send a morning message to {contact_name} ({contact.email}) before the scheduled meeting",
            due_at=tomorrow,
            contact_email=contact.email,
            contact_name=contact_name,
        )
        session.add(morning_task)

        # Task 2: Pre-meeting reminder (30 min after morning ping)
        pre_meeting_task = OperatorTask(
            project_id=contact.project_id,
            contact_id=contact.id,
            task_type="pre_meeting",
            title=f"Pre-meeting reminder — {contact_name}",
            description=f"Remind {contact_name} ({contact.email}) about the upcoming meeting",
            due_at=tomorrow + timedelta(minutes=30),
            contact_email=contact.email,
            contact_name=contact_name,
        )
        session.add(pre_meeting_task)
        tasks_created = 2

    await session.commit()

    return {
        "id": contact.id,
        "email": contact.email,
        "old_status": old_status,
        "new_status": contact.status,
        "smartlead_synced": smartlead_synced,
        "getsales_synced": False,  # Not supported via API
        "tasks_created": tasks_created,
    }
