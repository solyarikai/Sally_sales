"""
Pipeline API — Discovered companies, contact extraction, Apollo enrichment, CRM promotion.

All endpoints are company-scoped (require X-Company-ID header).
"""
from fastapi import APIRouter, Depends, HTTPException, Query as QueryParam
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
import csv
import io
import logging
from datetime import datetime

from app.db import get_session
from app.api.companies import get_required_company
from app.models.user import Company
from app.schemas.pipeline import (
    DiscoveredCompanyResponse, DiscoveredCompanyDetail,
    ExtractedContactResponse, PipelineEventResponse,
    PipelineStats,
    ExtractContactsRequest, ApolloEnrichRequest,
    PromoteToContactsRequest, BulkStatusUpdateRequest,
)
from app.services.pipeline_service import pipeline_service

router = APIRouter(prefix="/pipeline", tags=["pipeline"])
logger = logging.getLogger(__name__)


# ============ Projects (for dropdown) ============

@router.get("/projects")
async def list_pipeline_projects(
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """List projects that have discovered companies (fast, for dropdown)."""
    from sqlalchemy import text
    result = await db.execute(text("""
        SELECT DISTINCT dc.project_id as id, p.name
        FROM discovered_companies dc
        JOIN projects p ON p.id = dc.project_id
        WHERE dc.company_id = :company_id
        ORDER BY p.name
    """), {"company_id": company.id})
    return [{"id": row.id, "name": row.name} for row in result.fetchall()]


# ============ Discovered Companies ============

@router.get("/discovered-companies")
async def list_discovered_companies(
    project_id: Optional[int] = QueryParam(None),
    status: Optional[str] = QueryParam(None),
    is_target: Optional[bool] = QueryParam(None),
    search: Optional[str] = QueryParam(None),
    page: int = QueryParam(1, ge=1),
    page_size: int = QueryParam(50, ge=1, le=200),
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """List discovered companies with filters."""
    result = await pipeline_service.list_discovered_companies(
        session=db,
        company_id=company.id,
        project_id=project_id,
        status=status,
        is_target=is_target,
        search=search,
        page=page,
        page_size=page_size,
    )

    return {
        "items": [DiscoveredCompanyResponse.model_validate(item) for item in result["items"]],
        "total": result["total"],
        "page": result["page"],
        "page_size": result["page_size"],
    }


@router.get("/discovered-companies/{discovered_company_id}", response_model=DiscoveredCompanyDetail)
async def get_discovered_company(
    discovered_company_id: int,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Get discovered company detail with contacts and events."""
    dc = await pipeline_service.get_discovered_company_detail(
        session=db,
        company_id=company.id,
        discovered_company_id=discovered_company_id,
    )
    if not dc:
        raise HTTPException(status_code=404, detail="Discovered company not found")

    return DiscoveredCompanyDetail.model_validate(dc)


# ============ Contact Extraction ============

@router.post("/extract-contacts")
async def extract_contacts(
    body: ExtractContactsRequest,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Run GPT contact extraction on selected discovered companies."""
    stats = await pipeline_service.extract_contacts_batch(
        session=db,
        discovered_company_ids=body.discovered_company_ids,
        company_id=company.id,
    )
    return stats


# ============ Apollo Enrichment ============

# Only allow Apollo enrichment for these projects (to limit credit usage)
APOLLO_ALLOWED_PROJECTS = {"archistruct", "deliryo"}


@router.post("/enrich-apollo")
async def enrich_apollo(
    body: ApolloEnrichRequest,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Run Apollo enrichment on selected discovered companies."""
    from app.models.pipeline import DiscoveredCompany
    from app.models.contact import Project
    from sqlalchemy import select

    # Check that all selected companies belong to allowed projects
    result = await db.execute(
        select(DiscoveredCompany.project_id)
        .where(DiscoveredCompany.id.in_(body.discovered_company_ids))
        .distinct()
    )
    project_ids = [row[0] for row in result.fetchall()]

    proj_result = await db.execute(
        select(Project.id, Project.name).where(Project.id.in_(project_ids))
    )
    proj_names = {row.id: row.name for row in proj_result.fetchall()}

    blocked = [name for pid, name in proj_names.items() if name.lower() not in APOLLO_ALLOWED_PROJECTS]
    if blocked:
        raise HTTPException(
            status_code=400,
            detail=f"Apollo enrichment is restricted to archistruct and deliryo projects. Blocked: {', '.join(blocked)}",
        )

    stats = await pipeline_service.enrich_apollo_batch(
        session=db,
        discovered_company_ids=body.discovered_company_ids,
        company_id=company.id,
        max_people=body.max_people,
        titles=body.titles,
        max_credits=body.max_credits,
    )
    return stats


# ============ Promote to CRM ============

@router.post("/promote-to-crm")
async def promote_to_crm(
    body: PromoteToContactsRequest,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Promote extracted contacts to CRM Contact records."""
    stats = await pipeline_service.promote_to_crm(
        session=db,
        extracted_contact_ids=body.extracted_contact_ids,
        company_id=company.id,
        project_id=body.project_id,
        segment=body.segment,
    )
    return stats


# ============ Pipeline Stats ============

@router.get("/stats", response_model=PipelineStats)
async def get_pipeline_stats(
    project_id: Optional[int] = QueryParam(None),
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Get pipeline stats for a project."""
    stats = await pipeline_service.get_pipeline_stats(
        session=db,
        company_id=company.id,
        project_id=project_id,
    )
    return PipelineStats(**stats)


# ============ Bulk Status Update ============

@router.post("/update-status")
async def update_status(
    body: BulkStatusUpdateRequest,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Bulk update status for discovered companies."""
    from app.models.pipeline import DiscoveredCompany, DiscoveredCompanyStatus
    from sqlalchemy import select

    result = await db.execute(
        select(DiscoveredCompany).where(
            DiscoveredCompany.id.in_(body.discovered_company_ids),
            DiscoveredCompany.company_id == company.id,
        )
    )
    companies = result.scalars().all()

    updated = 0
    for dc in companies:
        dc.status = DiscoveredCompanyStatus(body.status.value.upper())
        updated += 1

    await db.commit()
    return {"updated": updated}


# ============ Export ============

@router.get("/export-csv")
async def export_csv(
    project_id: Optional[int] = QueryParam(None),
    is_target: Optional[bool] = QueryParam(None),
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Export discovered companies as CSV."""
    data = await pipeline_service.list_discovered_companies(
        session=db,
        company_id=company.id,
        project_id=project_id,
        is_target=is_target,
        page=1,
        page_size=10000,
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Domain", "Company Name", "Is Target", "Confidence", "Status",
        "Reasoning", "Services", "Location", "Industry",
        "Contacts Count", "Emails", "Phones", "Apollo People",
    ])

    for dc in data["items"]:
        info = dc.company_info or {}
        services = ", ".join(info.get("services", [])) if info.get("services") else ""
        emails = ", ".join(dc.emails_found or [])
        phones = ", ".join(dc.phones_found or [])

        writer.writerow([
            dc.domain,
            dc.name or info.get("name", ""),
            "Yes" if dc.is_target else "No",
            f"{(dc.confidence or 0) * 100:.0f}%",
            dc.status.value if hasattr(dc.status, 'value') else str(dc.status),
            dc.reasoning or "",
            services,
            info.get("location", ""),
            info.get("industry", ""),
            dc.contacts_count or 0,
            emails,
            phones,
            dc.apollo_people_count or 0,
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=pipeline_companies.csv"},
    )


CONTACTS_HEADERS = [
    "Domain", "URL", "Company Name", "Description", "Industry", "Location", "Confidence",
    "Reasoning", "First Name", "Last Name", "Email", "Phone", "Job Title", "LinkedIn",
    "Source", "Source Details",
]


async def _query_contacts(db: AsyncSession, company_id: int, project_id: Optional[int],
                          email_only: bool, phone_only: bool):
    """Shared query for contacts export (CSV + Google Sheets)."""
    from sqlalchemy import text
    import json

    where_clauses = ["dc.company_id = :company_id", "dc.is_target = true"]
    params = {"company_id": company_id}

    if project_id is not None:
        where_clauses.append("dc.project_id = :project_id")
        params["project_id"] = project_id
    if email_only:
        where_clauses.append("ec.email IS NOT NULL")
    if phone_only:
        where_clauses.append("ec.phone IS NOT NULL")

    query = text(f"""
        SELECT
            dc.domain,
            'https://' || dc.domain as url,
            dc.company_info->>'name' as company_name,
            dc.company_info->>'description' as description,
            dc.company_info->>'industry' as industry,
            dc.company_info->>'location' as location,
            dc.confidence,
            dc.reasoning,
            ec.first_name,
            ec.last_name,
            ec.email,
            ec.phone,
            ec.job_title,
            ec.linkedin_url,
            CAST(ec.source AS text) as source,
            ec.raw_data,
            COALESCE(sq.query_text, sq2.query_text) as search_query,
            sj.search_engine as search_engine
        FROM extracted_contacts ec
        JOIN discovered_companies dc ON ec.discovered_company_id = dc.id
        LEFT JOIN search_results sr ON sr.id = dc.search_result_id
        LEFT JOIN search_queries sq ON sq.id = sr.source_query_id
        LEFT JOIN search_jobs sj ON sj.id = dc.search_job_id
        LEFT JOIN LATERAL (
            SELECT sq3.query_text FROM search_queries sq3
            WHERE sq3.search_job_id = dc.search_job_id
            AND sq3.id = (
                SELECT sr2.source_query_id FROM search_results sr2
                WHERE sr2.domain = dc.domain AND sr2.search_job_id = dc.search_job_id
                AND sr2.source_query_id IS NOT NULL
                LIMIT 1
            )
            LIMIT 1
        ) sq2 ON sq.id IS NULL
        WHERE {' AND '.join(where_clauses)}
        ORDER BY dc.confidence DESC, dc.domain
    """)
    result = await db.execute(query, params)
    return result.fetchall()


def _build_source_details(row) -> str:
    """Build source details JSON from search query + raw_data."""
    import json
    details = {}

    if row.search_query:
        details["query"] = row.search_query

    if getattr(row, 'search_engine', None):
        details["engine"] = row.search_engine

    if row.raw_data:
        raw = row.raw_data if isinstance(row.raw_data, dict) else {}
        if isinstance(row.raw_data, str):
            try:
                raw = json.loads(row.raw_data)
            except Exception:
                raw = {}
        if row.source == "APOLLO":
            for k in ("organization", "seniority", "departments", "city", "country", "email_status"):
                if raw.get(k):
                    details[k] = raw[k]
        elif row.source == "WEBSITE_SCRAPE":
            if raw.get("is_generic"):
                details["generic_email"] = True

    if not details:
        return ""
    return json.dumps(details, ensure_ascii=False, default=str)


def _contacts_to_rows(rows) -> List[List[str]]:
    """Convert DB rows to list-of-lists (for CSV or Sheets)."""
    data = [CONTACTS_HEADERS]
    for r in rows:
        data.append([
            r.domain, r.url, r.company_name or "", r.description or "",
            r.industry or "", r.location or "", f"{(r.confidence or 0) * 100:.0f}%",
            r.reasoning or "",
            r.first_name or "", r.last_name or "", r.email or "", r.phone or "",
            r.job_title or "", r.linkedin_url or "", r.source or "",
            _build_source_details(r),
        ])
    return data


@router.get("/export-contacts-csv")
async def export_contacts_csv(
    project_id: Optional[int] = QueryParam(None),
    email_only: bool = QueryParam(False),
    phone_only: bool = QueryParam(False),
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Export contacts as CSV (one row per contact)."""
    rows = await _query_contacts(db, company.id, project_id, email_only, phone_only)
    data = _contacts_to_rows(rows)

    output = io.StringIO()
    writer = csv.writer(output)
    for row in data:
        writer.writerow(row)

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=contacts.csv"},
    )


@router.post("/export-contacts-sheet")
async def export_contacts_sheet(
    project_id: Optional[int] = QueryParam(None),
    email_only: bool = QueryParam(False),
    phone_only: bool = QueryParam(False),
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Export contacts to Google Sheets. Returns sheet URL."""
    from app.services.google_sheets_service import google_sheets_service

    rows = await _query_contacts(db, company.id, project_id, email_only, phone_only)
    if not rows:
        raise HTTPException(status_code=400, detail="No contacts to export")

    data = _contacts_to_rows(rows)

    # Build title with project name + timestamp
    proj_name = "All"
    if project_id:
        from sqlalchemy import text
        pq = await db.execute(text("SELECT name FROM projects WHERE id = :id"), {"id": project_id})
        prow = pq.fetchone()
        if prow:
            proj_name = prow.name

    filters = []
    if email_only:
        filters.append("email")
    if phone_only:
        filters.append("phone")
    filter_str = f" ({'+'.join(filters)})" if filters else ""
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    title = f"{proj_name} Contacts{filter_str} — {ts}"

    url = google_sheets_service.create_and_populate(
        title=title,
        data=data,
        share_with=["pn@getsally.io"],
    )
    if not url:
        raise HTTPException(status_code=500, detail="Google Sheets export failed")

    return {"url": url, "rows": len(data) - 1}
