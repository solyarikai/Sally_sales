"""Pipeline REST API — read-only endpoints for frontend, auth-required for writes."""
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db import get_session
from app.models.user import MCPUser
from app.models.project import Project, Company
from app.models.gathering import GatheringRun, ApprovalGate, CompanyScrape
from app.models.pipeline import DiscoveredCompany
from app.models.campaign import GeneratedSequence, Campaign
from app.auth.dependencies import get_current_user, get_optional_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


class ProjectCreateRequest(BaseModel):
    name: str
    target_segments: Optional[str] = None
    target_industries: Optional[str] = None
    sender_name: Optional[str] = None
    sender_company: Optional[str] = None
    sender_position: Optional[str] = None


@router.post("/projects")
async def create_project(
    req: ProjectCreateRequest,
    user: MCPUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Company).limit(1))
    company = result.scalar_one_or_none()
    if not company:
        company = Company(name=f"{user.name}'s Company")
        session.add(company)
        await session.flush()
    project = Project(
        company_id=company.id, user_id=user.id, name=req.name,
        target_segments=req.target_segments, target_industries=req.target_industries,
        sender_name=req.sender_name, sender_company=req.sender_company,
        sender_position=req.sender_position,
    )
    session.add(project)
    await session.flush()
    return {"project_id": project.id, "name": project.name}


@router.get("/projects")
async def list_projects(
    user: MCPUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Project).where(Project.user_id == user.id, Project.is_active == True)
    )
    return [{"id": p.id, "name": p.name, "target_segments": p.target_segments,
             "sender_name": p.sender_name, "sender_company": p.sender_company} for p in result.scalars().all()]


# ── Read-only endpoints (no auth required — shared via links) ──

@router.get("/runs/{run_id}")
async def get_run_status(
    run_id: int,
    session: AsyncSession = Depends(get_session),
):
    run = await session.get(GatheringRun, run_id)
    if not run:
        raise HTTPException(404, "Run not found")

    # Get project name
    project = await session.get(Project, run.project_id)

    # All gates for this run
    gates_result = await session.execute(
        select(ApprovalGate).where(ApprovalGate.gathering_run_id == run_id)
        .order_by(ApprovalGate.created_at)
    )
    all_gates = gates_result.scalars().all()

    # Count discovered companies
    dc_count = await session.execute(
        select(DiscoveredCompany.id).where(DiscoveredCompany.project_id == run.project_id)
    )
    total_companies = len(dc_count.all())

    # Count scrapes
    scrape_result = await session.execute(
        select(CompanyScrape.scrape_status)
        .join(DiscoveredCompany, DiscoveredCompany.id == CompanyScrape.discovered_company_id)
        .where(DiscoveredCompany.project_id == run.project_id)
    )
    scrapes = scrape_result.all()
    scraped_ok = sum(1 for s in scrapes if s[0] == "success")
    scraped_err = sum(1 for s in scrapes if s[0] != "success")

    return {
        "id": run.id,
        "status": run.status,
        "current_phase": run.current_phase,
        "source_type": run.source_type,
        "filters": run.filters,
        "project_name": project.name if project else "Unknown",
        "new_companies": run.new_companies_count,
        "duplicates": run.duplicate_count,
        "rejected": run.rejected_count,
        "total_companies": total_companies,
        "scraped_ok": scraped_ok,
        "scraped_errors": scraped_err,
        "target_rate": run.target_rate,
        "credits_used": run.credits_used,
        "created_at": str(run.created_at) if run.created_at else None,
        "gates": [
            {
                "gate_id": g.id,
                "type": g.gate_type,
                "label": g.gate_label,
                "status": g.status,
                "scope": g.scope,
                "decided_at": str(g.decided_at) if g.decided_at else None,
            }
            for g in all_gates
        ],
    }


@router.get("/runs/{run_id}/companies")
async def get_run_companies(
    run_id: int,
    session: AsyncSession = Depends(get_session),
):
    run = await session.get(GatheringRun, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    result = await session.execute(
        select(DiscoveredCompany).where(DiscoveredCompany.project_id == run.project_id)
        .order_by(DiscoveredCompany.domain)
    )
    companies = result.scalars().all()
    return [_company_to_dict(c) for c in companies]


def _company_to_dict(c):
    sd = c.source_data or {}
    return {
        "id": c.id, "domain": c.domain, "name": c.name,
        "industry": c.industry, "employee_count": c.employee_count,
        "employee_range": c.employee_range,
        "country": c.country, "city": c.city,
        "description": c.description, "linkedin_url": c.linkedin_url,
        # Apollo enrichment fields from source_data
        "revenue": sd.get("revenue") or sd.get("organization_revenue_printed"),
        "revenue_raw": sd.get("revenue_raw") or sd.get("organization_revenue"),
        "founded_year": sd.get("founded_year"),
        "phone": sd.get("phone") or sd.get("primary_phone"),
        "headcount_growth_6m": sd.get("headcount_6m_growth") or sd.get("organization_headcount_six_month_growth"),
        "headcount_growth_12m": sd.get("headcount_12m_growth") or sd.get("organization_headcount_twelve_month_growth"),
        "num_contacts_apollo": sd.get("num_contacts_in_apollo") or sd.get("num_contacts"),
        "website_url": c.website_url if hasattr(c, 'website_url') else sd.get("website_url"),
        # Pipeline state
        "is_blacklisted": c.is_blacklisted,
        "blacklist_reason": c.blacklist_reason,
        "is_pre_filtered": c.is_pre_filtered,
        "pre_filter_reason": c.pre_filter_reason,
        "is_target": c.is_target,
        "analysis_confidence": c.analysis_confidence,
        "analysis_segment": c.analysis_segment,
        "analysis_reasoning": c.analysis_reasoning,
        "is_enriched": c.is_enriched,
        "enrichment_source": c.enrichment_source,
        "source_data": sd,
    }


@router.get("/sequences/{seq_id}")
async def get_sequence(
    seq_id: int,
    session: AsyncSession = Depends(get_session),
):
    seq = await session.get(GeneratedSequence, seq_id)
    if not seq:
        raise HTTPException(404, "Sequence not found")
    project = await session.get(Project, seq.project_id)
    return {
        "id": seq.id,
        "campaign_name": seq.campaign_name,
        "status": seq.status,
        "steps": seq.sequence_steps,
        "step_count": seq.sequence_step_count,
        "rationale": seq.rationale,
        "project_name": project.name if project else None,
        "pushed_at": str(seq.pushed_at) if seq.pushed_at else None,
        "model_used": seq.model_used,
    }


@router.get("/runs")
async def list_runs(
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(GatheringRun).order_by(GatheringRun.created_at.desc()).limit(20)
    )
    runs = result.scalars().all()
    return [
        {"id": r.id, "status": r.status, "phase": r.current_phase,
         "source_type": r.source_type, "new_companies": r.new_companies_count,
         "created_at": str(r.created_at)}
        for r in runs
    ]


# ── CRM: all companies across all pipelines ──

@router.get("/crm/companies")
async def crm_companies(
    project_id: int = None,
    is_target: bool = None,
    session: AsyncSession = Depends(get_session),
):
    query = select(DiscoveredCompany).order_by(DiscoveredCompany.domain)
    if project_id:
        query = query.where(DiscoveredCompany.project_id == project_id)
    if is_target is not None:
        query = query.where(DiscoveredCompany.is_target == is_target)
    result = await session.execute(query.limit(500))
    companies = result.scalars().all()
    return [_company_to_dict(c) for c in companies]


@router.get("/crm/contacts")
async def crm_contacts(
    project_id: int = None,
    search: str = None,
    status: str = None,
    session: AsyncSession = Depends(get_session),
):
    """CRM contacts view — people extracted from pipeline."""
    from app.models.pipeline import ExtractedContact
    query = select(ExtractedContact).order_by(ExtractedContact.created_at.desc())
    if project_id:
        query = query.where(ExtractedContact.project_id == project_id)
    if search:
        query = query.where(
            (ExtractedContact.email.ilike(f"%{search}%")) |
            (ExtractedContact.first_name.ilike(f"%{search}%")) |
            (ExtractedContact.last_name.ilike(f"%{search}%"))
        )
    result = await session.execute(query.limit(500))
    contacts = result.scalars().all()
    return {
        "contacts": [
            {
                "id": c.id,
                "first_name": c.first_name,
                "last_name": c.last_name,
                "email": c.email,
                "job_title": c.job_title,
                "linkedin_url": c.linkedin_url,
                "phone": c.phone,
                "email_verified": c.email_verified,
                "email_source": c.email_source,
                "domain": None,  # TODO: join with discovered_company
                "company_name": None,
                "source_data": c.source_data,
                "created_at": str(c.created_at) if c.created_at else None,
            }
            for c in contacts
        ],
        "total": len(contacts),
    }
