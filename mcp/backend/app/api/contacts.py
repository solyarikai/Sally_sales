"""Contacts API — compatible with main app's /api/contacts contract.

The main app's ContactsPage.tsx expects these exact endpoints and response shapes.
This serves data from MCP's own database (extracted_contacts + discovered_companies).
"""
import math
import logging
from fastapi import APIRouter, Depends, Query
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, desc, asc

from app.db import get_session
from app.models.pipeline import DiscoveredCompany, ExtractedContact
from app.models.project import Project
from app.models.campaign import Campaign

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/contacts", tags=["contacts"])


def _contact_to_response(c: ExtractedContact, company: Optional[DiscoveredCompany] = None, project_name: str = None) -> dict:
    """Convert ExtractedContact to main app's Contact response shape."""
    return {
        "id": c.id,
        "email": c.email,
        "first_name": c.first_name,
        "last_name": c.last_name,
        "company_name": company.name if company else None,
        "domain": company.domain if company else (c.email.split("@")[1] if c.email and "@" in c.email else None),
        "job_title": c.job_title,
        "segment": None,
        "suitable_for": [],
        "geo": company.country if company else None,
        "project_id": c.project_id,
        "project_name": project_name,
        "source": c.email_source or "pipeline",
        "source_id": None,
        "status": "new",
        "status_external": None,
        "phone": c.phone,
        "linkedin_url": c.linkedin_url,
        "location": f"{company.city}, {company.country}" if company and company.city else (company.country if company else None),
        "notes": None,
        "smartlead_id": None,
        "getsales_id": None,
        "last_reply_at": None,
        "has_replied": False,
        "needs_followup": False,
        "latest_reply_category": None,
        "latest_reply_confidence": None,
        "provenance": c.source_data,
        "platform_state": {},
        "campaigns": [],
        "created_at": str(c.created_at) if c.created_at else None,
        "updated_at": str(c.created_at) if c.created_at else None,
    }


@router.get("")
@router.get("/")
async def list_contacts(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, le=500),
    sort_by: str = "created_at",
    sort_order: str = "desc",
    search: Optional[str] = None,
    project_id: Optional[int] = None,
    status: Optional[str] = None,
    source: Optional[str] = None,
    has_replied: Optional[bool] = None,
    needs_followup: Optional[bool] = None,
    campaign: Optional[str] = None,
    geo: Optional[str] = None,
    domain: Optional[str] = None,
    reply_category: Optional[str] = None,
    created_after: Optional[str] = None,
    created_before: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):
    """List contacts — same contract as main app's GET /api/contacts."""

    # Base query with optional company join
    query = (
        select(ExtractedContact, DiscoveredCompany)
        .outerjoin(DiscoveredCompany, DiscoveredCompany.id == ExtractedContact.discovered_company_id)
    )

    # Filters
    if project_id:
        query = query.where(ExtractedContact.project_id == project_id)
    if search:
        query = query.where(or_(
            ExtractedContact.email.ilike(f"%{search}%"),
            ExtractedContact.first_name.ilike(f"%{search}%"),
            ExtractedContact.last_name.ilike(f"%{search}%"),
        ))
    if source:
        query = query.where(ExtractedContact.email_source == source)
    if domain:
        for d in domain.split(","):
            query = query.where(DiscoveredCompany.domain.ilike(f"%{d.strip()}%"))
    if geo:
        query = query.where(DiscoveredCompany.country.ilike(f"%{geo}%"))

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await session.execute(count_query)).scalar() or 0

    # Sort
    sort_col = getattr(ExtractedContact, sort_by, ExtractedContact.created_at)
    query = query.order_by(desc(sort_col) if sort_order == "desc" else asc(sort_col))

    # Paginate
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await session.execute(query)
    rows = result.all()

    # Get project names
    project_ids = {c.project_id for c, _ in rows if c.project_id}
    project_names = {}
    if project_ids:
        pn_result = await session.execute(
            select(Project.id, Project.name).where(Project.id.in_(project_ids))
        )
        project_names = {pid: pname for pid, pname in pn_result.all()}

    contacts = [
        _contact_to_response(c, company, project_names.get(c.project_id))
        for c, company in rows
    ]

    return {
        "contacts": contacts,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if page_size > 0 else 0,
    }


@router.get("/stats")
async def contact_stats(
    project_id: Optional[int] = None,
    session: AsyncSession = Depends(get_session),
):
    """Contact statistics — same contract as main app."""
    q = select(func.count(ExtractedContact.id))
    if project_id:
        q = q.where(ExtractedContact.project_id == project_id)
    total = (await session.execute(q)).scalar() or 0

    # By source
    sq = select(ExtractedContact.email_source, func.count(ExtractedContact.id)).group_by(ExtractedContact.email_source)
    if project_id:
        sq = sq.where(ExtractedContact.project_id == project_id)
    by_source = {(row[0] or "unknown"): row[1] for row in (await session.execute(sq)).all()}

    return {
        "total": total,
        "by_status": {"new": total},
        "by_segment": {},
        "by_source": by_source,
        "by_project": {},
    }


@router.get("/filters")
async def contact_filters(session: AsyncSession = Depends(get_session)):
    """Available filter options — same contract as main app."""
    # Sources
    sources_r = await session.execute(
        select(ExtractedContact.email_source).distinct().where(ExtractedContact.email_source != None)
    )
    sources = [r[0] for r in sources_r.all()]

    # Projects
    projects_r = await session.execute(select(Project.id, Project.name).where(Project.is_active == True))
    projects = [{"id": pid, "name": pname} for pid, pname in projects_r.all()]

    return {
        "statuses": ["new"],
        "sources": sources,
        "segments": [],
        "geos": [],
        "projects": projects,
    }


@router.get("/projects/names")
async def project_names(session: AsyncSession = Depends(get_session)):
    """Project names for dropdown — same contract as main app."""
    result = await session.execute(select(Project.id, Project.name).where(Project.is_active == True))
    return [{"id": pid, "name": pname} for pid, pname in result.all()]


@router.get("/projects/list")
async def project_list(session: AsyncSession = Depends(get_session)):
    """Full project list — same contract as main app."""
    result = await session.execute(select(Project).where(Project.is_active == True))
    projects = result.scalars().all()
    return [
        {
            "id": p.id, "name": p.name, "description": None,
            "target_industries": p.target_industries, "target_segments": p.target_segments,
            "campaign_filters": p.campaign_filters or [],
            "campaign_ownership_rules": None,
            "contact_count": 0,
            "created_at": str(p.created_at) if p.created_at else None,
            "updated_at": str(p.updated_at) if p.updated_at else None,
        }
        for p in projects
    ]


@router.get("/campaigns")
async def list_campaigns(session: AsyncSession = Depends(get_session)):
    """Campaign list for CRM filters."""
    result = await session.execute(select(Campaign).order_by(Campaign.name))
    campaigns = result.scalars().all()
    return [
        {"id": str(c.id), "name": c.name, "source": c.platform, "message_count": c.leads_count or 0}
        for c in campaigns
    ]


@router.get("/{contact_id}")
async def get_contact(
    contact_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Single contact detail."""
    contact = await session.get(ExtractedContact, contact_id)
    if not contact:
        from fastapi import HTTPException
        raise HTTPException(404, "Contact not found")

    company = None
    if contact.discovered_company_id:
        company = await session.get(DiscoveredCompany, contact.discovered_company_id)

    return _contact_to_response(contact, company)


@router.patch("/{contact_id}")
async def update_contact(
    contact_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Update contact — stub for main app compatibility."""
    return {"id": contact_id, "updated": True}


@router.get("/{contact_id}/history")
async def contact_history(
    contact_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Contact conversation history — stub."""
    return {"email_history": [], "linkedin_history": [], "inbox_links": {}}
