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

from app.db import get_session
from app.api.companies import get_required_company
from app.models.user import Company
from app.schemas.pipeline import (
    DiscoveredCompanyResponse, DiscoveredCompanyDetail,
    ExtractedContactResponse, PipelineEventResponse,
    PipelineStats, SpendingDetail,
    ExtractContactsRequest, ApolloEnrichRequest,
    PromoteToContactsRequest, BulkStatusUpdateRequest,
    PipelineExportSheetRequest, PipelineExportSheetResponse,
)
from app.services.pipeline_service import pipeline_service

router = APIRouter(prefix="/pipeline", tags=["pipeline"])
logger = logging.getLogger(__name__)


# ============ Discovered Companies ============

@router.get("/discovered-companies")
async def list_discovered_companies(
    project_id: Optional[int] = QueryParam(None),
    status: Optional[str] = QueryParam(None),
    is_target: Optional[bool] = QueryParam(None),
    search: Optional[str] = QueryParam(None),
    sort_by: Optional[str] = QueryParam(None),
    sort_order: Optional[str] = QueryParam("desc"),
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
        sort_by=sort_by,
        sort_order=sort_order,
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

@router.post("/enrich-apollo")
async def enrich_apollo(
    body: ApolloEnrichRequest,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Run Apollo enrichment on selected discovered companies."""
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
    """Get pipeline stats for a project, including spending when project_id provided."""
    stats = await pipeline_service.get_pipeline_stats(
        session=db,
        company_id=company.id,
        project_id=project_id,
    )

    spending = None
    if project_id:
        try:
            from app.services.company_search_service import company_search_service
            raw = await company_search_service.get_project_spending(db, project_id)

            # Count Apollo enriched contacts for this project
            from sqlalchemy import select, func
            from app.models.pipeline import DiscoveredCompany
            apollo_q = await db.execute(
                select(func.sum(DiscoveredCompany.apollo_people_count))
                .where(
                    DiscoveredCompany.company_id == company.id,
                    DiscoveredCompany.project_id == project_id,
                    DiscoveredCompany.apollo_enriched_at.isnot(None),
                )
            )
            apollo_credits = apollo_q.scalar() or 0
            apollo_cost = apollo_credits * 0.01  # ~$0.01 per Apollo credit

            spending = SpendingDetail(
                yandex_cost=raw.get("yandex_cost", 0),
                openai_cost_estimate=raw.get("openai_cost_estimate", 0),
                gemini_cost_estimate=raw.get("gemini_cost_estimate", 0),
                ai_cost_estimate=raw.get("ai_cost_estimate", 0),
                crona_cost=raw.get("crona_cost", 0),
                apollo_credits_used=apollo_credits,
                apollo_cost_estimate=round(apollo_cost, 4),
                total_estimate=round(raw.get("total_estimate", 0) + apollo_cost, 4),
            )
        except Exception as e:
            logger.warning(f"Failed to get spending for project {project_id}: {e}")

    return PipelineStats(**stats, spending=spending)


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


@router.post("/export-sheet", response_model=PipelineExportSheetResponse)
async def export_google_sheet(
    body: PipelineExportSheetRequest,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Export discovered companies to a new Google Sheet."""
    from app.services.google_sheets_service import GoogleSheetsService
    from datetime import datetime as dt

    data = await pipeline_service.list_discovered_companies(
        session=db,
        company_id=company.id,
        project_id=body.project_id,
        is_target=body.is_target,
        page=1,
        page_size=10000,
    )

    headers = [
        "Domain", "Website", "Company Name", "Is Target", "Confidence", "Status",
        "Industry", "Services", "Location", "Description",
        "Contacts Count", "Emails", "Phones", "Apollo People", "Reasoning",
    ]
    rows = [headers]

    for dc in data["items"]:
        info = dc.company_info or {}
        services = ", ".join(info.get("services", [])) if info.get("services") else ""
        emails = ", ".join(dc.emails_found or [])
        phones = ", ".join(dc.phones_found or [])
        desc = info.get("description", "") or ""

        rows.append([
            dc.domain,
            f"https://{dc.domain}",
            dc.name or info.get("name", ""),
            "Yes" if dc.is_target else "No",
            f"{(dc.confidence or 0) * 100:.0f}%",
            dc.status.value if hasattr(dc.status, 'value') else str(dc.status),
            info.get("industry", ""),
            services,
            info.get("location", ""),
            desc[:200],
            dc.contacts_count or 0,
            emails,
            phones,
            dc.apollo_people_count or 0,
            (dc.reasoning or "")[:300],
        ])

    sheets_service = GoogleSheetsService()
    title = f"Pipeline Export — {dt.now().strftime('%Y-%m-%d %H:%M')}"
    try:
        sheet_url = sheets_service.create_and_populate(
            title=title,
            data=rows,
            share_with=["pn@getsally.io"],
        )
    except Exception as e:
        logger.error(f"Google Sheet export failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create Google Sheet: {str(e)}")

    if not sheet_url:
        raise HTTPException(status_code=500, detail="Failed to create Google Sheet (returned None)")

    return PipelineExportSheetResponse(sheet_url=sheet_url)


# ============ Auto-Enrich Config ============

@router.get("/auto-enrich-config/{project_id}")
async def get_auto_enrich_config(
    project_id: int,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Get auto-enrichment config for a project."""
    from app.models.contact import Project
    from sqlalchemy import select

    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.company_id == company.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return project.auto_enrich_config or {
        "auto_extract": True,
        "auto_apollo": False,
        "apollo_titles": ["CEO", "Founder", "Managing Director", "Owner"],
        "apollo_max_people": 5,
        "apollo_max_credits": 50,
    }


@router.put("/auto-enrich-config/{project_id}")
async def update_auto_enrich_config(
    project_id: int,
    body: dict,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Update auto-enrichment config for a project."""
    from app.models.contact import Project
    from sqlalchemy import select

    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.company_id == company.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Validate allowed keys
    allowed_keys = {"auto_extract", "auto_apollo", "apollo_titles", "apollo_max_people", "apollo_max_credits"}
    config = {k: v for k, v in body.items() if k in allowed_keys}
    project.auto_enrich_config = config
    await db.commit()
    return config
