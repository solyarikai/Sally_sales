"""
CRM Contacts API endpoints
Simple flat table with filters - project, segment, status, source
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Body, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, String, text as sql_text, desc
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, EmailStr, field_validator, model_validator
from datetime import datetime
import csv
import io
import re
import asyncio
import logging
import os
import httpx

from app.db import get_session
from app.models.contact import Contact, Project, ContactActivity
from app.utils.normalization import normalize_name
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


class ContactResponse(BaseModel):
    """Clean API contract. No deprecated DB internals leak here."""
    id: int
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company_name: Optional[str] = None
    domain: Optional[str] = None
    job_title: Optional[str] = None
    segment: Optional[str] = None
    suitable_for: Optional[List[str]] = None
    geo: Optional[str] = None
    project_id: Optional[int] = None
    project_name: Optional[str] = None
    source: str
    source_id: Optional[str] = None
    status: str
    status_external: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    smartlead_id: Optional[str] = None
    getsales_id: Optional[str] = None
    # Canonical funnel
    last_reply_at: Optional[datetime] = None
    has_replied: Optional[bool] = None
    needs_followup: Optional[bool] = None
    # Reply classification (enriched from ProcessedReply)
    latest_reply_category: Optional[str] = None
    latest_reply_confidence: Optional[str] = None
    # Canonical data
    provenance: Optional[Dict[str, Any]] = None
    platform_state: Optional[Dict[str, Any]] = None
    campaigns: Optional[List[Dict[str, Any]]] = None
    # Timestamps
    created_at: datetime
    updated_at: datetime

    @field_validator('has_replied', mode='before')
    @classmethod
    def compute_has_replied(cls, v, info):
        if info.data.get('last_reply_at') is not None:
            return True
        return bool(v)

    @staticmethod
    def _decode_unicode_escapes(s: str) -> str:
        """Decode broken unicode escapes like 'u0411u0438' → 'Би'."""
        import re
        return re.sub(r'u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), s)

    @model_validator(mode='after')
    def derive_campaigns(self):
        """Derive campaigns list from platform_state since the campaigns column was dropped.
        Uses model_validator instead of field_validator because Pydantic v2 skips
        field validators when the ORM object lacks the attribute entirely."""
        if self.campaigns:
            return self
        if not isinstance(self.platform_state, dict):
            return self
        seen = {}  # deduplicate by campaign id
        for plat_name, plat_data in self.platform_state.items():
            if isinstance(plat_data, dict):
                for camp in plat_data.get("campaigns", []):
                    if isinstance(camp, dict):
                        camp_copy = dict(camp)
                        # Normalize legacy keys (campaign_name/campaign_id → name/id)
                        if "name" not in camp_copy and "campaign_name" in camp_copy:
                            camp_copy["name"] = camp_copy.pop("campaign_name")
                        if "id" not in camp_copy and "campaign_id" in camp_copy:
                            camp_copy["id"] = camp_copy.pop("campaign_id")
                        # Fix broken unicode escapes in campaign name
                        if camp_copy.get("name") and "u0" in camp_copy["name"]:
                            camp_copy["name"] = self._decode_unicode_escapes(camp_copy["name"])
                        camp_copy.setdefault("source", plat_name)
                        # Deduplicate: keep the entry with a proper name
                        cid = camp_copy.get("id")
                        if cid:
                            if cid not in seen:
                                seen[cid] = camp_copy
                            else:
                                # prefer entry with decoded (non-escape) name
                                existing = seen[cid]
                                if "u0" in (existing.get("name") or ""):
                                    seen[cid] = camp_copy
                        else:
                            seen[id(camp_copy)] = camp_copy
        result = list(seen.values())
        self.campaigns = result or None
        return self

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
    campaign_ownership_rules: Optional[Dict[str, Any]] = None
    telegram_chat_id: Optional[str] = None  # Resolved chat ID (set automatically)
    telegram_username: Optional[str] = None  # Operator @username for notifications
    webhooks_enabled: Optional[bool] = None
    sheet_sync_config: Optional[Dict[str, Any]] = None
    sender_name: Optional[str] = None
    sender_position: Optional[str] = None
    sender_company: Optional[str] = None
    reply_prompt_template_id: Optional[int] = None
    sdr_email: Optional[str] = None  # SDR email for test campaign notifications


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    target_industries: Optional[str] = None
    target_segments: Optional[str] = None
    campaign_filters: Optional[List[str]] = None
    campaign_ownership_rules: Optional[Dict[str, Any]] = None
    telegram_chat_id: Optional[str] = None
    telegram_username: Optional[str] = None
    webhooks_enabled: bool = True
    sheet_sync_config: Optional[Dict[str, Any]] = None
    sender_name: Optional[str] = None
    sender_position: Optional[str] = None
    sender_company: Optional[str] = None
    reply_prompt_template_id: Optional[int] = None
    external_status_config: Optional[Dict[str, Any]] = None
    sdr_email: Optional[str] = None
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

CONTACT_STATUSES = ["new", "contacted", "replied", "calendly_sent", "meeting_booked", "meeting_held", "qualified", "not_qualified"]
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
    domain: Optional[str] = None,
    suitable_for: Optional[str] = None,
    reply_category: Optional[str] = None,
    reply_since: Optional[str] = None,
    status_external: Optional[str] = None,
    source_id: Optional[str] = None,
    is_qualified: Optional[bool] = None,
):
    """Build a filtered Contact query. Shared by list, CSV export, and Google Sheet export."""
    query = select(Contact).where(
        and_(
            Contact.company_id == company_id if company_id else True,
            Contact.deleted_at.is_(None)
        )
    )

    if project_id:
        # Простая фильтрация по project_id — быстро и надёжно
        query = query.where(Contact.project_id == project_id)

    if segment:
        segments_list = [s.strip() for s in segment.split(',') if s.strip()]
        # Expand snake_case keys to also match display names (e.g. family_office → Family Office)
        expanded = set(segments_list)
        for s in segments_list:
            if '_' in s:
                expanded.add(s.replace('_', ' ').title())  # family_office → Family Office
            expanded.add(s)  # keep original
        all_variants = list(expanded)
        if len(all_variants) == 1:
            query = query.where(func.lower(Contact.segment) == all_variants[0].lower())
        else:
            query = query.where(func.lower(Contact.segment).in_([v.lower() for v in all_variants]))
    if geo:
        # Map country names to 2-letter codes used in contacts (Russia→RU, etc.)
        _COUNTRY_TO_GEO = {
            "russia": "RU", "uae": "AE", "turkey": "TR", "cyprus": "CY",
            "thailand": "TH", "montenegro": "ME", "spain": "ES", "greece": "GR",
            "uk": "UK", "israel": "IL", "italy": "IT", "switzerland": "CH",
            "singapore": "SG", "estonia": "EE", "georgia": "GE", "serbia": "RS",
            "portugal": "PT", "indonesia": "ID", "malta": "MT",
        }
        geo_val = _COUNTRY_TO_GEO.get(geo.lower(), geo)
        query = query.where(Contact.geo == geo_val)
    if status:
        statuses = [s.strip() for s in status.split(',') if s.strip()]
        if len(statuses) == 1:
            query = query.where(Contact.status == statuses[0])
        elif len(statuses) > 1:
            query = query.where(Contact.status.in_(statuses))
    if source:
        query = query.where(Contact.source == source)
    if source_id:
        query = query.where(Contact.source_id == source_id)
    if has_replied is not None:
        if has_replied:
            query = query.where(Contact.last_reply_at.isnot(None))
        else:
            query = query.where(Contact.last_reply_at.is_(None))
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
                sql_text("contacts.platform_state::text LIKE :cid_0")
                .bindparams(cid_0=f"%{ids[0]}%")
            )
        else:
            cid_parts = " OR ".join(f"contacts.platform_state::text LIKE :cid_{i}" for i in range(len(ids)))
            cid_params = {f"cid_{i}": f"%{v}%" for i, v in enumerate(ids)}
            query = query.where(sql_text(f"({cid_parts})").bindparams(**cid_params))
    elif campaign and not source_id:
        # Skip campaign filter when source_id is explicit — source_id already identifies the contacts
        names = [n.strip() for n in campaign.split(',') if n.strip()]
        if len(names) == 1:
            query = query.where(
                sql_text("contacts.platform_state::text ILIKE :camp_0")
                .bindparams(camp_0=f"%{names[0]}%")
            )
        elif len(names) > 1:
            camp_parts = " OR ".join(f"contacts.platform_state::text ILIKE :camp_{i}" for i in range(len(names)))
            camp_params = {f"camp_{i}": f"%{n}%" for i, n in enumerate(names)}
            query = query.where(sql_text(f"({camp_parts})").bindparams(**camp_params))
    if needs_followup is True:
        from datetime import timedelta
        three_days_ago = datetime.utcnow() - timedelta(days=3)
        query = query.where(
            and_(
                Contact.last_reply_at.is_(None),
                Contact.created_at < three_days_ago
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
    if domain:
        domain_list = [d.strip().lower() for d in domain.split(',') if d.strip()]
        if len(domain_list) == 1:
            query = query.where(func.lower(Contact.domain) == domain_list[0])
        elif domain_list:
            query = query.where(func.lower(Contact.domain).in_(domain_list))
    if suitable_for:
        # suitable_for is a JSON array column; filter contacts where the array contains the value
        query = query.where(
            sql_text("contacts.suitable_for::jsonb @> :sf_val::jsonb")
            .bindparams(sf_val=f'["{suitable_for}"]')
        )
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
    if reply_category:
        from app.models.reply import ProcessedReply
        cats = [c.strip() for c in reply_category.split(',') if c.strip()]
        # Subquery: leads with matching reply category (optionally time-bounded)
        cat_filter = [ProcessedReply.category.in_(cats)]
        if reply_since:
            try:
                since_dt = datetime.fromisoformat(reply_since)
                cat_filter.append(ProcessedReply.received_at >= since_dt)
            except ValueError:
                pass
        latest_cat = (
            select(ProcessedReply.lead_email)
            .distinct(ProcessedReply.lead_email)
            .where(and_(*cat_filter))
            .order_by(ProcessedReply.lead_email, desc(ProcessedReply.received_at))
        ).subquery()
        query = query.where(Contact.email.in_(select(latest_cat.c.lead_email)))

    if status_external:
        ext_list = [s.strip() for s in status_external.split(',') if s.strip()]
        if len(ext_list) == 1:
            query = query.where(Contact.status_external == ext_list[0])
        elif ext_list:
            query = query.where(Contact.status_external.in_(ext_list))

    if is_qualified is True:
        # Filter contacts that have at least one qualified (warm) ProcessedReply
        from app.models.reply import ProcessedReply
        qualified_emails = (
            select(ProcessedReply.lead_email)
            .distinct(ProcessedReply.lead_email)
            .where(ProcessedReply.is_qualified == True)
        ).subquery()
        query = query.where(Contact.email.in_(select(qualified_emails.c.lead_email)))

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
    domain: Optional[str] = Query(None, description="Filter by domain(s), comma-separated"),
    suitable_for: Optional[str] = Query(None, description="Filter by suitable_for project name"),
    reply_category: Optional[str] = Query(None, description="Filter by latest reply category (comma-separated)"),
    reply_since: Optional[str] = Query(None, description="Only include replies received after this date (ISO format)"),
    status_external: Optional[str] = Query(None, description="Filter by external status (comma-separated)"),
    source_id: Optional[str] = Query(None, description="Filter by source_id (e.g., clay_123 for gather run)"),
    is_qualified: Optional[bool] = Query(None, description="Filter warm/qualified leads (from ProcessedReply.is_qualified)"),
    session: AsyncSession = Depends(get_session),
    company_id: int | None = Depends(get_optional_company_id),
):
    """Get paginated list of contacts with filters"""
    if source_id and source_id.startswith("clay_"):
        logger.info(f"[CONTACTS_DEBUG] source_id={source_id} project_id={project_id} campaign={campaign} campaign_id={campaign_id}")
    query = await _build_filtered_query(
        session, company_id,
        project_id=project_id, segment=segment, geo=geo, status=status, source=source,
        has_replied=has_replied, has_smartlead=has_smartlead, has_getsales=has_getsales,
        campaign=campaign, campaign_id=campaign_id, needs_followup=needs_followup,
        created_after=created_after, created_before=created_before, search=search,
        domain=domain, suitable_for=suitable_for, reply_category=reply_category,
        reply_since=reply_since, status_external=status_external, source_id=source_id,
        is_qualified=is_qualified,
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
    
    # Enrich with latest reply category
    contact_emails = [c.email for c in contacts if c.email]
    reply_cat_map: dict[str, tuple[str | None, str | None]] = {}
    if contact_emails:
        from app.models.reply import ProcessedReply
        latest_reply_sub = (
            select(
                ProcessedReply.lead_email,
                ProcessedReply.category,
                ProcessedReply.category_confidence,
            )
            .distinct(ProcessedReply.lead_email)
            .where(ProcessedReply.lead_email.in_(contact_emails))
            .order_by(ProcessedReply.lead_email, desc(ProcessedReply.received_at))
        ).subquery()
        cat_result = await session.execute(select(latest_reply_sub))
        for row in cat_result.all():
            reply_cat_map[row[0]] = (row[1], row[2])

    # Build response
    contact_responses = []
    for contact in contacts:
        response = ContactResponse.model_validate(contact)
        if contact.project_id:
            response.project_name = project_names.get(contact.project_id)
        cat_info = reply_cat_map.get(contact.email)
        if cat_info:
            response.latest_reply_category = cat_info[0]
            response.latest_reply_confidence = cat_info[1]
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
    project_id: int | None = Query(None),
):
    """Get contact statistics, optionally filtered by project."""

    filters = [Contact.deleted_at.is_(None)]
    if company_id:
        filters.append(Contact.company_id == company_id)
    if project_id:
        filters.append(Contact.project_id == project_id)
    base_filter = and_(*filters)
    
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
    source: Optional[str] = Query(None, description="Filter by source/platform: smartlead or getsales"),
):
    """Get list of unique campaign names from campaigns table (fast, indexed)."""
    from app.models.campaign import Campaign

    query = select(Campaign.name, Campaign.platform).where(
        Campaign.name.isnot(None),
        Campaign.name != "",
    )
    if source:
        query = query.where(Campaign.platform == source)
    query = query.distinct().order_by(Campaign.name)

    result = await session.execute(query)
    campaigns = [
        {"name": name, "source": platform}
        for name, platform in result.all()
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
    
    data = contact.model_dump(exclude_none=False)
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
                        sql_text("contacts.platform_state::text ILIKE :cid").bindparams(cid=f"%{cid}%"),
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
                        # Normalize name fields
                        if field in ('first_name', 'last_name'):
                            value = normalize_name(value) or value
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


class EnrichResult(BaseModel):
    """Result of CSV enrich operation."""
    success: bool
    total_rows: int
    enriched: int
    skipped: int
    not_found: int
    errors: List[str]


@router.post("/enrich/csv", response_model=EnrichResult)
async def enrich_contacts_csv(
    file: UploadFile = File(...),
    project_id: Optional[int] = Query(None, description="Only enrich contacts in this project"),
    session: AsyncSession = Depends(get_session),
    company_id: int | None = Depends(get_optional_company_id),
):
    """
    Enrich existing contacts from a CSV file.

    Matches contacts by email (case-insensitive) and fills in empty fields only.
    Never overwrites existing data.

    Supported CSV columns (same aliases as import):
    - email (required, used for matching)
    - first_name, last_name, company, job_title, phone, linkedin_url, location, notes
    """
    if not file.filename or not file.filename.lower().endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    try:
        content = await file.read()
        text_content = content.decode('utf-8-sig')
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")

    try:
        reader = csv.DictReader(io.StringIO(text_content))
        rows = list(reader)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {str(e)}")

    if not rows:
        raise HTTPException(status_code=400, detail="CSV file is empty")

    # Same column mapping as import
    column_mapping = {
        'email': ['email', 'e-mail', 'email_address', 'emailaddress'],
        'first_name': ['first_name', 'firstname', 'first name', 'first'],
        'last_name': ['last_name', 'lastname', 'last name', 'last', 'surname'],
        'company_name': ['company', 'company_name', 'companyname', 'organization', 'org'],
        'domain': ['domain', 'website', 'company_domain'],
        'job_title': ['job_title', 'jobtitle', 'title', 'position', 'role'],
        'phone': ['phone', 'phone_number', 'phonenumber', 'mobile', 'tel'],
        'linkedin_url': ['linkedin_url', 'linkedin', 'linkedin_profile', 'linkedinurl'],
        'location': ['location', 'city', 'country', 'region', 'address'],
        'notes': ['notes', 'note', 'comments', 'comment'],
    }

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

    enrichable_fields = ['first_name', 'last_name', 'company_name', 'domain', 'job_title', 'phone', 'linkedin_url', 'location', 'notes']
    csv_fields = [f for f in enrichable_fields if f in field_to_csv_col]

    if not csv_fields:
        raise HTTPException(
            status_code=400,
            detail="CSV has no enrichable columns besides email. Need at least one of: first_name, last_name, company, job_title, phone, linkedin_url, location, notes"
        )

    logger.info(f"CSV enrich: {len(rows)} rows, fields to enrich: {csv_fields}")

    enriched = 0
    skipped = 0
    not_found = 0
    errors = []

    for idx, row in enumerate(rows, start=2):
        try:
            email_col = field_to_csv_col['email']
            email = row.get(email_col, '').strip().lower()

            if not email:
                errors.append(f"Row {idx}: Empty email")
                continue

            if not validate_email(email):
                errors.append(f"Row {idx}: Invalid email '{email}'")
                continue

            # Find existing contact by email
            conditions = [
                func.lower(Contact.email) == email,
                Contact.deleted_at.is_(None),
            ]
            if company_id:
                conditions.append(Contact.company_id == company_id)
            if project_id:
                conditions.append(Contact.project_id == project_id)

            result = await session.execute(
                select(Contact).where(and_(*conditions)).limit(1)
            )
            contact = result.scalar_one_or_none()

            if not contact:
                not_found += 1
                continue

            # Enrich: fill only empty fields
            updated = False
            for field in csv_fields:
                csv_col = field_to_csv_col[field]
                csv_value = row.get(csv_col, '').strip()
                if not csv_value:
                    continue
                # Normalize name fields
                if field in ('first_name', 'last_name'):
                    csv_value = normalize_name(csv_value) or csv_value
                current_value = getattr(contact, field, None)
                if not current_value:
                    setattr(contact, field, csv_value)
                    updated = True

            if updated:
                enriched += 1
            else:
                skipped += 1

        except Exception as e:
            errors.append(f"Row {idx}: {str(e)}")
            if len(errors) > 100:
                errors.append("... (more errors truncated)")
                break

    await session.commit()

    logger.info(f"CSV enrich complete: {enriched} enriched, {skipped} skipped, {not_found} not found, {len(errors)} errors")

    return EnrichResult(
        success=enriched > 0,
        total_rows=len(rows),
        enriched=enriched,
        skipped=skipped,
        not_found=not_found,
        errors=errors[:20],
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


def _format_platform_campaigns(platform_state) -> str:
    """Extract and format campaign names from platform_state JSON."""
    if not isinstance(platform_state, dict):
        return ""
    names = []
    for plat_data in platform_state.values():
        if not isinstance(plat_data, dict):
            continue
        for camp in plat_data.get("campaigns", []):
            if isinstance(camp, dict):
                name = camp.get("name", "")
                if name:
                    names.append(name)
            elif isinstance(camp, str) and camp:
                names.append(camp)
    return ", ".join(names)


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
                row[col] = _format_platform_campaigns(c.platform_state)
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
                row.append(_format_platform_campaigns(c.platform_state))
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


# ============= SmartLead Sequence Generation =============

# Inxy context for sequence generation — based on top-performing campaigns (10-21% reply rate)
_INXY_CONTEXT = """
INXY is a crypto payment infrastructure company. Core services:
1. Paygate — accept crypto payments, settle in fiat (EUR/USD) directly to legal entity
2. Payout — mass crypto payouts to contractors/partners worldwide (SWIFT/Wise alternative, 3-5% cheaper)
3. OTC — crypto-to-fiat exchange for businesses

Key differentiators: 30% below market rates, EU-licensed (Polish VASP + Canadian MSB),
host2host API integration in 1-2 days, processed $2B+ in 2025, KYT compliance.

Case studies: WowVendor (gaming, +15% revenue via Polygon/Ton/Tron), Solar Staff (automated freelancer payouts),
servers.com (0.5% processing fees).

Top-performing email patterns (10-21% reply rates):
- Short, direct emails (3-4 sentences max)
- Step 1: specific value prop for their segment + ask for call
- Step 2: different angle (e.g. if Step 1 was about accepting payments, Step 2 is about payouts) + case study
- Step 3: "start as a backup" reframe + gentle breakup
- Sign as "Serge Kuznetsov, Co-founder @ INXY.io"
- Use {{first_name}} for personalization
- HTML with <p> tags only, no fancy formatting
"""


async def _generate_outreach_sequence(project_name: str, segment_name: str) -> list:
    """Generate a 3-step email outreach sequence using Claude, tailored to project and segment."""
    import anthropic
    import json

    try:
        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        prompt = (
            f"{_INXY_CONTEXT}\n\n"
            f"Generate a 3-step cold email sequence for INXY targeting: {segment_name or 'B2B companies'}\n"
            f"Project context: {project_name}\n\n"
            f"Requirements:\n"
            f"- Step 1: Initial outreach (delay 0 days). Tailored to {segment_name} — explain how crypto payouts "
            f"can help them pay contractors/partners cheaper and faster. Short subject line.\n"
            f"- Step 2: Follow-up (delay 4 days). Subject starts with 'Re: ' of step 1. "
            f"Different angle — mention a relevant case study or the compliance advantage.\n"
            f"- Step 3: Breakup (delay 5 days). Subject starts with 'Re: Re: ' of step 1. "
            f"'Start as a backup' reframe, offer one-pager, gentle close.\n"
            f"- Use {{{{first_name}}}} and {{{{company_name}}}} variables. Include {{{{company_name}}}} in the Step 1 subject line.\n"
            f"- HTML <p> tags, sign as Serge Kuznetsov, Co-founder @ INXY.io\n"
            f"- Each email: 3-4 sentences MAX. No fluff.\n\n"
            f"Return ONLY a JSON array of 3 objects: {{\"seq_number\": N, \"subject\": \"...\", \"email_body\": \"<p>...</p>\"}}\n"
        )

        resp = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text
        # Extract JSON from response (may be wrapped in ```json blocks)
        if "```" in text:
            text = text.split("```json")[-1].split("```")[0] if "```json" in text else text.split("```")[1].split("```")[0]
        raw = json.loads(text.strip())
        steps = raw if isinstance(raw, list) else raw.get("sequences", raw.get("steps", []))

        sequences = []
        for i, step in enumerate(steps[:3], 1):
            sequences.append({
                "seq_number": i,
                "seq_delay_details": {"delay_in_days": [0, 4, 5][i - 1]},
                "subject": step.get("subject", f"Follow-up #{i}"),
                "email_body": step.get("email_body", step.get("body", "")),
            })
        logger.info(f"[SEQUENCE] Claude generated {len(sequences)} steps for '{segment_name}'")
        return sequences
    except Exception as e:
        logger.warning(f"Claude sequence generation failed: {e}, using Inxy fallback")
        fn = "{{first_name}}"
        seg = segment_name or "your industry"
        return [
            {
                "seq_number": 1,
                "seq_delay_details": {"delay_in_days": 0},
                "subject": f"crypto payouts for {{{{company_name}}}}",
                "email_body": (
                    f"<p>Hi {fn},</p>"
                    f"<p>We help {seg} companies pay contractors and partners worldwide using crypto rails "
                    f"— settling in EUR/USD directly to your legal entity, 30% cheaper than SWIFT or Wise.</p>"
                    f"<p>Integration takes 1-2 days via API. Would a quick 15-min call make sense to see if there's a fit?</p>"
                    f"<p>Serge Kuznetsov<br/>Co-founder @ INXY.io</p>"
                ),
            },
            {
                "seq_number": 2,
                "seq_delay_details": {"delay_in_days": 4},
                "subject": f"Re: crypto payouts for {{{{company_name}}}}",
                "email_body": (
                    f"<p>Hi {fn},</p>"
                    f"<p>Quick follow-up. Solar Staff used our payout infrastructure to automate payments "
                    f"to 50K+ international freelancers — cutting processing costs by 30%.</p>"
                    f"<p>We're EU-licensed (Polish VASP + Canadian MSB), so compliance is handled. "
                    f"Happy to send a one-pager with the details.</p>"
                    f"<p>Serge</p>"
                ),
            },
            {
                "seq_number": 3,
                "seq_delay_details": {"delay_in_days": 5},
                "subject": f"Re: Re: crypto payouts for {{{{company_name}}}}",
                "email_body": (
                    f"<p>Hi {fn},</p>"
                    f"<p>Last note — no worries if now isn't the right time. Many of our clients started INXY "
                    f"as a backup payment rail alongside their existing setup, zero commitment.</p>"
                    f"<p>If the topic of cheaper international payouts comes up — I'm here.</p>"
                    f"<p>Best,<br/>Serge</p>"
                ),
            },
        ]


# ============= SmartLead Draft Campaign =============

class PushToSmartleadRequest(BaseModel):
    contact_ids: List[int] = []
    campaign_name: Optional[str] = None
    # Filter-based push: when contact_ids is empty, use these to select all matching contacts
    source_id: Optional[str] = None
    project_id: Optional[int] = None


@router.post("/push-to-smartlead")
async def push_contacts_to_smartlead(
    body: PushToSmartleadRequest = Body(...),
    session: AsyncSession = Depends(get_session),
    company_id: int | None = Depends(get_optional_company_id),
):
    """Create a draft SmartLead campaign from selected contacts and add them as leads.

    Accepts contact_ids OR source_id+project_id to push all matching contacts.
    Returns campaign ID, name, and link.
    """
    if not smartlead_service.is_connected():
        raise HTTPException(status_code=400, detail="SmartLead API key not configured")

    # Fetch contacts — by IDs or by filter
    if body.contact_ids:
        result = await session.execute(
            select(Contact).where(Contact.id.in_(body.contact_ids))
        )
    elif body.source_id:
        q = select(Contact).where(
            Contact.source_id == body.source_id,
            Contact.deleted_at.is_(None),
            Contact.email.isnot(None),
        )
        if body.project_id:
            q = q.where(Contact.project_id == body.project_id)
        result = await session.execute(q)
    else:
        raise HTTPException(status_code=400, detail="Provide contact_ids or source_id")

    contacts_list = list(result.scalars().all())

    if not contacts_list:
        raise HTTPException(status_code=400, detail="No contacts found for given IDs")

    # Filter contacts with valid emails
    valid_contacts = [c for c in contacts_list if c.email and "@" in c.email]
    if not valid_contacts:
        raise HTTPException(status_code=400, detail="No contacts with valid emails")

    # Build campaign name: Project — Segment — Date (N leads)
    ts = datetime.utcnow().strftime("%m/%d")
    if body.campaign_name:
        campaign_name = body.campaign_name
    else:
        # Derive project name and segment from contacts
        project_name = ""
        segment_name = ""
        sample = valid_contacts[0]
        if sample.project_id:
            proj = await session.execute(
                select(Project.name).where(Project.id == sample.project_id)
            )
            project_name = proj.scalar_one_or_none() or ""
        segment_raw = sample.segment or ""
        # Truncate segment: take only the part before parentheses/hash, max 40 chars
        segment_name = segment_raw.split("(")[0].split("#")[0].strip()[:40].strip()
        parts = [p for p in [project_name, segment_name] if p]
        prefix = " — ".join(parts) if parts else "Draft"
        campaign_name = f"{prefix} {ts} ({len(valid_contacts)} leads)"

    # Create campaign in SmartLead
    try:
        campaign_result = await smartlead_service.create_campaign(campaign_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create SmartLead campaign: {e}")

    campaign_id = campaign_result["id"]

    # Generate and set email sequence for the campaign
    try:
        project_name = ""
        segment_name = ""
        if valid_contacts[0].project_id:
            proj_row = await session.execute(
                select(Project).where(Project.id == valid_contacts[0].project_id)
            )
            proj_obj = proj_row.scalar_one_or_none()
            if proj_obj:
                project_name = proj_obj.name or ""
        segment_name = (valid_contacts[0].segment or "").split("#")[0].strip()

        logger.info(f"[SEQUENCE] Generating for campaign {campaign_id}: project={project_name}, segment={segment_name}")
        sequences = await _generate_outreach_sequence(project_name, segment_name)
        logger.info(f"[SEQUENCE] Got {len(sequences)} steps for campaign {campaign_id}")
        if sequences:
            result = await smartlead_service.set_campaign_sequences(campaign_id, sequences)
            logger.info(f"[SEQUENCE] Set result for campaign {campaign_id}: {result}")
    except Exception as e:
        logger.warning(f"Failed to generate sequence for campaign {campaign_id}: {e}")

    # Format leads for SmartLead
    leads = []
    for c in valid_contacts:
        lead = {
            "email": c.email,
            "first_name": c.first_name or "",
            "last_name": c.last_name or "",
        }
        if c.company_name:
            lead["company_name"] = c.company_name
        if c.domain:
            lead["website"] = c.domain if c.domain.startswith("http") else f"https://{c.domain}"
        custom_fields = {}
        if c.job_title:
            custom_fields["job_title"] = c.job_title
        if c.linkedin_url:
            custom_fields["linkedin_url"] = c.linkedin_url
        if c.phone:
            custom_fields["phone"] = c.phone
        if c.location:
            custom_fields["location"] = c.location
        if c.segment:
            custom_fields["segment"] = c.segment
        if custom_fields:
            lead["custom_fields"] = custom_fields
        leads.append(lead)

    # Add leads to campaign
    add_result = await smartlead_service.add_leads_to_campaign(campaign_id, leads)

    if not add_result.get("success"):
        logger.error(f"Failed to add leads to campaign {campaign_id}: {add_result.get('error')}")
        # Campaign was created but leads failed — still return the campaign link
        return {
            "campaign_id": campaign_id,
            "campaign_name": campaign_name,
            "campaign_url": f"https://app.smartlead.ai/app/email-campaigns-v2/{campaign_id}/analytics",
            "leads_added": 0,
            "leads_total": len(valid_contacts),
            "error": add_result.get("error"),
        }

    # Update contacts' platform_state to track the campaign
    for c in valid_contacts:
        ps = dict(c.platform_state or {})
        sl = dict(ps.get("smartlead", {}))
        campaigns = list(sl.get("campaigns", []))
        campaigns.append({"id": campaign_id, "name": campaign_name})
        sl["campaigns"] = campaigns
        ps["smartlead"] = sl
        c.platform_state = ps
    await session.commit()

    return {
        "campaign_id": campaign_id,
        "campaign_name": campaign_name,
        "campaign_url": f"https://app.smartlead.ai/app/email-campaigns-v2/{campaign_id}/analytics",
        "leads_added": len(valid_contacts),
        "leads_total": len(valid_contacts),
    }


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
    """List all projects with contact counts (batch query — no N+1)."""

    result = await session.execute(
        select(Project)
        .where(and_(Project.company_id == company_id if company_id else True, Project.deleted_at.is_(None)))
        .order_by(Project.name)
    )
    projects = result.scalars().all()

    # Batch: get contact counts by project_id in a single query
    project_ids = [p.id for p in projects]
    counts_by_id: dict[int, int] = {}
    if project_ids:
        count_result = await session.execute(
            select(Contact.project_id, func.count(Contact.id))
            .where(and_(Contact.project_id.in_(project_ids), Contact.deleted_at.is_(None)))
            .group_by(Contact.project_id)
        )
        counts_by_id = dict(count_result.all())

    project_responses = []
    for project in projects:
        contact_count = counts_by_id.get(project.id, 0)

        response = ProjectResponse(
            id=project.id,
            name=project.name,
            description=project.description,
            target_industries=project.target_industries,
            target_segments=project.target_segments,
            campaign_filters=project.campaign_filters,
            campaign_ownership_rules=project.campaign_ownership_rules,
            telegram_chat_id=project.telegram_chat_id,
            webhooks_enabled=project.webhooks_enabled,
            sheet_sync_config=project.sheet_sync_config,
            sender_name=project.sender_name,
            sender_position=project.sender_position,
            sender_company=project.sender_company,
            reply_prompt_template_id=project.reply_prompt_template_id,
            sdr_email=project.sdr_email,
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
        campaign_ownership_rules=db_project.campaign_ownership_rules,
        telegram_chat_id=db_project.telegram_chat_id,
        webhooks_enabled=db_project.webhooks_enabled,
        sheet_sync_config=db_project.sheet_sync_config,
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

    # Contact count — use project_id index (fast)
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
        campaign_ownership_rules=project.campaign_ownership_rules,
        telegram_chat_id=project.telegram_chat_id,
        webhooks_enabled=project.webhooks_enabled,
        sheet_sync_config=project.sheet_sync_config,
        sender_name=project.sender_name,
        sender_position=project.sender_position,
        sender_company=project.sender_company,
        reply_prompt_template_id=project.reply_prompt_template_id,
        sdr_email=project.sdr_email,
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

    # Audit campaign_filters changes (manual adds/removes from UI)
    if "campaign_filters" in update_data and update_data["campaign_filters"] is not None:
        from app.models.campaign_audit_log import CampaignAuditLog
        old_filters = project.campaign_filters or []
        new_filters = update_data["campaign_filters"]
        old_set = {f.lower(): f for f in old_filters}
        new_set = {f.lower(): f for f in new_filters}
        for key in new_set:
            if key not in old_set:
                session.add(CampaignAuditLog(
                    project_id=project_id, action="add", campaign_name=new_set[key],
                    source="manual", details="Added via project settings UI",
                    campaigns_before=old_filters, campaigns_after=new_filters,
                ))
        for key in old_set:
            if key not in new_set:
                session.add(CampaignAuditLog(
                    project_id=project_id, action="remove", campaign_name=old_set[key],
                    source="manual", details="Removed via project settings UI",
                    campaigns_before=old_filters, campaigns_after=new_filters,
                ))

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
    
    # Refresh project prefix cache if ownership rules changed
    if "campaign_ownership_rules" in update_data:
        try:
            from app.services.crm_sync_service import refresh_project_prefixes
            await refresh_project_prefixes()
        except Exception:
            pass

    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        target_industries=project.target_industries,
        target_segments=project.target_segments,
        campaign_filters=project.campaign_filters,
        campaign_ownership_rules=project.campaign_ownership_rules,
        telegram_chat_id=project.telegram_chat_id,
        telegram_username=project.telegram_username,
        webhooks_enabled=project.webhooks_enabled,
        sheet_sync_config=project.sheet_sync_config,
        sender_name=project.sender_name,
        sender_position=project.sender_position,
        sender_company=project.sender_company,
        reply_prompt_template_id=project.reply_prompt_template_id,
        sdr_email=project.sdr_email,
        contact_count=contact_count,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


# ============= Sheet Sync Endpoints =============

@router.get("/projects/{project_id}/sheet-sync/status")
async def get_sheet_sync_status(
    project_id: int,
    session: AsyncSession = Depends(get_session),
    company_id: int | None = Depends(get_optional_company_id),
):
    """Get sheet sync config and status for a project."""
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

    config = project.sheet_sync_config or {}
    return {
        "configured": bool(config.get("sheet_id")),
        "enabled": config.get("enabled", False),
        "sheet_id": config.get("sheet_id"),
        "leads_tab": config.get("leads_tab"),
        "replies_tab": config.get("replies_tab", "Replies"),
        "last_replies_sync_at": config.get("last_replies_sync_at"),
        "last_leads_push_at": config.get("last_leads_push_at"),
        "last_qualification_poll_at": config.get("last_qualification_poll_at"),
        "replies_synced_count": config.get("replies_synced_count", 0),
        "leads_pushed_count": config.get("leads_pushed_count", 0),
        "last_error": config.get("last_error"),
        "last_error_at": config.get("last_error_at"),
    }


@router.post("/projects/{project_id}/sheet-sync/test")
async def test_sheet_connection(
    project_id: int,
    session: AsyncSession = Depends(get_session),
    company_id: int | None = Depends(get_optional_company_id),
):
    """Test Google Sheet connection — verify sheet is accessible and tabs match."""
    from app.services.google_sheets_service import google_sheets_service

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

    config = project.sheet_sync_config or {}
    sheet_id = config.get("sheet_id")
    if not sheet_id:
        raise HTTPException(status_code=400, detail="No sheet_id configured")

    if not google_sheets_service.is_configured():
        raise HTTPException(status_code=500, detail="Google Sheets service not configured")

    # Get sheet info
    info = google_sheets_service.get_sheet_info(sheet_id)
    if not info:
        raise HTTPException(
            status_code=400,
            detail="Cannot access sheet. Make sure it's shared with the service account.",
        )

    # Get tab info
    tabs = google_sheets_service.get_tab_info(sheet_id)
    tab_names = [t["name"] for t in tabs]

    leads_tab = config.get("leads_tab")
    replies_tab = config.get("replies_tab", "Replies")

    leads_ok = leads_tab in tab_names if leads_tab else False
    replies_ok = replies_tab in tab_names

    # Read headers if leads tab exists
    leads_headers = []
    if leads_ok:
        leads_headers = google_sheets_service.read_sheet_headers(sheet_id, leads_tab)

    return {
        "success": leads_ok and replies_ok,
        "sheet_title": info.get("title"),
        "tabs": tabs,
        "leads_tab_found": leads_ok,
        "replies_tab_found": replies_ok,
        "leads_headers": leads_headers,
        "service_account": google_sheets_service.get_service_account_email(),
    }


@router.post("/projects/{project_id}/sheet-sync/trigger")
async def trigger_sheet_sync(
    project_id: int,
    sync_type: str = Query(default="all", description="all, replies, leads, or qualification"),
    session: AsyncSession = Depends(get_session),
    company_id: int | None = Depends(get_optional_company_id),
):
    """Manually trigger sheet sync for a project."""
    from app.services.sheet_sync_service import sheet_sync_service

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

    config = project.sheet_sync_config or {}
    if not config.get("sheet_id"):
        raise HTTPException(status_code=400, detail="No sheet_id configured")

    results = {}

    if sync_type in ("all", "replies"):
        results["replies"] = await sheet_sync_service.sync_replies_to_sheet(project_id)

    if sync_type in ("all", "leads"):
        results["leads"] = await sheet_sync_service.push_leads_to_sheet(project_id)

    if sync_type in ("all", "qualification"):
        results["qualification"] = await sheet_sync_service.poll_qualification_from_sheet(project_id)

    return {"sync_type": sync_type, "results": results}


@router.post("/projects/{project_id}/sheet-sync/bootstrap-reference")
async def bootstrap_reference_data(
    project_id: int,
    session: AsyncSession = Depends(get_session),
    company_id: int | None = Depends(get_optional_company_id),
):
    """One-time: copy reference tab data to the replies tab for initial bootstrap."""
    from app.services.sheet_sync_service import sheet_sync_service

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

    config = project.sheet_sync_config or {}
    if not config.get("sheet_id"):
        raise HTTPException(status_code=400, detail="No sheet_id configured")
    if not config.get("reference_tab"):
        raise HTTPException(status_code=400, detail="No reference_tab configured")

    stats = await sheet_sync_service.copy_reference_to_tab(project_id)

    if stats["errors"]:
        raise HTTPException(status_code=400, detail=stats["errors"][0])

    return {"rows_copied": stats["rows_copied"]}


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


@router.get("/projects/{project_id}/gtm-data")
async def get_gtm_data(
    project_id: int,
    session: AsyncSession = Depends(get_session),
    company_id: int | None = Depends(get_optional_company_id),
):
    """Return real segment/industry stats from classified contacts for GTM dashboard."""
    from sqlalchemy import cast, JSON
    from collections import Counter

    # Verify project
    project_stmt = select(Project).where(
        Project.id == project_id, Project.deleted_at.is_(None),
    )
    if company_id:
        project_stmt = project_stmt.where(Project.company_id == company_id)
    project = (await session.execute(project_stmt)).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Fetch all non-deleted contacts for this project
    contacts_result = await session.execute(
        select(Contact).where(
            and_(Contact.project_id == project_id, Contact.deleted_at.is_(None))
        )
    )
    contacts = list(contacts_result.scalars().all())
    total = len(contacts)

    # Segment distribution
    segment_counts: Dict[str, int] = Counter()
    industry_counts: Dict[str, int] = Counter()
    keyword_counts: Dict[str, int] = Counter()
    suitable_for_counts: Dict[str, int] = Counter()
    status_by_segment: Dict[str, Dict[str, int]] = {}
    classified = 0
    unclassified = 0
    confidences: list[float] = []

    for c in contacts:
        seg = c.segment
        if seg:
            classified += 1
            segment_counts[seg] += 1
            # Status breakdown per segment
            status_by_segment.setdefault(seg, Counter())
            status_by_segment[seg][c.status or "lead"] += 1
        else:
            unclassified += 1

        # Extract industry/keywords from platform_state.classification
        ps = c.platform_state or {}
        cls_data = ps.get("classification", {})
        if cls_data:
            industry = cls_data.get("industry")
            if industry:
                industry_counts[industry] += 1
            for kw in cls_data.get("keywords", []):
                keyword_counts[kw] += 1
            conf = cls_data.get("confidence")
            if conf is not None:
                confidences.append(float(conf))

        # Cross-project suitability
        for target in (c.suitable_for or []):
            suitable_for_counts[target] += 1

    # Sort everything by count descending
    segments = [{"segment": k, "count": v} for k, v in segment_counts.most_common()]
    industries = [{"industry": k, "count": v} for k, v in industry_counts.most_common(20)]
    keywords = [{"keyword": k, "count": v} for k, v in keyword_counts.most_common(30)]
    cross_matches = [{"target": k, "count": v} for k, v in suitable_for_counts.most_common()]

    # Convert status_by_segment Counters to regular dicts
    status_breakdown = {seg: dict(counts) for seg, counts in status_by_segment.items()}

    return {
        "project_id": project_id,
        "project_name": project.name,
        "total_contacts": total,
        "classified": classified,
        "unclassified": unclassified,
        "avg_confidence": round(sum(confidences) / len(confidences), 2) if confidences else None,
        "segments": segments,
        "industries": industries,
        "top_keywords": keywords,
        "cross_project_matches": cross_matches,
        "status_by_segment": status_breakdown,
        "gtm_plan": project.gtm_plan,
    }


@router.get("/projects/{project_id}/segment-funnel")
async def get_segment_funnel(
    project_id: int,
    period: str = Query("all", pattern="^(7d|30d|90d|all)$"),
    session: AsyncSession = Depends(get_session),
    company_id: int | None = Depends(get_optional_company_id),
):
    """Segment funnel analytics derived from campaign names at query time."""
    from app.models.campaign import Campaign
    from app.models.reply import ProcessedReply
    from datetime import timedelta

    # Verify project
    project_stmt = select(Project).where(
        Project.id == project_id, Project.deleted_at.is_(None),
    )
    if company_id:
        project_stmt = project_stmt.where(Project.company_id == company_id)
    project = (await session.execute(project_stmt)).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Auto-derive segments from campaign names (shared utility)
    from app.utils.segment_extraction import build_segment_map, build_segment_case_when

    campaign_names_result = await session.execute(
        select(Campaign.name).where(
            Campaign.project_id == project_id,
            Campaign.name.isnot(None),
        )
    )
    raw_campaign_names = [r[0] for r in campaign_names_result.fetchall() if r[0]]
    segment_map = build_segment_map(raw_campaign_names, project.name)

    campaign_case = build_segment_case_when(segment_map, "c.name")
    reply_case = build_segment_case_when(segment_map, "pr.campaign_name")

    # Period cutoff
    cutoff = None
    if period != "all":
        days = {"7d": 7, "30d": 30, "90d": 90}[period]
        cutoff = datetime.utcnow() - timedelta(days=days)

    # Query 1: contacts per segment from campaigns table (fast — uses pre-computed leads_count)
    contacts_sql = f"""
        SELECT {campaign_case} as segment, SUM(COALESCE(c.leads_count, 0)) as total_contacts
        FROM campaigns c
        WHERE c.project_id = :pid AND c.name IS NOT NULL
        GROUP BY 1 ORDER BY total_contacts DESC
    """
    contacts_result = await session.execute(sql_text(contacts_sql), {"pid": project_id})
    contacts_rows = contacts_result.fetchall()

    # Query 2: reply funnel per segment with unique replied contacts
    reply_where = "c2.project_id = :pid AND pr.parent_reply_id IS NULL"
    reply_params: dict = {"pid": project_id}
    if cutoff:
        reply_where += " AND pr.received_at >= :cutoff"
        reply_params["cutoff"] = cutoff

    reply_sql = f"""
        SELECT {reply_case} as segment,
            COUNT(*) as total_replies,
            COUNT(DISTINCT pr.lead_email) as unique_replied,
            COUNT(*) FILTER (WHERE pr.category IN ('interested','meeting_request','question')) as positive,
            COUNT(*) FILTER (WHERE pr.category = 'meeting_request') as meeting_requests,
            COUNT(*) FILTER (WHERE pr.category = 'interested') as interested,
            COUNT(*) FILTER (WHERE pr.category = 'question') as questions,
            COUNT(*) FILTER (WHERE pr.category = 'not_interested') as not_interested,
            COUNT(*) FILTER (WHERE pr.category = 'out_of_office') as ooo
        FROM processed_replies pr
        JOIN contacts c2 ON LOWER(c2.email) = LOWER(pr.lead_email) AND c2.deleted_at IS NULL
        WHERE {reply_where}
        GROUP BY 1
    """
    reply_result = await session.execute(sql_text(reply_sql), reply_params)
    reply_rows = reply_result.fetchall()

    # Merge results
    reply_map = {}
    for row in reply_rows:
        reply_map[row.segment] = {
            "total_replies": row.total_replies,
            "unique_replied": row.unique_replied,
            "positive": row.positive,
            "meeting_requests": row.meeting_requests,
            "interested": row.interested,
            "questions": row.questions,
            "not_interested": row.not_interested,
            "ooo": row.ooo,
        }

    segments = []
    grand_contacts = 0
    grand_replies = 0
    grand_positive = 0
    grand_meetings = 0

    for row in contacts_rows:
        seg = row.segment
        tc = row.total_contacts or 0
        r = reply_map.pop(seg, {})
        ur = r.get("unique_replied", 0)
        # Ensure total_contacts >= unique_replied (some contacts may only exist in replies)
        tc = max(tc, ur)
        grand_contacts += tc
        tr = r.get("total_replies", 0)
        pos = r.get("positive", 0)
        mtg = r.get("meeting_requests", 0)
        grand_replies += tr
        grand_positive += pos
        grand_meetings += mtg
        segments.append({
            "segment": seg,
            "total_contacts": tc,
            "total_replies": tr,
            "unique_replied": ur,
            "positive": pos,
            "meeting_requests": mtg,
            "interested": r.get("interested", 0),
            "questions": r.get("questions", 0),
            "not_interested": r.get("not_interested", 0),
            "ooo": r.get("ooo", 0),
            "reply_rate": round(ur / tc * 100, 1) if tc else 0,
            "positive_rate": round(pos / ur * 100, 1) if ur else 0,
        })

    # Add segments that only appear in replies (no campaign match)
    for seg, r in reply_map.items():
        ur = r["unique_replied"]
        tr = r["total_replies"]
        pos = r["positive"]
        mtg = r["meeting_requests"]
        grand_contacts += ur
        grand_replies += tr
        grand_positive += pos
        grand_meetings += mtg
        segments.append({
            "segment": seg,
            "total_contacts": ur,
            "total_replies": tr,
            "unique_replied": ur,
            "positive": pos,
            "meeting_requests": mtg,
            "interested": r["interested"],
            "questions": r["questions"],
            "not_interested": r["not_interested"],
            "ooo": r["ooo"],
            "reply_rate": round(ur / ur * 100, 1) if ur else 0,
            "positive_rate": round(pos / ur * 100, 1) if ur else 0,
        })

    return {
        "project_id": project_id,
        "period": period,
        "totals": {
            "total_contacts": grand_contacts,
            "total_replies": grand_replies,
            "positive": grand_positive,
            "meeting_requests": grand_meetings,
        },
        "segments": segments,
    }


@router.post("/projects/{project_id}/generate-gtm")
async def generate_gtm_plan(
    project_id: int,
    session: AsyncSession = Depends(get_session),
    company_id: int | None = Depends(get_optional_company_id),
):
    """Generate GTM plan using Claude with segment funnel + warm conversations."""
    # GTM generation temporarily disabled to save API costs
    raise HTTPException(status_code=503, detail="GTM generation is temporarily disabled")

    from app.models.reply import ProcessedReply, ThreadMessage
    from app.models.campaign import Campaign
    import json as json_mod
    import anthropic

    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")

    # Verify project
    project_stmt = select(Project).where(
        Project.id == project_id, Project.deleted_at.is_(None),
    )
    if company_id:
        project_stmt = project_stmt.where(Project.company_id == company_id)
    project = (await session.execute(project_stmt)).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # ── 1. Segment funnel data — dynamic extraction from campaign names ──
    from app.utils.segment_extraction import build_segment_map as bsm_gtm, build_segment_case_when as bscw_gtm

    gtm_campaigns_result = await session.execute(
        select(Campaign.name).where(
            Campaign.project_id == project_id,
            Campaign.name.isnot(None),
        )
    )
    gtm_raw_names = [r[0] for r in gtm_campaigns_result.fetchall() if r[0]]
    gtm_segment_map = bsm_gtm(gtm_raw_names, project.name)

    reply_case = bscw_gtm(gtm_segment_map, "pr.campaign_name")

    funnel_sql = f"""
        SELECT {reply_case} as segment,
            COUNT(*) as total_replies,
            COUNT(*) FILTER (WHERE pr.category IN ('interested','meeting_request','question')) as positive,
            COUNT(*) FILTER (WHERE pr.category = 'meeting_request') as meeting_requests,
            COUNT(*) FILTER (WHERE pr.category = 'interested') as interested,
            COUNT(*) FILTER (WHERE pr.category = 'question') as questions,
            COUNT(*) FILTER (WHERE pr.category = 'not_interested') as not_interested,
            COUNT(*) FILTER (WHERE pr.category = 'out_of_office') as ooo,
            COUNT(*) FILTER (WHERE pr.category = 'wrong_person') as wrong_person,
            COUNT(*) FILTER (WHERE pr.category = 'unsubscribe') as unsubscribe
        FROM processed_replies pr
        JOIN contacts c2 ON LOWER(c2.email) = LOWER(pr.lead_email) AND c2.deleted_at IS NULL
        WHERE c2.project_id = :pid AND pr.parent_reply_id IS NULL
        GROUP BY 1 ORDER BY total_replies DESC
    """
    funnel_result = await session.execute(sql_text(funnel_sql), {"pid": project_id})
    funnel_rows = funnel_result.fetchall()

    # Campaign contact counts
    campaigns_result = await session.execute(
        select(Campaign.name, Campaign.leads_count, Campaign.platform)
        .where(Campaign.project_id == project_id)
    )
    campaigns = campaigns_result.fetchall()
    total_contacts = sum(c.leads_count or 0 for c in campaigns)

    funnel_text = "SEGMENT FUNNEL ANALYTICS:\n"
    funnel_text += f"Total contacts: ~{total_contacts} across {len(campaigns)} campaigns\n\n"
    funnel_text += f"{'Segment':<16} {'Replies':>7} {'Positive':>8} {'Meetings':>8} {'Interested':>10} {'Questions':>9} {'Not Int':>7} {'OOO':>5} {'Wrong':>5}\n"
    funnel_text += "-" * 95 + "\n"
    for r in funnel_rows:
        funnel_text += f"{r.segment:<16} {r.total_replies:>7} {r.positive:>8} {r.meeting_requests:>8} {r.interested:>10} {r.questions:>9} {r.not_interested:>7} {r.ooo:>5} {r.wrong_person:>5}\n"

    # ── 2. ALL replies (positive + negative + questions) grouped by segment ──
    # Include NOT_INTERESTED and QUESTION replies — objections are gold for strategy
    def _classify_segment(campaign_name: str) -> str:
        if not campaign_name:
            return "Other"
        from app.utils.segment_extraction import extract_segment
        return gtm_segment_map.get(campaign_name, extract_segment(campaign_name, project.name))

    # Fetch recent replies across ALL categories (not just positive)
    all_replies_result = await session.execute(
        select(ProcessedReply)
        .join(Contact, and_(
            func.lower(Contact.email) == func.lower(ProcessedReply.lead_email),
            Contact.deleted_at.is_(None),
        ))
        .where(
            Contact.project_id == project_id,
            ProcessedReply.parent_reply_id.is_(None),
            ProcessedReply.category.in_([
                "meeting_request", "interested", "question",
                "not_interested", "wrong_person",
            ]),
        )
        .order_by(ProcessedReply.received_at.desc())
        .limit(120)
    )
    all_replies = list(all_replies_result.scalars().all())

    # Fetch thread messages for replies that have them
    reply_ids = [r.id for r in all_replies]
    threads_map: Dict[int, list] = {}
    if reply_ids:
        threads_result = await session.execute(
            select(ThreadMessage)
            .where(ThreadMessage.reply_id.in_(reply_ids))
            .order_by(ThreadMessage.reply_id, ThreadMessage.position)
        )
        for tm in threads_result.scalars().all():
            threads_map.setdefault(tm.reply_id, []).append(tm)

    # Build conversations grouped by category for better analysis
    positive_convos = "POSITIVE REPLIES (meetings + interested + questions):\n\n"
    negative_convos = "OBJECTIONS & REJECTIONS (not_interested + wrong_person):\n\n"
    pos_count = neg_count = 0

    for reply in all_replies:
        seg = _classify_segment(reply.campaign_name)

        header = f"--- [{seg}] {reply.lead_first_name or ''} {reply.lead_last_name or ''}"
        if reply.lead_company:
            header += f" @ {reply.lead_company}"
        header += f" | {reply.category}"
        if reply.email_subject:
            header += f" | subj: {reply.email_subject[:80]}"
        header += f" | {reply.campaign_name or 'unknown'}\n"

        thread = threads_map.get(reply.id, [])
        body_text = ""
        if thread:
            for msg in thread:
                d = ">>>" if msg.direction == "outbound" else "<<<"
                b = (msg.body or "")[:350].strip()
                if b:
                    body_text += f"  {d} {b}\n"
        else:
            b = (reply.reply_text or reply.email_body or "")[:350].strip()
            if b:
                body_text += f"  <<< {b}\n"

        if reply.category in ("meeting_request", "interested", "question") and pos_count < 70:
            positive_convos += header + body_text + "\n"
            pos_count += 1
        elif reply.category in ("not_interested", "wrong_person") and neg_count < 50:
            negative_convos += header + body_text + "\n"
            neg_count += 1

    # ── 3. Campaign list with metadata ──
    campaigns_text = "CAMPAIGNS:\n"
    for c in sorted(campaigns, key=lambda x: x.leads_count or 0, reverse=True):
        campaigns_text += f"  {c.name} ({c.platform}, {c.leads_count or '?'} leads)\n"

    # ── 4. Call Claude Opus ──
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    system_prompt = """You are a strategic growth advisor reviewing REAL cold outreach data. Your job: provide actionable, data-driven recommendations that build on the team's existing strategy.

PRODUCT: Rizzult — performance marketing platform connecting brands with influencers on a CPA (cost-per-action) model. Brands pay only for completed actions (orders, signups, installs). Primarily LATAM market, Spanish-language outreach via email + LinkedIn.

CRITICAL CONTEXT — RESPECT THE TEAM'S STRATEGY:
- The outreach team has DELIBERATELY chosen their targeting approach — your job is to optimize, not criticize
- "Wrong person" replies are NOT failures — the team intentionally casts a wider net to get referrals to decision-makers. This is a VALID strategy. Frame these as "referral path replies" and analyze which ones led to successful redirections
- Each segment's targeting was a deliberate HYPOTHESIS being tested. Present results as "hypothesis results" not "mistakes"
- Use CONSTRUCTIVE framing: "opportunity to improve" not "terrible conversion"; "refine targeting" not "wrong targeting"; "test showed X" not "failure"
- Your tone must be that of a trusted advisor who respects the team's decisions and offers data-backed suggestions for improvement

DATA PROVIDED:
1. SEGMENT FUNNEL — reply/conversion metrics per business vertical (derived from campaign names)
2. POSITIVE CONVERSATIONS — meetings, interested, questions (with thread history when available)
3. OBJECTIONS — not_interested + wrong_person replies (these reveal optimization opportunities)
4. CAMPAIGN LIST — all active outreach campaigns with platform and lead count

YOUR ANALYSIS STANDARDS:
- NEVER fabricate case studies, brand names, or metrics not in the provided data
- ONLY quote phrases that appear verbatim in the conversations provided
- For segments with <20 replies: confidence=LOW, recommend gathering more data before changes
- Every action item must answer: WHO does WHAT by WHEN with WHAT message
- Objection analysis should focus on OPTIMIZATION opportunities, not blame

Return ONLY valid JSON:
{
  "executive_summary": "3-5 sentences. Start with the #1 revenue opportunity, then the #1 optimization opportunity, then the recommended next move. Use constructive, forward-looking language.",

  "segments": [
    {
      "segment": "Name",
      "priority": 1,
      "verdict": "SCALE UP|MAINTAIN|REFINE|TEST MORE|REALLOCATE",
      "confidence": "HIGH (50+ replies)|MEDIUM (20-50)|LOW (<20)",

      "metrics": {
        "contacts": 8000,
        "total_replies": 661,
        "unique_replied": 500,
        "meetings": 27,
        "positive": 36,
        "not_interested": 15,
        "wrong_person": 10,
        "reply_rate_pct": 6.3,
        "meeting_rate_pct": 4.1,
        "wrong_person_pct": 1.5
      },

      "diagnosis": "2-3 sentences. Present as hypothesis results: what the data shows about this segment's response to the current approach. Constructive tone.",

      "winning_patterns": ["EXACT quote from a conversation that led to a meeting"],
      "losing_patterns": ["EXACT quote from a not_interested or wrong_person reply"],

      "this_week_actions": [
        {
          "action": "REPLACE|ADD|REMOVE|CHANGE",
          "what": "Specific thing to change (e.g., 'first email opening line')",
          "from": "Current text or approach being used (quote from data if available)",
          "to": "New text or approach — ready to copy-paste into campaign",
          "why": "Evidence from conversations — framed constructively"
        }
      ],

      "targeting_fix": {
        "current_problem": "What the data suggests about current targeting (e.g., 'referral path replies at 16% — opportunity to tighten for efficiency')",
        "target_titles": ["VP Marketing", "Head of Growth"],
        "avoid_titles": ["Procurement", "Admin"],
        "company_criteria": "50-500 employees, LATAM, has existing influencer spend"
      },

      "email_template": {
        "subject": "Subject line — based on what actually got replies",
        "opening": "First 2 sentences of the email — ready to use",
        "cta": "The specific call-to-action that converts"
      },

      "channel_recommendation": "email-first|linkedin-first|both — with reasoning",
      "monthly_volume_target": 500
    }
  ],

  "critical_bottlenecks": [
    {
      "bottleneck": "One-sentence description — constructive framing",
      "severity": "CRITICAL|HIGH|MEDIUM",
      "affected_replies": 107,
      "affected_pct": 16.2,
      "evidence": "Exact quote or data point",
      "root_cause": "What the data suggests about the cause",
      "fix": "Recommended optimization steps",
      "expected_impact": "What improvement to expect (e.g., '+5% meeting rate')"
    }
  ],

  "messaging_rules": [
    {
      "rule": "NEVER|ALWAYS|REPLACE",
      "description": "e.g., NEVER use 'CPA' in first email",
      "evidence": "Quote from prospect showing confusion/rejection",
      "alternative": "What to say instead"
    }
  ],

  "new_segments_to_test": [
    {
      "segment": "Name",
      "why": "Based on patterns in conversations provided — NOT fabricated",
      "initial_volume": 200,
      "test_message": "First email opening to test"
    }
  ],

  "thirty_day_plan": [
    {
      "week": 1,
      "priority": "P0",
      "actions": [
        {
          "task": "Exact task description",
          "segment": "Target",
          "owner": "campaign_manager|copywriter|data_team",
          "deliverable": "What's produced (e.g., '3 new email templates for Shopping')",
          "volume": 500
        }
      ]
    }
  ],

  "kpi_targets": {
    "current_meeting_rate": 4.1,
    "target_meeting_rate_30d": 6.0,
    "current_wrong_person_pct": 8.5,
    "target_wrong_person_pct_30d": 4.0,
    "segments_to_scale": ["Agencies", "Telemedicine"],
    "segments_to_reallocate": ["Streaming"]
  }
}

ABSOLUTE RULES:
1. Include EVERY segment from funnel data — no exceptions
2. Every winning_pattern and losing_pattern must be a VERBATIM quote from the conversations provided. If no quote exists, say "No conversation data for this pattern"
3. email_template.opening must be in SPANISH (the outreach language) and ready to paste
4. this_week_actions must be specific enough that a junior SDR can execute without asking questions
5. NEVER invent revenue numbers, brand names, or metrics — only reference data you can see in the input
6. messaging_rules: extract at least 5 rules from the objection patterns
7. thirty_day_plan: week 1 = optimize messaging, week 2 = scale what works, week 3 = test new, week 4 = measure + iterate
8. critical_bottlenecks must include the EXACT number of affected replies and percentage
9. INTERNAL CONSISTENCY: if you create a NEVER rule (e.g., "never use CPA"), your own email_templates MUST NOT violate that rule
10. NEVER use words like "terrible", "failure", "broken", "wrong" as judgments. Use "opportunity", "refine", "optimize", "hypothesis result"
11. this_week_actions "from" field: quote the ACTUAL current email text being used (from conversations) — not a generic description
12. For segments you recommend REALLOCATING: include a "reallocate_to" field suggesting where to redirect those leads
13. "wrong_person" replies should be analyzed for REFERRAL POTENTIAL — the team deliberately targets broadly to get redirected to decision-makers"""

    user_prompt = f"""Project: {project.name}

{funnel_text}

{campaigns_text}

{positive_convos}

{negative_convos}

ANALYSIS FOCUS — answer these with EVIDENCE from the data above:
1. Shopping: 661 replies, 27 meetings (4.1%). WHY the 96% drop-off? Quote specific objections.
2. Agencies: 163 replies, 27 meetings (16.6%). What's DIFFERENT about these conversations?
3. Wrong person rate: count exact wrong_person replies per segment. Which segments have targeting problems?
4. "CPA" confusion: find every conversation where the prospect didn't understand the offer. What words caused confusion?
5. For each segment: what is the ONE change to make THIS WEEK that would improve meetings by 20%?
6. Which segments should be DROPPED immediately (zero meetings + low replies)?
7. Channel: do email campaigns or LinkedIn campaigns convert differently? (check campaign platform data)
8. What messaging rules should be ENFORCED across all campaigns based on objection patterns?"""

    # Input summary for log
    input_summary = f"{len(campaigns)} campaigns, {sum(r.total_replies for r in funnel_rows)} replies, {pos_count} positive + {neg_count} objections"

    try:
        # Use streaming to avoid timeout on large outputs
        response_text = ""
        in_tokens = 0
        out_tokens = 0
        async with client.messages.stream(
            model="claude-sonnet-4-20250514",
            max_tokens=16000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            temperature=0.2,
        ) as stream:
            async for text in stream.text_stream:
                response_text += text
            final_message = await stream.get_final_message()
            in_tokens = final_message.usage.input_tokens
            out_tokens = final_message.usage.output_tokens
        # Sonnet 4 pricing: $3/M input, $15/M output
        cost = round(in_tokens * 3 / 1_000_000 + out_tokens * 15 / 1_000_000, 4)

        # Extract JSON from response (may have markdown wrapping)
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if not json_match:
            raise ValueError("No JSON found in Sonnet response")
        gtm_json = json_match.group(0)
        json_mod.loads(gtm_json)  # validate

        # Save to project (latest strategy)
        project.gtm_plan = gtm_json
        project.updated_at = datetime.utcnow()

        # Save to log
        from app.models.gtm_log import GTMStrategyLog
        log = GTMStrategyLog(
            project_id=project_id,
            trigger="manual",
            model="claude-sonnet-4-20250514",
            strategy_json=gtm_json,
            input_summary=input_summary,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            cost_usd=str(cost),
            status="completed",
        )
        session.add(log)
        await session.commit()
        await session.refresh(log)

        return {
            "success": True,
            "gtm_plan": gtm_json,
            "log_id": log.id,
            "tokens": {"input": in_tokens, "output": out_tokens, "cost_usd": cost},
        }
    except Exception as e:
        # Log the failure
        try:
            from app.models.gtm_log import GTMStrategyLog
            fail_log = GTMStrategyLog(
                project_id=project_id,
                trigger="manual",
                model="claude-sonnet-4-20250514",
                input_summary=input_summary,
                status="failed",
                error_message=str(e)[:500],
            )
            session.add(fail_log)
            await session.commit()
        except Exception:
            pass
        logger.error(f"GTM generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"GTM generation failed: {str(e)}")


@router.get("/projects/{project_id}/gtm-strategy-logs")
async def get_gtm_strategy_logs(
    project_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    company_id: int | None = Depends(get_optional_company_id),
):
    """List GTM strategy generation logs for a project."""
    from app.models.gtm_log import GTMStrategyLog

    count_result = await session.execute(
        select(func.count(GTMStrategyLog.id)).where(GTMStrategyLog.project_id == project_id)
    )
    total = count_result.scalar() or 0

    logs_result = await session.execute(
        select(GTMStrategyLog)
        .where(GTMStrategyLog.project_id == project_id)
        .order_by(GTMStrategyLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    logs = logs_result.scalars().all()

    return {
        "items": [
            {
                "id": log.id,
                "trigger": log.trigger,
                "model": log.model,
                "status": log.status,
                "input_summary": log.input_summary,
                "input_tokens": log.input_tokens,
                "output_tokens": log.output_tokens,
                "cost_usd": log.cost_usd,
                "error_message": log.error_message,
                "created_at": log.created_at.isoformat() if log.created_at else None,
                "has_strategy": log.strategy_json is not None,
            }
            for log in logs
        ],
        "total": total,
    }


@router.get("/projects/{project_id}/gtm-strategy-logs/{log_id}")
async def get_gtm_strategy_log_detail(
    project_id: int,
    log_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get a specific GTM strategy log with full strategy JSON."""
    from app.models.gtm_log import GTMStrategyLog

    log = (await session.execute(
        select(GTMStrategyLog).where(
            GTMStrategyLog.id == log_id,
            GTMStrategyLog.project_id == project_id,
        )
    )).scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="GTM log not found")

    return {
        "id": log.id,
        "project_id": log.project_id,
        "trigger": log.trigger,
        "model": log.model,
        "status": log.status,
        "strategy_json": log.strategy_json,
        "input_summary": log.input_summary,
        "input_tokens": log.input_tokens,
        "output_tokens": log.output_tokens,
        "cost_usd": log.cost_usd,
        "error_message": log.error_message,
        "created_at": log.created_at.isoformat() if log.created_at else None,
    }


class TranslateRequest(BaseModel):
    text: str
    target_lang: str = "en"


@router.post("/translate")
async def translate_text(body: TranslateRequest = Body(...)):
    """Translate text to target language using GPT-4o-mini."""
    from app.services.reply_processor import detect_and_translate
    if not body.text or len(body.text.strip()) < 5:
        return {"translated": None}
    result = await detect_and_translate(body.text[:3000])
    return {"translated": result.get("translation"), "language": result.get("language")}


class CRMSpotlightRequest(BaseModel):
    question: str
    filters: Optional[Dict[str, Any]] = None


@router.post("/projects/{project_id}/crm-spotlight-gtm")
async def crm_spotlight_gtm(
    project_id: int,
    body: CRMSpotlightRequest = Body(...),
    session: AsyncSession = Depends(get_session),
    company_id: int | None = Depends(get_optional_company_id),
):
    """Analyze warm reply contacts with Gemini 2.5 Pro and generate GTM insights.

    Operator asks a question (e.g. 'how to improve scheduling rate') from the CRM page
    with warm-reply filters active. We fetch matching contacts + their conversation histories,
    feed everything to Gemini, and save the analysis as the project's GTM plan.
    """
    from collections import Counter
    from app.models.reply import ProcessedReply, ThreadMessage
    from app.services.gemini_client import gemini_generate, extract_json_from_gemini
    import json as json_mod

    # Verify project
    project_stmt = select(Project).where(
        Project.id == project_id, Project.deleted_at.is_(None),
    )
    if company_id:
        project_stmt = project_stmt.where(Project.company_id == company_id)
    project = (await session.execute(project_stmt)).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Build contact query with caller's filters
    filters = body.filters or {}
    query = await _build_filtered_query(
        session, company_id,
        project_id=project_id,
        has_replied=filters.get("has_replied", True),
        reply_category=filters.get("reply_category", "interested,meeting_request,question,other"),
        segment=filters.get("segment"),
        geo=filters.get("geo"),
        status=filters.get("status"),
        campaign=filters.get("campaign"),
        campaign_id=filters.get("campaign_id"),
        search=filters.get("search"),
        created_after=filters.get("created_after"),
        created_before=filters.get("created_before"),
        reply_since=filters.get("reply_since"),
    )
    result = await session.execute(query.limit(200))
    contacts = list(result.scalars().all())

    if not contacts:
        raise HTTPException(status_code=400, detail="No matching contacts found with current filters.")

    # Fetch latest ProcessedReply + thread_messages for each contact
    contact_emails = [c.email for c in contacts]
    replies_result = await session.execute(
        select(ProcessedReply)
        .where(ProcessedReply.lead_email.in_(contact_emails))
        .order_by(ProcessedReply.lead_email, desc(ProcessedReply.received_at))
    )
    all_replies = list(replies_result.scalars().all())

    # Group replies by email (take latest per email)
    replies_by_email: Dict[str, ProcessedReply] = {}
    for r in all_replies:
        if r.lead_email not in replies_by_email:
            replies_by_email[r.lead_email] = r

    # Fetch thread messages for these replies
    reply_ids = [r.id for r in replies_by_email.values()]
    threads: Dict[int, list] = {}
    if reply_ids:
        thread_result = await session.execute(
            select(ThreadMessage)
            .where(ThreadMessage.reply_id.in_(reply_ids))
            .order_by(ThreadMessage.reply_id, ThreadMessage.position)
        )
        for tm in thread_result.scalars().all():
            threads.setdefault(tm.reply_id, []).append(tm)

    # Build conversation summaries for Gemini
    conversation_summaries = []
    category_counts: Dict[str, int] = Counter()
    for c in contacts:
        reply = replies_by_email.get(c.email)
        cat = reply.category if reply else "unknown"
        category_counts[cat] += 1

        summary = f"- {c.first_name or ''} {c.last_name or ''} ({c.email})"
        summary += f" | Company: {c.company_name or 'N/A'} | Title: {c.job_title or 'N/A'}"
        summary += f" | Category: {cat}"
        if c.status:
            summary += f" | Status: {c.status}"

        if reply and reply.id in threads:
            msgs = threads[reply.id]
            summary += f"\n  Conversation ({len(msgs)} messages):"
            for msg in msgs[:10]:  # limit to 10 messages per thread
                direction = "LEAD" if msg.direction == "inbound" else "US"
                body_preview = (msg.body or "")[:300].replace("\n", " ").strip()
                if body_preview:
                    summary += f"\n    [{direction}]: {body_preview}"
        elif reply:
            body_preview = (reply.email_body or "")[:300].replace("\n", " ").strip()
            if body_preview:
                summary += f"\n  Latest reply: {body_preview}"

        conversation_summaries.append(summary)

    category_breakdown = ", ".join(f"{cat}: {cnt}" for cat, cnt in category_counts.most_common())

    system_prompt = """You are a B2B sales strategist analyzing REAL conversation histories from a cold outreach campaign.
The operator is asking for specific, actionable advice on how to improve their scheduling/conversion rate.

Analyze every conversation carefully. Look for patterns:
- What objections appear frequently?
- What messaging resonates vs falls flat?
- Where do conversations stall (after what message)?
- What types of leads actually schedule vs just show interest?
- Common drop-off points in the conversation funnel

Return ONLY valid JSON:
{
  "segments": [
    {
      "segment": "Pattern/Category Name",
      "priority": 1,
      "size": 123,
      "rationale": "Data-driven insight about this group",
      "characteristics": ["trait 1", "trait 2"],
      "outreach_angle": "Specific recommendation for this group"
    }
  ],
  "summary": "Executive summary answering the operator's question with specific, actionable recommendations. Reference actual conversation patterns you observed.",
  "total_addressable": "Conversion funnel analysis: X warm leads → Y interested → Z scheduled"
}

Be specific and reference actual patterns from the conversations. Don't be generic."""

    user_prompt = f"""Project: {project.name}
Operator's question: {body.question}

REPLY CATEGORY BREAKDOWN: {category_breakdown}
TOTAL WARM CONTACTS ANALYZED: {len(contacts)}

CONVERSATION HISTORIES:
{chr(10).join(conversation_summaries[:100])}

Based on these REAL conversations, answer the operator's question with specific, data-driven recommendations.
Focus on what patterns emerge and what concrete changes would improve the scheduling/conversion rate."""

    try:
        result = await gemini_generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.4,
            max_tokens=6000,
            model="gemini-2.5-flash",
            project_id=project_id,
        )

        gtm_json = extract_json_from_gemini(result["content"])
        json_mod.loads(gtm_json)  # validate

        # Save as project GTM plan
        project.gtm_plan = gtm_json
        project.updated_at = datetime.utcnow()
        await session.commit()

        return {
            "success": True,
            "gtm_plan": gtm_json,
            "contacts_analyzed": len(contacts),
            "project_slug": project.name.lower().replace(" ", "-"),
        }
    except Exception as e:
        logger.error(f"CRM Spotlight GTM failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


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


@router.post("/projects/{project_id}/classify-segments")
async def classify_project_segments(
    project_id: int,
    limit: int = Query(0, description="Max contacts to classify (0=all, 1000 for test)"),
    cross_match_project: Optional[str] = Query(None, description="Target project name for cross-matching (e.g. 'inxy')"),
    session: AsyncSession = Depends(get_session),
    company_id: int | None = Depends(get_optional_company_id),
):
    """Batch classify contacts into business segments using website scraping + GPT-4o-mini.
    Optionally cross-match results against a target project's ICP."""
    from app.services.segment_classifier import classify_contacts_for_project, cross_match_for_project

    # Verify project exists
    project_stmt = select(Project).where(
        Project.id == project_id,
        Project.deleted_at.is_(None),
    )
    if company_id:
        project_stmt = project_stmt.where(Project.company_id == company_id)
    project = (await session.execute(project_stmt)).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        result = await classify_contacts_for_project(
            session, project_id, limit=limit, only_unclassified=True,
        )

        # Optional cross-matching step
        cross_match_result = None
        if cross_match_project:
            cross_match_result = await cross_match_for_project(
                session, project_id, target_project_name=cross_match_project,
            )

        return {"success": True, **result, "cross_match": cross_match_result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Segment classification failed: {str(e)}")


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

    # Extract campaigns from platform_state
    campaigns_raw = []
    ps = contact.platform_state or {}
    for plat_name, plat_data in ps.items():
        if isinstance(plat_data, dict):
            for camp in plat_data.get("campaigns", []):
                if isinstance(camp, dict):
                    camp_copy = dict(camp)
                    camp_copy.setdefault("source", plat_name)
                    campaigns_raw.append(camp_copy)

    if not campaigns_raw:
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

    # Fetch live GetSales history if local linkedin activities are incomplete
    if contact and contact.platform_state and "getsales" in (contact.platform_state or {}):
        try:
            gs_key = os.getenv("GETSALES_API_KEY")
            if gs_key:
                from app.services.crm_sync_service import GetSalesClient
                gs_client = GetSalesClient(gs_key)
                try:
                    # Try lead_uuid from getsales_id or platform_state
                    lead_uuid = contact.getsales_id
                    if not lead_uuid:
                        gs_state = contact.platform_state.get("getsales", {})
                        gs_campaigns = gs_state.get("campaigns", [])
                        if gs_campaigns and isinstance(gs_campaigns[0], dict):
                            lead_uuid = gs_campaigns[0].get("lead_uuid")
                    if lead_uuid:
                        gs_messages = await gs_client.get_messages_by_lead(lead_uuid)
                        if gs_messages:
                            existing_bodies = {(a.body or "")[:80].strip().lower() for a in linkedin_activities}
                            from app.models.contact import ContactActivity as CA
                            for msg in gs_messages:
                                body = msg.get("body") or msg.get("text") or ""
                                if body[:80].strip().lower() in existing_bodies:
                                    continue
                                existing_bodies.add(body[:80].strip().lower())
                                direction = "outbound" if msg.get("type") == "outbox" else "inbound"
                                ts_str = msg.get("created_at") or msg.get("sent_at")
                                ts = None
                                if ts_str:
                                    try:
                                        from dateutil.parser import parse as dt_parse
                                        ts = dt_parse(ts_str).replace(tzinfo=None)
                                    except Exception:
                                        pass
                                # Create a fake activity object for rendering
                                fake = CA(
                                    id=hash(ts_str or body) & 0x7FFFFFFF,
                                    contact_id=contact_id,
                                    activity_type="linkedin_sent" if direction == "outbound" else "linkedin_replied",
                                    channel="linkedin",
                                    direction=direction,
                                    source="getsales_live",
                                    body=body,
                                    snippet=body[:200] if body else None,
                                    activity_at=ts,
                                )
                                linkedin_activities.append(fake)
                            linkedin_activities.sort(key=lambda a: a.activity_at or datetime.min, reverse=True)
                finally:
                    await gs_client.close()
        except Exception as e:
            logger.warning(f"Failed to fetch live GetSales history for contact {contact_id}: {e}")

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

    # Supplement email_history with processed_replies that may be missing
    # (e.g. SmartLead API didn't return them for archived/old campaigns)
    if contact and contact.email:
        from app.models.reply import ProcessedReply
        pr_result = await session.execute(
            select(ProcessedReply)
            .where(
                and_(
                    func.lower(ProcessedReply.lead_email) == contact.email.lower(),
                    ProcessedReply.received_at.isnot(None),
                )
            )
            .order_by(ProcessedReply.received_at.desc())
        )
        processed_replies = pr_result.scalars().all()

        if processed_replies:
            # Build a set of existing message fingerprints to avoid duplicates.
            # Use (direction, truncated body, rounded timestamp) for matching.
            existing_fingerprints = set()
            for msg in email_history:
                body_snippet = (msg.get("body") or "")[:100].strip().lower()
                existing_fingerprints.add(("inbound", body_snippet))
            # Also add fingerprints from local DB activities already in history
            for a in (a for a in activities if a.channel == "email" and a.direction == "inbound"):
                body_snippet = (a.body or "")[:100].strip().lower()
                existing_fingerprints.add(("inbound", body_snippet))

            for pr in processed_replies:
                body = pr.reply_text or pr.email_body or ""
                body_clean = _strip_html(body) if "<" in body else body
                body_snippet = body_clean[:100].strip().lower()

                if ("inbound", body_snippet) in existing_fingerprints:
                    continue  # already present
                if not body_clean.strip():
                    continue  # skip empty

                existing_fingerprints.add(("inbound", body_snippet))
                email_history.append({
                    "id": pr.id + 2_000_000_000,  # offset to avoid ID collision
                    "type": "email_reply",
                    "direction": "inbound",
                    "subject": pr.email_subject or "",
                    "body": body_clean,
                    "snippet": body_clean[:200] if body_clean else None,
                    "channel": "email",
                    "source": "processed_reply",
                    "campaign": pr.campaign_name,
                    "timestamp": pr.received_at.isoformat() if pr.received_at else None,
                })

            # Re-sort by timestamp descending (newest first) after merging
            email_history.sort(
                key=lambda m: m.get("timestamp") or "",
                reverse=True,
            )

    # Fetch inbox links from ProcessedReply for this contact's email
    inbox_links = {}
    if contact and contact.email:
        from app.models.reply import ProcessedReply
        inbox_result = await session.execute(
            select(ProcessedReply.campaign_name, ProcessedReply.inbox_link)
            .where(
                and_(
                    ProcessedReply.lead_email == contact.email,
                    ProcessedReply.inbox_link.isnot(None),
                )
            )
            .order_by(ProcessedReply.received_at.desc())
        )
        for row in inbox_result:
            key = row.campaign_name or "Unknown"
            if key not in inbox_links:
                inbox_links[key] = row.inbox_link

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
                "automation": get_getsales_flow_name(a.extra_data, None),
                "timestamp": a.activity_at.isoformat(),
            }
            for a in linkedin_activities
        ],
        "inbox_links": inbox_links,
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

    # Re-derive external status on manual status change
    if contact.project_id:
        proj_result = await session.execute(
            select(Project).where(Project.id == contact.project_id)
        )
        proj = proj_result.scalar()
        if proj and proj.external_status_config:
            from app.services.status_machine import derive_external_status
            ext = derive_external_status(
                proj.external_status_config,
                internal_status=request.status,
            )
            if ext:
                contact.status_external = ext

    # Sync to Smartlead if enabled and contact has smartlead_id
    smartlead_synced = False
    if request.sync_to_smartlead and contact.smartlead_id and request.status in SMARTLEAD_STATUS_MAPPING:
        api_key = os.getenv("SMARTLEAD_API_KEY")
        if api_key:
            category_id = SMARTLEAD_STATUS_MAPPING[request.status]
            pause_lead = request.status in SMARTLEAD_PAUSE_ON_STATUS
            
            # Get campaign ID from contact's platform_state
            campaign_id = None
            sl_campaigns = contact.get_platform("smartlead").get("campaigns", [])
            for c in sl_campaigns:
                if isinstance(c, dict):
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

    # Propagate status_external to Google Sheet (fire-and-forget)
    if contact.status_external and contact.project_id and contact.email:
        try:
            from app.services.sheet_sync_service import sheet_sync_service
            await sheet_sync_service.update_sheet_status(
                contact.project_id, contact.email, contact.status_external
            )
        except Exception as e:
            logger.warning(f"Sheet status update failed for {contact.email}: {e}")

    return {
        "id": contact.id,
        "email": contact.email,
        "old_status": old_status,
        "new_status": contact.status,
        "smartlead_synced": smartlead_synced,
        "getsales_synced": False,  # Not supported via API
        "tasks_created": tasks_created,
    }
