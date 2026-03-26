"""Pipeline REST API — read-only endpoints for frontend, auth-required for writes."""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func as sa_func, outerjoin

from app.db import get_session
from app.models.user import MCPUser
from app.models.project import Project, Company
from app.models.gathering import GatheringRun, ApprovalGate, CompanyScrape, CompanySourceLink
from app.models.pipeline import DiscoveredCompany
from app.models.campaign import GeneratedSequence, Campaign
from app.models.usage import MCPUsageLog
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

    # LEFT JOIN with company_scrapes to get scrape info per company
    stmt = (
        select(DiscoveredCompany, CompanyScrape)
        .outerjoin(
            CompanyScrape,
            (CompanyScrape.discovered_company_id == DiscoveredCompany.id)
            & (CompanyScrape.is_current == True),
        )
        .where(DiscoveredCompany.project_id == run.project_id)
        .order_by(DiscoveredCompany.domain)
    )
    result = await session.execute(stmt)
    rows = result.all()
    return [_company_to_dict(c, scrape=s, truncate_reasoning=True) for c, s in rows]


@router.get("/runs/{run_id}/companies/{company_id}")
async def get_run_company_detail(
    run_id: int,
    company_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Full detail for a single company — includes full scrape text, full reasoning, raw source_data."""
    run = await session.get(GatheringRun, run_id)
    if not run:
        raise HTTPException(404, "Run not found")

    company = await session.get(DiscoveredCompany, company_id)
    if not company or company.project_id != run.project_id:
        raise HTTPException(404, "Company not found in this run's project")

    # Get current scrape
    scrape_result = await session.execute(
        select(CompanyScrape)
        .where(
            CompanyScrape.discovered_company_id == company_id,
            CompanyScrape.is_current == True,
        )
        .limit(1)
    )
    scrape = scrape_result.scalar_one_or_none()

    data = _company_to_dict(company, scrape=scrape, truncate_reasoning=False)

    # Add full detail fields
    if scrape:
        data["scrape_text"] = scrape.clean_text
        data["scrape_error"] = scrape.error_message
        data["scrape_http_code"] = scrape.http_status_code
        data["scrape_timestamp"] = str(scrape.scraped_at) if scrape.scraped_at else None
    else:
        data["scrape_text"] = None
        data["scrape_error"] = None
        data["scrape_http_code"] = None
        data["scrape_timestamp"] = None

    # Full source_data (already included but explicitly confirm it's not stripped)
    data["source_data"] = company.source_data or {}

    return data


@router.get("/iterations")
async def list_iterations(
    project_id: Optional[int] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """List all gathering runs (iterations) with target counts for the pipeline page."""
    query = select(GatheringRun).order_by(GatheringRun.created_at.desc())
    if project_id is not None:
        query = query.where(GatheringRun.project_id == project_id)
    query = query.limit(50)

    result = await session.execute(query)
    runs = result.scalars().all()

    iterations = []
    for r in runs:
        # Count targets for this run's project that were discovered in this run
        target_count_result = await session.execute(
            select(sa_func.count(DiscoveredCompany.id))
            .join(
                CompanySourceLink,
                CompanySourceLink.discovered_company_id == DiscoveredCompany.id,
            )
            .where(
                CompanySourceLink.gathering_run_id == r.id,
                DiscoveredCompany.is_target == True,
            )
        )
        target_count = target_count_result.scalar() or 0

        # Get project name
        project = await session.get(Project, r.project_id)

        iterations.append({
            "id": r.id,
            "source_type": r.source_type,
            "filters": r.filters,
            "new_companies_count": r.new_companies_count,
            "current_phase": r.current_phase,
            "status": r.status,
            "target_count": target_count,
            "project_id": r.project_id,
            "project_name": project.name if project else "Unknown",
            "created_at": str(r.created_at) if r.created_at else None,
        })

    return iterations


@router.get("/usage-logs")
async def get_usage_logs(
    run_id: Optional[int] = Query(None),
    limit: int = Query(100, le=500),
    session: AsyncSession = Depends(get_session),
):
    """Return MCP usage logs, optionally filtered by run_id in metadata."""
    query = select(MCPUsageLog).order_by(MCPUsageLog.created_at.desc())

    if run_id is not None:
        # Filter logs where extra_data contains the run_id
        query = query.where(
            MCPUsageLog.extra_data["run_id"].as_integer() == run_id
        )

    query = query.limit(limit)
    result = await session.execute(query)
    logs = result.scalars().all()

    return [
        {
            "id": log.id,
            "user_id": log.user_id,
            "action": log.action,
            "tool_name": log.tool_name,
            "metadata": log.extra_data,
            "created_at": str(log.created_at) if log.created_at else None,
        }
        for log in logs
    ]


def _compute_company_status(c, scrape=None):
    """Derive a single status string from the company's pipeline state flags."""
    if c.is_blacklisted:
        return "blacklisted"
    if c.is_pre_filtered:
        return "filtered"
    # Check scrape state
    if scrape:
        if scrape.scrape_status != "success":
            return "scrape_failed"
    # Check analysis state
    if c.is_target is True:
        if c.is_enriched:
            return "verified"
        return "target"
    if c.is_target is False:
        return "rejected"
    # is_target is None — analysis hasn't run yet
    if scrape and scrape.scrape_status == "success":
        return "scraped"
    # No scrape yet, not blacklisted, not filtered
    return "gathered"


# SIC code prefixes → human labels
_SIC = {
    "73": "IT Services", "72": "Computer Services", "48": "Communications",
    "36": "Electronics", "35": "Industrial Equipment", "38": "Instruments",
    "50": "Wholesale", "59": "Retail", "60": "Banking", "61": "Credit",
    "62": "Securities", "63": "Insurance", "65": "Real Estate",
    "80": "Healthcare", "82": "Education", "87": "Engineering & Management",
    "27": "Publishing", "49": "Utilities", "15": "Construction",
    "20": "Food Processing", "28": "Chemicals", "37": "Transportation Equipment",
}

# NAICS code prefixes → human labels
_NAICS = {
    "511": "Software Publishing", "518": "Data & Hosting", "519": "Web & Search",
    "541": "Professional Services", "561": "Business Support", "517": "Telecom",
    "522": "Banking", "523": "Securities", "524": "Insurance", "531": "Real Estate",
    "611": "Education", "621": "Healthcare", "512": "Media", "334": "Electronics",
    "336": "Transportation Mfg", "325": "Chemicals", "423": "Wholesale Tech",
    "454": "E-Commerce", "236": "Construction", "333": "Machinery",
}


def _company_to_dict(c, scrape=None, truncate_reasoning=False):
    sd = c.source_data or {}

    # Build apollo_url if apollo_id present
    apollo_id = sd.get("apollo_id") or sd.get("organization_id") or sd.get("id")
    apollo_url = None
    if apollo_id:
        apollo_url = f"https://app.apollo.io/#/organizations/{apollo_id}"

    # Keywords: translate SIC/NAICS codes to human labels
    keywords = sd.get("keywords") or sd.get("tags") or sd.get("keyword_tags") or []
    if isinstance(keywords, str):
        keywords = [k.strip() for k in keywords.split(",") if k.strip()]
    if not keywords:
        parts = []
        for code in (sd.get("sic_codes") or []):
            parts.append(_SIC.get(str(code)[:2], str(code)))
        for code in (sd.get("naics_codes") or []):
            parts.append(_NAICS.get(str(code)[:3], str(code)))
        # Deduplicate and remove empties
        seen = set()
        keywords = []
        for p in parts:
            if p and p not in seen:
                seen.add(p)
                keywords.append(p)
        keywords = ", ".join(keywords) if keywords else ""

    reasoning = c.analysis_reasoning
    if truncate_reasoning and reasoning and len(reasoning) > 100:
        reasoning = reasoning[:100] + "..."

    result = {
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
        # New fields for pipeline page
        "status": _compute_company_status(c, scrape),
        "keywords": keywords,
        "apollo_url": apollo_url,
        # Scrape info (from JOIN)
        "scrape_status": scrape.scrape_status if scrape else None,
        "scrape_text_size": scrape.text_size_bytes if scrape else None,
        "scrape_text_preview": (scrape.clean_text[:150] + "...") if scrape and scrape.clean_text and len(scrape.clean_text) > 150 else (scrape.clean_text if scrape else None),
        # Analysis
        "analysis_reasoning": reasoning,
        # Pipeline state
        "is_blacklisted": c.is_blacklisted,
        "blacklist_reason": c.blacklist_reason,
        "is_pre_filtered": c.is_pre_filtered,
        "pre_filter_reason": c.pre_filter_reason,
        "is_target": c.is_target,
        "analysis_confidence": c.analysis_confidence,
        "analysis_segment": c.analysis_segment,
        "is_enriched": c.is_enriched,
        "enrichment_source": c.enrichment_source,
        "source_data": sd,
    }
    return result


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
