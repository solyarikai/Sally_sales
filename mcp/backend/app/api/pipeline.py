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


async def _get_user_project_ids(user, session) -> list[int]:
    """Get all project IDs owned by this user."""
    result = await session.execute(
        select(Project.id).where(Project.user_id == user.id, Project.is_active == True)
    )
    return [pid for (pid,) in result.all()]


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
    user: MCPUser = Depends(get_optional_user),
    session: AsyncSession = Depends(get_session),
):
    query = select(Project).where(Project.is_active == True)
    if user:
        query = query.where(Project.user_id == user.id)
    result = await session.execute(query)
    return [{"id": p.id, "name": p.name, "target_segments": p.target_segments,
             "sender_name": p.sender_name, "sender_company": p.sender_company,
             "campaign_filters": p.campaign_filters or []} for p in result.scalars().all()]


# ── Read-only endpoints (no auth required — shared via links) ──

@router.get("/runs/{run_id}")
async def get_run_status(
    run_id: int,
    user: MCPUser = Depends(get_optional_user),
    session: AsyncSession = Depends(get_session),
):
    run = await session.get(GatheringRun, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    # User-scope: verify run belongs to user's project
    if user:
        project = await session.get(Project, run.project_id)
        if project and project.user_id != user.id:
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

    # Find SmartLead campaign created from this pipeline
    campaign_info = None
    seq_result = await session.execute(
        select(GeneratedSequence).where(
            GeneratedSequence.project_id == run.project_id,
            GeneratedSequence.pushed_campaign_id.isnot(None),
        ).order_by(GeneratedSequence.pushed_at.desc()).limit(1)
    )
    seq = seq_result.scalar_one_or_none()
    if seq and seq.pushed_campaign_id:
        campaign = await session.get(Campaign, seq.pushed_campaign_id)
        if campaign and campaign.external_id:
            campaign_info = {
                "id": campaign.id,
                "name": campaign.name,
                "smartlead_id": campaign.external_id,
                "smartlead_url": f"https://app.smartlead.ai/app/email-campaigns-v2/{campaign.external_id}/analytics",
                "status": campaign.status,
            }

    return {
        "id": run.id,
        "status": run.status,
        "current_phase": run.current_phase,
        "source_type": run.source_type,
        "filters": run.filters,
        "project_id": run.project_id,
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
        "campaign": campaign_info,
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
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
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
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    rows = result.all()

    # Total count for pagination
    total_result = await session.execute(
        select(sa_func.count(DiscoveredCompany.id))
        .where(DiscoveredCompany.project_id == run.project_id)
    )
    total_companies = total_result.scalar() or 0

    # Count contacts per company
    from app.models.pipeline import ExtractedContact
    contact_counts: dict = {}
    cc_result = await session.execute(
        select(ExtractedContact.discovered_company_id, sa_func.count(ExtractedContact.id))
        .where(ExtractedContact.project_id == run.project_id)
        .group_by(ExtractedContact.discovered_company_id)
    )
    for dc_id, cnt in cc_result.all():
        contact_counts[dc_id] = cnt

    # Check if any targets exist (to signal frontend to show contacts column)
    has_targets = any(c.is_target for c, _ in rows)

    companies = [_company_to_dict(c, scrape=s, truncate_reasoning=True, contacts_count=contact_counts.get(c.id, 0)) for c, s in rows]
    return {
        "companies": companies,
        "has_targets": has_targets,
        "total_contacts": sum(contact_counts.values()),
        "total_companies": total_companies,
        "page": page,
        "page_size": page_size,
    }


@router.get("/companies/{company_id}")
async def get_company_detail(
    company_id: int,
    user: MCPUser = Depends(get_optional_user),
    session: AsyncSession = Depends(get_session),
):
    """Full detail for a single company — user-scoped."""
    company = await session.get(DiscoveredCompany, company_id)
    if not company:
        raise HTTPException(404, "Company not found")
    if user:
        project = await session.get(Project, company.project_id)
        if project and project.user_id != user.id:
            raise HTTPException(404, "Company not found")
    return await _get_company_detail(company, session)


@router.get("/runs/{run_id}/companies/{company_id}")
async def get_run_company_detail(
    run_id: int,
    company_id: int,
    user: MCPUser = Depends(get_optional_user),
    session: AsyncSession = Depends(get_session),
):
    """Full detail for a single company scoped to a run — user-scoped."""
    run = await session.get(GatheringRun, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    if user:
        project = await session.get(Project, run.project_id)
        if project and project.user_id != user.id:
            raise HTTPException(404, "Run not found")

    company = await session.get(DiscoveredCompany, company_id)
    if not company or company.project_id != run.project_id:
        raise HTTPException(404, "Company not found in this run's project")

    return await _get_company_detail(company, session)


async def _get_company_detail(company, session):
    """Full company detail with scrape text and raw source data."""
    # Get current scrape
    scrape_result = await session.execute(
        select(CompanyScrape)
        .where(
            CompanyScrape.discovered_company_id == company.id,
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
    user: MCPUser = Depends(get_optional_user),
):
    """List gathering runs (iterations) scoped to user's projects."""
    query = select(GatheringRun).order_by(GatheringRun.created_at.desc())
    if user:
        user_projects = await session.execute(select(Project.id).where(Project.user_id == user.id))
        pids = [pid for (pid,) in user_projects.all()]
        if pids:
            query = query.where(GatheringRun.project_id.in_(pids))
        else:
            return []
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
    user: MCPUser = Depends(get_optional_user),
    session: AsyncSession = Depends(get_session),
):
    """Return MCP usage logs — user-scoped."""
    query = select(MCPUsageLog).order_by(MCPUsageLog.created_at.desc())
    if user:
        query = query.where(MCPUsageLog.user_id == user.id)

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


# SIC codes → human labels (4-digit for precision, 2-digit as fallback)
_SIC = {
    "7371": "Computer Programming", "7372": "Software", "7374": "Data Processing",
    "7375": "Computer Facilities Management", "7376": "Computer Maintenance",
    "7378": "Computer Maintenance", "7379": "Computer Services",
    "7361": "Staffing & Recruiting", "7363": "Staffing & Recruiting",
    "73": "IT & Business Services", "72": "Computer Services", "48": "Communications",
    "36": "Electronics", "35": "Industrial Equipment", "38": "Instruments",
    "50": "Wholesale", "59": "Retail", "60": "Banking", "61": "Credit",
    "62": "Securities", "63": "Insurance", "65": "Real Estate",
    "80": "Healthcare", "82": "Education", "87": "Engineering & Management",
    "27": "Publishing", "49": "Utilities", "15": "Construction",
}

# NAICS codes → human labels (5-digit for precision, 3-digit as fallback)
_NAICS = {
    "54151": "Computer Systems Design", "54161": "Management Consulting",
    "54171": "Scientific R&D", "54131": "Architectural Services",
    "54111": "Legal Services", "54121": "Accounting",
    "51121": "Software Publishing", "51913": "Internet Publishing",
    "51821": "Data Processing & Hosting", "51911": "News Syndicates",
    "54169": "Management & Technical Consulting",
    "51611": "Internet Publishing", "51711": "Wired Telecom",
    "54181": "Advertising", "56132": "Staffing & Recruiting",
    "511": "Software & Publishing", "518": "Data & Hosting", "519": "Web & Search",
    "541": "Professional Services", "561": "Business Support", "517": "Telecom",
    "522": "Banking", "523": "Securities", "524": "Insurance", "531": "Real Estate",
    "611": "Education", "621": "Healthcare", "512": "Media", "334": "Electronics",
    "454": "E-Commerce",
}


def _company_to_dict(c, scrape=None, truncate_reasoning=False, contacts_count=0):
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
        "industry": c.industry,
        "employee_count": c.employee_count,
        "employee_count_note": "Apollo contacts (not actual headcount)" if c.employee_count and c.employee_count < 50 else None,
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
        # Contacts/people status
        "contacts_count": contacts_count,
        "contacts_status": "found" if contacts_count > 0 else ("gathering" if c.is_enriched else None),
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
    user: MCPUser = Depends(get_optional_user),
):
    query = select(GatheringRun).order_by(GatheringRun.created_at.desc()).limit(20)
    # User-scope: only show runs from user's projects
    if user:
        from app.models.project import Project
        user_projects = await session.execute(select(Project.id).where(Project.user_id == user.id))
        pids = [pid for (pid,) in user_projects.all()]
        if pids:
            query = query.where(GatheringRun.project_id.in_(pids))
        else:
            return []
    result = await session.execute(query)
    runs = result.scalars().all()
    return [
        {"id": r.id, "status": r.status, "phase": r.current_phase,
         "source_type": r.source_type, "new_companies": r.new_companies_count,
         "credits_used": r.credits_used or 0,
         "target_rate": f"{(r.target_rate or 0)*100:.0f}%" if r.target_rate else None,
         "created_at": str(r.created_at)}
        for r in runs
    ]


# ── Deep links helper ──

@router.get("/deep-links")
async def get_deep_links(
    project_id: int = Query(...),
    session: AsyncSession = Depends(get_session),
):
    """Generate CRM/Tasks deep links for a project."""
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    base = "/tasks"
    crm_base = "/crm"
    name = project.name
    return {
        "all_replies": f"{base}?project={name}",
        "warm_replies": f"{base}?project={name}&category=interested",
        "meetings": f"{base}?project={name}&tab=meetings",
        "questions": f"{base}?project={name}&tab=questions",
        "followups": f"{base}?project={name}&tab=follow-ups",
        "crm_all": f"{crm_base}?project_id={project_id}",
        "crm_targets": f"{crm_base}?project_id={project_id}&is_target=true",
        "pipeline": f"/pipeline",
        "projects": f"/projects",
    }


# ── Gate approval + pipeline actions (auth required) ──


class GateApprovalRequest(BaseModel):
    notes: Optional[str] = None


@router.post("/gates/{gate_id}/approve")
async def approve_gate(
    gate_id: int,
    req: GateApprovalRequest = GateApprovalRequest(),
    user: MCPUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Approve an approval gate (checkpoint)."""
    from datetime import datetime, timezone
    gate = await session.get(ApprovalGate, gate_id)
    if not gate:
        raise HTTPException(404, "Gate not found")
    if gate.status != "pending":
        raise HTTPException(400, f"Gate already {gate.status}")
    gate.status = "approved"
    gate.decided_at = datetime.now(timezone.utc)
    if req.notes:
        gate.scope = {**(gate.scope or {}), "approval_notes": req.notes}

    # Advance the run phase
    run = await session.get(GatheringRun, gate.gathering_run_id)
    if run:
        phase_map = {
            "awaiting_scope_ok": "pre_filter",
            "awaiting_targets_ok": "prepare_verification",
            "awaiting_verify_ok": "verified",
        }
        if run.current_phase in phase_map:
            run.current_phase = phase_map[run.current_phase]

    await session.commit()
    return {"gate_id": gate_id, "status": "approved", "run_phase": run.current_phase if run else None}


@router.post("/runs/{run_id}/generate-sequence")
async def generate_sequence(
    run_id: int,
    user: MCPUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Generate email sequence for a pipeline run."""
    from app.services.campaign_intelligence import CampaignIntelligenceService
    run = await session.get(GatheringRun, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    svc = CampaignIntelligenceService()
    result = await svc.generate_sequence(session, run_id=run_id, project_id=run.project_id)
    await session.commit()
    return result


@router.post("/runs/{run_id}/create-campaign")
async def create_campaign(
    run_id: int,
    user: MCPUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Create SmartLead campaign from pipeline run."""
    from app.services.campaign_intelligence import CampaignIntelligenceService
    run = await session.get(GatheringRun, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    svc = CampaignIntelligenceService()
    result = await svc.push_to_smartlead(session, run_id=run_id, project_id=run.project_id)
    await session.commit()
    return result


class SendTestEmailRequest(BaseModel):
    test_email: str = "pn@getsally.io"
    sequence_number: int = 1


@router.post("/runs/{run_id}/send-test-email")
async def send_test_email(
    run_id: int,
    req: SendTestEmailRequest = SendTestEmailRequest(),
    user: MCPUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Send a test email via SmartLead's native send-test-email API.

    Uses the proper API: POST /campaigns/{id}/send-test-email with
    leadId + sequenceNumber + selectedEmailAccountId + customEmailAddress.
    """
    from app.services.smartlead_service import SmartLeadService

    run = await session.get(GatheringRun, run_id)
    if not run:
        raise HTTPException(404, "Run not found")

    # Find the generated sequence that was pushed for this run
    seq_result = await session.execute(
        select(GeneratedSequence).where(
            GeneratedSequence.project_id == run.project_id,
            GeneratedSequence.pushed_campaign_id.isnot(None),
        ).order_by(GeneratedSequence.pushed_at.desc()).limit(1)
    )
    seq = seq_result.scalar_one_or_none()

    if not seq or not seq.pushed_campaign_id:
        raise HTTPException(400, "No SmartLead campaign found for this run. Create a campaign first.")

    campaign = await session.get(Campaign, seq.pushed_campaign_id)
    if not campaign or not campaign.external_id:
        raise HTTPException(400, "Campaign has no SmartLead ID")

    smartlead_campaign_id = int(campaign.external_id)
    sl = SmartLeadService()

    if not sl.is_configured():
        raise HTTPException(500, "SmartLead API key not configured")

    # Use native SmartLead send-test-email API (auto-resolves account + lead)
    result = await sl.send_test_email(
        campaign_id=smartlead_campaign_id,
        test_email=req.test_email,
        sequence_number=req.sequence_number,
    )

    return {
        "campaign_name": campaign.name,
        "smartlead_campaign_id": smartlead_campaign_id,
        **result,
    }


# ── CRM: all companies across all pipelines ──

@router.get("/crm/companies")
async def crm_companies(
    project_id: int = None,
    is_target: bool = None,
    user: MCPUser = Depends(get_optional_user),
    session: AsyncSession = Depends(get_session),
):
    query = select(DiscoveredCompany).order_by(DiscoveredCompany.domain)
    # User-scope: only show companies from user's projects
    if user:
        user_pids = await _get_user_project_ids(user, session)
        query = query.where(DiscoveredCompany.project_id.in_(user_pids))
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
    pipeline: int = None,
    search: str = None,
    user: MCPUser = Depends(get_optional_user),
    session: AsyncSession = Depends(get_session),
):
    """CRM contacts view — people extracted from pipeline. Filter by pipeline run ID."""
    from app.models.pipeline import ExtractedContact

    # JOIN with DiscoveredCompany to get company info + pipeline run link
    stmt = (
        select(ExtractedContact, DiscoveredCompany)
        .outerjoin(DiscoveredCompany, DiscoveredCompany.id == ExtractedContact.discovered_company_id)
        .order_by(ExtractedContact.created_at.desc())
    )

    # User-scope
    if user:
        user_pids = await _get_user_project_ids(user, session)
        stmt = stmt.where(ExtractedContact.project_id.in_(user_pids))

    if project_id:
        stmt = stmt.where(ExtractedContact.project_id == project_id)

    if pipeline:
        # Filter to contacts whose company was gathered in this pipeline run
        stmt = stmt.where(
            DiscoveredCompany.id.in_(
                select(CompanySourceLink.discovered_company_id)
                .where(CompanySourceLink.gathering_run_id == pipeline)
            )
        )

    if search:
        stmt = stmt.where(
            (ExtractedContact.email.ilike(f"%{search}%")) |
            (ExtractedContact.first_name.ilike(f"%{search}%")) |
            (ExtractedContact.last_name.ilike(f"%{search}%"))
        )

    result = await session.execute(stmt.limit(500))
    rows = result.all()

    contacts = []
    for contact, company in rows:
        # Find pipeline run IDs for this company
        run_ids = []
        if company:
            links = await session.execute(
                select(CompanySourceLink.gathering_run_id)
                .where(CompanySourceLink.discovered_company_id == company.id)
            )
            run_ids = [r[0] for r in links.all()]

        contacts.append({
            "id": contact.id,
            "first_name": contact.first_name,
            "last_name": contact.last_name,
            "email": contact.email,
            "job_title": contact.job_title,
            "linkedin_url": contact.linkedin_url,
            "phone": contact.phone,
            "email_verified": contact.email_verified,
            "email_source": contact.email_source,
            "domain": company.domain if company else None,
            "company_name": company.name if company else None,
            "industry": company.industry if company else None,
            "country": company.country if company else None,
            "pipeline_run_ids": run_ids,
            "created_at": str(contact.created_at) if contact.created_at else None,
        })

    return {"contacts": contacts, "total": len(contacts)}
