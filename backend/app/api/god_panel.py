"""
God Panel API — Campaign Intelligence Dashboard.

Endpoints for monitoring campaign discovery, resolution, and assignment.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, and_, func, desc, case, literal_column
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session, async_session_maker
from app.models.campaign import Campaign
from app.models.contact import Project
from app.models.learning import LearningLog

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/god-panel", tags=["God Panel"])


# ─── Response schemas ──────────────────────────────────────────

class CampaignOut(BaseModel):
    id: int
    name: str
    platform: str
    channel: str
    external_id: Optional[str] = None
    project_id: Optional[int] = None
    project_name: Optional[str] = None
    status: Optional[str] = None
    resolution_method: Optional[str] = None
    resolution_detail: Optional[str] = None
    first_seen_at: Optional[datetime] = None
    acknowledged: bool = False
    replied_count: Optional[int] = 0
    leads_count: Optional[int] = 0
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AssignRequest(BaseModel):
    project_id: int


class RuleFeedbackRequest(BaseModel):
    feedback_text: str


class ProjectRulesOut(BaseModel):
    project_id: int
    project_name: str
    rules: List[str]


class CampaignAuditLogOut(BaseModel):
    id: int
    action: str
    campaign_name: Optional[str] = None
    source: str
    learning_log_id: Optional[int] = None
    details: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class StatsOut(BaseModel):
    total_campaigns: int
    smartlead_campaigns: int
    getsales_campaigns: int
    unresolved_count: int
    unacknowledged_count: int
    assignment_rate: float
    reply_volume_7d: int
    reply_volume_30d: int
    newest_campaign: Optional[str] = None
    newest_campaign_at: Optional[datetime] = None


class ProjectMetric(BaseModel):
    project_id: int
    project_name: str
    contacts_uploaded: int = 0
    warm_replies: int = 0


class ProjectMetricsOut(BaseModel):
    projects: List[ProjectMetric]
    period: str


# ─── Endpoints ─────────────────────────────────────────────────

@router.get("/campaigns/", response_model=List[CampaignOut])
async def list_campaigns(
    platform: Optional[str] = Query(None, description="Filter by platform: smartlead, getsales"),
    unresolved: Optional[bool] = Query(None, description="Only unresolved campaigns (no project)"),
    unacknowledged: Optional[bool] = Query(None, description="Only unacknowledged campaigns"),
    project_id: Optional[int] = Query(None, description="Filter by project"),
    since: Optional[str] = Query(None, description="ISO date — campaigns first seen after this date"),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
):
    """List all campaigns with optional filters."""
    query = select(Campaign, Project.name.label("project_name")).outerjoin(
        Project, Campaign.project_id == Project.id
    )

    filters = []
    if platform:
        filters.append(Campaign.platform == platform)
    if unresolved:
        filters.append(Campaign.project_id.is_(None))
    if unacknowledged:
        filters.append(Campaign.acknowledged == False)
    if project_id:
        filters.append(Campaign.project_id == project_id)
    if since:
        try:
            since_dt = datetime.fromisoformat(since)
            filters.append(Campaign.first_seen_at >= since_dt)
        except ValueError:
            pass

    if filters:
        query = query.where(and_(*filters))

    query = query.order_by(desc(Campaign.first_seen_at), desc(Campaign.created_at))
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await session.execute(query)
    rows = result.all()

    return [
        CampaignOut(
            id=campaign.id,
            name=campaign.name,
            platform=campaign.platform,
            channel=campaign.channel,
            external_id=campaign.external_id,
            project_id=campaign.project_id,
            project_name=project_name,
            status=campaign.status,
            resolution_method=campaign.resolution_method,
            resolution_detail=campaign.resolution_detail,
            first_seen_at=campaign.first_seen_at,
            acknowledged=campaign.acknowledged or False,
            replied_count=campaign.replied_count or 0,
            leads_count=campaign.leads_count or 0,
            created_at=campaign.created_at,
        )
        for campaign, project_name in rows
    ]


@router.post("/campaigns/{campaign_id}/acknowledge")
async def acknowledge_campaign(
    campaign_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Mark a campaign as reviewed by operator."""
    result = await session.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar()
    if not campaign:
        raise HTTPException(404, "Campaign not found")

    campaign.acknowledged = True
    await session.commit()
    return {"ok": True, "campaign_id": campaign_id}


@router.post("/campaigns/{campaign_id}/assign")
async def assign_campaign(
    campaign_id: int,
    body: AssignRequest,
    session: AsyncSession = Depends(get_session),
):
    """Assign a campaign to a project. Also adds to project's campaign_filters."""
    result = await session.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar()
    if not campaign:
        raise HTTPException(404, "Campaign not found")

    # Validate project exists
    proj_result = await session.execute(
        select(Project).where(Project.id == body.project_id, Project.deleted_at.is_(None))
    )
    project = proj_result.scalar()
    if not project:
        raise HTTPException(404, "Project not found")

    # Update campaign
    campaign.project_id = project.id
    campaign.resolution_method = "manual"
    campaign.resolution_detail = f"Manually assigned to '{project.name}' via God Panel"
    campaign.acknowledged = True

    # Add to project's campaign_filters if not already there
    existing_filters = project.campaign_filters or []
    existing_lower = {f.lower() for f in existing_filters if isinstance(f, str)}
    if campaign.name.lower() not in existing_lower:
        new_filters = existing_filters + [campaign.name]
        project.campaign_filters = new_filters
        logger.info(f"[GOD_PANEL] Added '{campaign.name}' to project '{project.name}' campaign_filters")

        # Audit log
        from app.models.campaign_audit_log import CampaignAuditLog
        session.add(CampaignAuditLog(
            project_id=project.id, action="add", campaign_name=campaign.name,
            source="god_panel", details=f"Assigned via God Panel (campaign #{campaign_id})",
            campaigns_before=existing_filters, campaigns_after=new_filters,
        ))

    await session.commit()
    return {
        "ok": True,
        "campaign_id": campaign_id,
        "project_id": project.id,
        "project_name": project.name,
    }


@router.get("/projects/{project_id}/rules", response_model=ProjectRulesOut)
async def get_project_rules(
    project_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get computed assignment rules for a project."""
    result = await session.execute(
        select(Project).where(Project.id == project_id, Project.deleted_at.is_(None))
    )
    project = result.scalar()
    if not project:
        raise HTTPException(404, "Project not found")

    rules = []
    ownership = project.campaign_ownership_rules or {}

    # 1. Ownership rules (replaces hardcoded _PROJECT_PREFIXES)
    rule_prefixes = ownership.get("prefixes", [])
    rule_contains = ownership.get("contains", [])
    rule_tags = ownership.get("smartlead_tags", [])
    if rule_prefixes:
        rules.append(f"Prefix match: campaigns starting with {', '.join(repr(p) for p in rule_prefixes)}")
    if rule_contains:
        rules.append(f"Contains match: campaigns containing {', '.join(repr(s) for s in rule_contains)}")
    if rule_tags:
        rules.append(f"SmartLead tag match: {', '.join(repr(t) for t in rule_tags)}")

    # 2. Campaign filters
    filters = project.campaign_filters or []
    if filters:
        if len(filters) <= 5:
            rules.append(f"Explicit campaign filters: {', '.join(filters)}")
        else:
            rules.append(f"Explicit campaign filters: {len(filters)} campaigns ({', '.join(filters[:3])}, ...)")

    # 4. GetSales senders — resolve UUIDs to human names
    senders = project.getsales_senders or []
    if senders:
        try:
            from app.services.crm_sync_service import GETSALES_SENDER_PROFILES
            sender_names = [GETSALES_SENDER_PROFILES.get(s, s[:8]) for s in senders if isinstance(s, str)]
        except ImportError:
            sender_names = [s[:8] for s in senders]
        rules.append(f"LinkedIn senders: {', '.join(sender_names)}")

    # 5. Project name prefix (implicit)
    project_name_lower = (project.name or "").lower()
    if project_name_lower and len(project_name_lower) >= 4:
        rules.append(f"Implicit name prefix match: campaigns starting with '{project.name}'")

    # 6. Monitoring schedule
    rules.append("Monitoring: new campaigns checked every ~30 min, replies polled every 3–10 min")

    return ProjectRulesOut(
        project_id=project.id,
        project_name=project.name,
        rules=rules if rules else ["No assignment rules configured"],
    )


@router.get("/projects/{project_id}/campaign-logs", response_model=List[CampaignAuditLogOut])
async def get_campaign_logs(
    project_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    """Campaign assignment change history for a project."""
    from app.models.campaign_audit_log import CampaignAuditLog
    result = await session.execute(
        select(CampaignAuditLog)
        .where(CampaignAuditLog.project_id == project_id)
        .order_by(desc(CampaignAuditLog.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return result.scalars().all()


@router.get("/stats", response_model=StatsOut)
async def get_stats(
    session: AsyncSession = Depends(get_session),
):
    """Cross-project campaign intelligence metrics."""
    from app.models.reply import ProcessedReply

    # Campaign counts
    total_result = await session.execute(select(func.count(Campaign.id)))
    total = total_result.scalar() or 0

    platform_result = await session.execute(
        select(Campaign.platform, func.count(Campaign.id)).group_by(Campaign.platform)
    )
    platform_counts = dict(platform_result.all())

    unresolved_result = await session.execute(
        select(func.count(Campaign.id)).where(Campaign.project_id.is_(None))
    )
    unresolved = unresolved_result.scalar() or 0

    unack_result = await session.execute(
        select(func.count(Campaign.id)).where(Campaign.acknowledged == False)
    )
    unacknowledged = unack_result.scalar() or 0

    # Reply volumes
    now = datetime.utcnow()
    vol_7d = await session.execute(
        select(func.count(ProcessedReply.id)).where(
            ProcessedReply.received_at >= now - timedelta(days=7)
        )
    )
    vol_30d = await session.execute(
        select(func.count(ProcessedReply.id)).where(
            ProcessedReply.received_at >= now - timedelta(days=30)
        )
    )

    # Newest campaign
    newest_result = await session.execute(
        select(Campaign.name, Campaign.first_seen_at)
        .order_by(desc(Campaign.first_seen_at))
        .limit(1)
    )
    newest = newest_result.first()

    assigned = total - unresolved
    assignment_rate = (assigned / total * 100) if total > 0 else 0.0

    return StatsOut(
        total_campaigns=total,
        smartlead_campaigns=platform_counts.get("smartlead", 0),
        getsales_campaigns=platform_counts.get("getsales", 0),
        unresolved_count=unresolved,
        unacknowledged_count=unacknowledged,
        assignment_rate=round(assignment_rate, 1),
        reply_volume_7d=vol_7d.scalar() or 0,
        reply_volume_30d=vol_30d.scalar() or 0,
        newest_campaign=newest[0] if newest else None,
        newest_campaign_at=newest[1] if newest else None,
    )


@router.post("/projects/{project_id}/rule-feedback")
async def submit_rule_feedback(
    project_id: int,
    body: RuleFeedbackRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    """Submit feedback on campaign assignment rules — AI reconsiders and updates campaign_filters."""
    # Validate project
    proj_result = await session.execute(
        select(Project).where(Project.id == project_id, Project.deleted_at.is_(None))
    )
    if not proj_result.scalar():
        raise HTTPException(404, "Project not found")

    # Create learning log immediately
    log = LearningLog(
        project_id=project_id,
        trigger="rule_feedback",
        feedback_text=body.feedback_text,
        status="processing",
    )
    session.add(log)
    await session.flush()
    log_id = log.id
    await session.commit()

    # Process in background with own session
    async def _process():
        from app.services.learning_service import learning_service
        async with async_session_maker() as bg_session:
            try:
                await learning_service.process_rule_feedback(
                    bg_session, project_id, body.feedback_text, log_id
                )
                await bg_session.commit()
            except Exception as e:
                logger.error(f"Rule feedback processing failed: {e}", exc_info=True)
                await bg_session.rollback()

    background_tasks.add_task(_process)
    return {"learning_log_id": log_id, "status": "processing"}


@router.get("/project-metrics", response_model=ProjectMetricsOut)
async def get_project_metrics(
    period: str = Query("30d", description="Time period: 7d, 30d, or all"),
    session: AsyncSession = Depends(get_session),
):
    """Per-project metrics: contacts uploaded to campaigns + warm replies."""
    from app.models.reply import ProcessedReply

    # Time filter
    now = datetime.utcnow()
    if period == "7d":
        since = now - timedelta(days=7)
    elif period == "30d":
        since = now - timedelta(days=30)
    else:
        since = None

    # 1. All active projects
    proj_result = await session.execute(
        select(Project.id, Project.name).where(Project.deleted_at.is_(None)).order_by(Project.name)
    )
    projects_list = proj_result.all()
    if not projects_list:
        return ProjectMetricsOut(projects=[], period=period)

    # 2. Contacts uploaded (sum of Campaign.leads_count per project)
    leads_query = (
        select(Campaign.project_id, func.coalesce(func.sum(Campaign.leads_count), 0).label("total_leads"))
        .where(Campaign.project_id.isnot(None))
        .group_by(Campaign.project_id)
    )
    leads_result = await session.execute(leads_query)
    leads_map = {row.project_id: row.total_leads for row in leads_result.all()}

    # 3. Warm replies per project (interested + meeting_request + question)
    #    Join ProcessedReply → Campaign on campaign_name to resolve project_id
    warm_categories = ["interested", "meeting_request", "question"]
    warm_query = (
        select(Campaign.project_id, func.count(ProcessedReply.id).label("warm_count"))
        .join(Campaign, func.lower(ProcessedReply.campaign_name) == func.lower(Campaign.name))
        .where(
            and_(
                ProcessedReply.category.in_(warm_categories),
                Campaign.project_id.isnot(None),
            )
        )
        .group_by(Campaign.project_id)
    )
    if since:
        warm_query = warm_query.where(ProcessedReply.received_at >= since)
    warm_result = await session.execute(warm_query)
    warm_map = {row.project_id: row.warm_count for row in warm_result.all()}

    # 4. Build response sorted by warm replies desc
    metrics = []
    for pid, pname in projects_list:
        metrics.append(ProjectMetric(
            project_id=pid,
            project_name=pname,
            contacts_uploaded=leads_map.get(pid, 0),
            warm_replies=warm_map.get(pid, 0),
        ))
    metrics.sort(key=lambda m: m.warm_replies, reverse=True)

    return ProjectMetricsOut(projects=metrics, period=period)


@router.get("/unresolved-count")
async def get_unresolved_count(
    session: AsyncSession = Depends(get_session),
):
    """Badge count: number of unresolved campaigns (no project assigned)."""
    now = datetime.utcnow()
    result = await session.execute(
        select(func.count(Campaign.id)).where(Campaign.project_id.is_(None))
    )
    count = result.scalar() or 0

    # Count campaigns first seen in last 60 seconds
    new_result = await session.execute(
        select(func.count(Campaign.id)).where(
            Campaign.first_seen_at >= now - timedelta(seconds=60)
        )
    )
    new_count = new_result.scalar() or 0

    return {"count": count, "new_count": new_count}
