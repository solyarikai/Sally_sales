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
from app.models.user import MCPUser
from app.auth.dependencies import get_optional_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/contacts", tags=["contacts"])


def _contact_to_response(c: ExtractedContact, company: Optional[DiscoveredCompany] = None, project_name: str = None) -> dict:
    """Convert ExtractedContact to main app's Contact response shape."""
    sd = c.source_data or {}

    # Build campaigns list with clickable links
    campaigns = []
    if sd.get("campaign"):
        camp_id = sd.get("campaign_id", "")
        camp_link = None
        if camp_id:
            camp_link = f"https://app.smartlead.ai/app/email-campaigns-v2/{camp_id}/analytics"
        campaigns.append({
            "id": str(camp_id),
            "name": sd["campaign"],
            "source": "smartlead",
            "url": camp_link,
        })

    # Domain from company or email
    domain = None
    if company and company.domain:
        domain = company.domain
    elif c.email and "@" in c.email:
        domain = c.email.split("@")[1]

    return {
        "id": c.id,
        "email": c.email,
        "first_name": c.first_name,
        "last_name": c.last_name,
        "company_name": sd.get("company_name") or (company.name if company else None),
        "domain": domain,
        "job_title": c.job_title,
        "segment": None,
        "suitable_for": [],
        "geo": company.country if company else None,
        "project_id": c.project_id,
        "project_name": project_name,
        "source": c.email_source or "pipeline",
        "source_id": str(sd.get("campaign_id", "")) if sd.get("campaign_id") else None,
        "status": "new",
        "status_external": None,
        "phone": c.phone,
        "linkedin_url": c.linkedin_url,
        "location": f"{company.city}, {company.country}" if company and company.city else (company.country if company else None),
        "notes": None,
        "smartlead_id": str(sd.get("campaign_id", "")) if sd.get("campaign_id") else None,
        "getsales_id": None,
        "last_reply_at": sd.get("reply_time"),
        "has_replied": sd.get("has_replied", False),
        "needs_followup": sd.get("has_replied", False) and sd.get("reply_category") in ("interested", "meeting", "question"),
        "latest_reply_category": sd.get("reply_category"),
        "latest_reply_confidence": str(sd.get("reply_confidence", "")) if sd.get("reply_confidence") else None,
        "provenance": sd,
        "platform_state": {
            "smartlead": {
                "campaigns": [{"id": str(sd.get("campaign_id", "")), "name": sd["campaign"]}] if sd.get("campaign") else [],
            },
        } if sd.get("campaign") else {},
        "campaigns": campaigns,
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
    pipeline: Optional[int] = None,
    created_after: Optional[str] = None,
    created_before: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    user: MCPUser = Depends(get_optional_user),
):
    """List contacts — same contract as main app's GET /api/contacts."""

    # Base query with optional company join
    query = (
        select(ExtractedContact, DiscoveredCompany)
        .outerjoin(DiscoveredCompany, DiscoveredCompany.id == ExtractedContact.discovered_company_id)
    )

    # User-scope: only show contacts from user's projects
    if user:
        user_projects = await session.execute(select(Project.id).where(Project.user_id == user.id))
        pids = [pid for (pid,) in user_projects.all()]
        if pids:
            query = query.where(ExtractedContact.project_id.in_(pids))
        else:
            return {"contacts": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0}

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
    if has_replied:
        # Filter contacts whose source_data has "has_replied": true
        from sqlalchemy import cast, String
        query = query.where(ExtractedContact.source_data["has_replied"].as_boolean() == True)
    if needs_followup:
        # Contacts who replied but need follow-up action
        query = query.where(ExtractedContact.source_data["has_replied"].as_boolean() == True)
    if reply_category:
        # Filter by reply category (warm=interested, meeting, etc.)
        for cat in reply_category.split(","):
            cat = cat.strip()
            if cat == "warm":
                query = query.where(
                    ExtractedContact.source_data["reply_category"].astext.in_(["interested", "meeting", "question"])
                )
            else:
                query = query.where(ExtractedContact.source_data["reply_category"].astext == cat)
    if campaign:
        query = query.where(ExtractedContact.source_data["campaign"].astext.ilike(f"%{campaign}%"))
    if pipeline:
        # Filter contacts from a specific pipeline run (via discovered_company → source_links)
        from app.models.gathering import CompanySourceLink
        pipeline_companies = select(CompanySourceLink.discovered_company_id).where(
            CompanySourceLink.gathering_run_id == pipeline
        ).distinct()
        query = query.where(ExtractedContact.discovered_company_id.in_(pipeline_companies))
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
    user: MCPUser = Depends(get_optional_user),
):
    """Contact statistics — same contract as main app."""
    # User-scope
    user_pids = None
    if user:
        up = await session.execute(select(Project.id).where(Project.user_id == user.id))
        user_pids = [pid for (pid,) in up.all()]

    q = select(func.count(ExtractedContact.id))
    if project_id:
        q = q.where(ExtractedContact.project_id == project_id)
    elif user_pids is not None:
        if user_pids:
            q = q.where(ExtractedContact.project_id.in_(user_pids))
        else:
            return {"total": 0, "by_status": {}, "by_segment": {}, "by_source": {}, "by_project": {}}
    total = (await session.execute(q)).scalar() or 0

    # By source
    sq = select(ExtractedContact.email_source, func.count(ExtractedContact.id)).group_by(ExtractedContact.email_source)
    if project_id:
        sq = sq.where(ExtractedContact.project_id == project_id)
    elif user_pids:
        sq = sq.where(ExtractedContact.project_id.in_(user_pids))
    by_source = {(row[0] or "unknown"): row[1] for row in (await session.execute(sq)).all()}

    return {
        "total": total,
        "by_status": {"new": total},
        "by_segment": {},
        "by_source": by_source,
        "by_project": {},
    }


@router.get("/filters")
async def contact_filters(
    session: AsyncSession = Depends(get_session),
    user: MCPUser = Depends(get_optional_user),
):
    """Available filter options — same contract as main app."""
    user_filter = Project.is_active == True
    if user:
        user_filter = (Project.user_id == user.id) & (Project.is_active == True)

    sources_r = await session.execute(
        select(ExtractedContact.email_source).distinct().where(ExtractedContact.email_source != None)
    )
    sources = [r[0] for r in sources_r.all()]

    projects_r = await session.execute(select(Project.id, Project.name).where(user_filter))
    projects = [{"id": pid, "name": pname} for pid, pname in projects_r.all()]

    return {
        "statuses": ["new"],
        "sources": sources,
        "segments": [],
        "geos": [],
        "projects": projects,
    }


@router.get("/projects/names")
async def project_names(
    session: AsyncSession = Depends(get_session),
    user: MCPUser = Depends(get_optional_user),
):
    """Project names for dropdown — same contract as main app."""
    q = select(Project.id, Project.name).where(Project.is_active == True)
    if user:
        q = q.where(Project.user_id == user.id)
    result = await session.execute(q)
    return [{"id": pid, "name": pname} for pid, pname in result.all()]


@router.get("/projects/list")
async def project_list(
    session: AsyncSession = Depends(get_session),
    user: MCPUser = Depends(get_optional_user),
):
    """Full project list — same contract as main app."""
    q = select(Project).where(Project.is_active == True)
    if user:
        q = q.where(Project.user_id == user.id)
    result = await session.execute(q)
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
async def list_campaigns(
    session: AsyncSession = Depends(get_session),
    user: MCPUser = Depends(get_optional_user),
):
    """Campaign list for CRM filters — wrapped in {campaigns:[]} as main app expects."""
    q = select(Campaign).order_by(Campaign.name)
    if user:
        up = await session.execute(select(Project.id).where(Project.user_id == user.id))
        pids = [pid for (pid,) in up.all()]
        if pids:
            q = q.where(Campaign.project_id.in_(pids))
        else:
            return {"campaigns": []}
    result = await session.execute(q)
    campaigns = result.scalars().all()
    return {
        "campaigns": [
            {"id": str(c.id), "name": c.name, "source": c.platform, "message_count": c.leads_count or 0}
            for c in campaigns
        ]
    }


@router.get("/{contact_id}")
async def get_contact(
    contact_id: int,
    session: AsyncSession = Depends(get_session),
    user: MCPUser = Depends(get_optional_user),
):
    """Single contact detail — user-scoped."""
    contact = await session.get(ExtractedContact, contact_id)
    if not contact:
        from fastapi import HTTPException
        raise HTTPException(404, "Contact not found")

    # User-scope check
    if user and contact.project_id:
        project = await session.get(Project, contact.project_id)
        if project and project.user_id != user.id:
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
    user: MCPUser = Depends(get_optional_user),
):
    """Contact conversation history — shows planned sequence steps + any replies.

    The @main CRM contact detail uses this to show conversation tab.
    For MCP contacts: shows the generated sequence that will be/was sent.
    """
    from app.models.campaign import GeneratedSequence

    contact = await session.get(ExtractedContact, contact_id)
    if not contact:
        return {"email_history": [], "linkedin_history": [], "inbox_links": {}, "planned_sequence": []}

    # User-scope
    if user and contact.project_id:
        project = await session.get(Project, contact.project_id)
        if project and project.user_id != user.id:
            return {"email_history": [], "linkedin_history": [], "inbox_links": {}, "planned_sequence": []}

    # Get the sequence for this contact's project
    planned_steps = []
    seq_result = await session.execute(
        select(GeneratedSequence).where(
            GeneratedSequence.project_id == contact.project_id,
        ).order_by(GeneratedSequence.created_at.desc()).limit(1)
    )
    seq = seq_result.scalar_one_or_none()
    if seq and seq.sequence_steps:
        steps = seq.sequence_steps
        if isinstance(steps, list):
            for step in steps:
                # Substitute merge tags with contact's actual data
                subject = step.get("subject", "")
                body = step.get("body", "")
                if contact.first_name:
                    subject = subject.replace("{{first_name}}", contact.first_name)
                    body = body.replace("{{first_name}}", contact.first_name)
                if contact.source_data and contact.source_data.get("company_name"):
                    company = contact.source_data["company_name"]
                    subject = subject.replace("{{company}}", company)
                    body = body.replace("{{company}}", company)

                # Get city from discovered company
                if contact.discovered_company_id:
                    dc = await session.get(DiscoveredCompany, contact.discovered_company_id)
                    if dc and dc.city:
                        subject = subject.replace("{{city}}", dc.city)
                        body = body.replace("{{city}}", dc.city)

                planned_steps.append({
                    "step": step.get("step", 0),
                    "day": step.get("day", 0),
                    "subject": subject,
                    "body": body,
                    "type": "planned",
                })

    # Get reply data from source_data (if analyzed)
    email_history = []
    sd = contact.source_data or {}
    if sd.get("has_replied"):
        email_history.append({
            "direction": "inbound",
            "body": sd.get("reply_text_preview", ""),
            "category": sd.get("reply_category", ""),
            "received_at": sd.get("reply_time", ""),
            "campaign": sd.get("reply_campaign", ""),
        })

    # SmartLead campaign link
    inbox_links = {}
    if sd.get("campaign_id"):
        inbox_links["smartlead"] = f"https://app.smartlead.ai/app/email-campaigns-v2/{sd['campaign_id']}/analytics"

    return {
        "email_history": email_history,
        "linkedin_history": [],
        "inbox_links": inbox_links,
        "planned_sequence": planned_steps,
        "sequence_name": seq.campaign_name if seq else None,
        "sequence_status": seq.status if seq else None,
    }
