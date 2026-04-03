"""Project Reports API — endpoints for report management, plan tracking, and subscriptions.

Endpoints:
- GET  /project-reports/{project_id}/status        - progress on plan
- GET  /project-reports/{project_id}/reports       - list of reports
- GET  /project-reports/{project_id}/plans         - list of plans
- POST /project-reports/{project_id}/plans         - upload a new plan
- POST /project-reports/{project_id}/generate-client-report - generate client report
- GET  /project-reports/{project_id}/subscriptions - list subscriptions
- POST /project-reports/{project_id}/subscriptions - add subscription
- DELETE /project-reports/{project_id}/subscriptions/{sub_id} - remove subscription
"""
import logging
from datetime import date, datetime, timedelta, time as dt_time
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.project_report import (
    ProjectReport, ProjectPlan, ProjectProgressItem,
    ProjectReportSubscription, ProgressStatus
)
from app.models.contact import Project
from app.services.project_report_service import (
    get_progress_status, parse_plan_into_items,
    generate_client_report, get_report_history,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/project-reports", tags=["project-reports"])


# ============= Pydantic Models =============

class ProgressStatusResponse(BaseModel):
    total: int
    completed: int
    in_progress: int
    pending: int
    blocked: int
    completion_percent: float
    by_category: dict


class ReportSummary(BaseModel):
    id: int
    date: str
    lead_name: str
    summary: str
    forwarded: bool


class PlanSummary(BaseModel):
    id: int
    title: Optional[str]
    version: int
    is_active: bool
    items_count: int
    created_at: datetime


class PlanItemResponse(BaseModel):
    id: int
    item_text: str
    due_date: Optional[str]
    priority: Optional[str]
    category: Optional[str]
    status: str


class PlanDetailResponse(BaseModel):
    id: int
    title: Optional[str]
    content: str
    version: int
    is_active: bool
    items: List[PlanItemResponse]
    created_at: datetime


class CreatePlanRequest(BaseModel):
    title: Optional[str] = None
    content: str = Field(..., min_length=10)


class GenerateReportRequest(BaseModel):
    start_date: date
    end_date: date
    include_plan_status: bool = True


class GenerateReportResponse(BaseModel):
    report_text: str
    period: str
    reports_count: int
    items_completed: int


class SubscriptionResponse(BaseModel):
    id: int
    chat_id: str
    username: Optional[str]
    first_name: Optional[str]
    role: str
    report_time: Optional[str]
    timezone: str
    is_active: bool
    last_asked_at: Optional[datetime]
    last_reported_at: Optional[datetime]


class CreateSubscriptionRequest(BaseModel):
    chat_id: str
    username: Optional[str] = None
    first_name: Optional[str] = None
    role: str = Field(..., pattern="^(lead|boss)$")
    report_time: Optional[str] = None  # HH:MM format
    timezone: str = "Europe/Moscow"


class UpdateProgressItemRequest(BaseModel):
    status: str = Field(..., pattern="^(pending|in_progress|completed|blocked)$")


# ============= Helper Functions =============

async def _get_project(session: AsyncSession, project_id: int) -> Project:
    """Get project or raise 404."""
    result = await session.execute(
        select(Project).where(
            Project.id == project_id,
            Project.deleted_at.is_(None),
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


# ============= Endpoints =============

@router.get("/{project_id}/status", response_model=ProgressStatusResponse)
async def get_project_progress_status(
    project_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get progress status for a project's active plan."""
    await _get_project(session, project_id)
    status = await get_progress_status(session, project_id)
    return ProgressStatusResponse(**status)


@router.get("/{project_id}/reports")
async def list_project_reports(
    project_id: int,
    days: int = Query(default=30, ge=1, le=365),
    session: AsyncSession = Depends(get_session),
):
    """List reports for a project."""
    await _get_project(session, project_id)
    history = await get_report_history(session, project_id, days=days)
    return {"reports": history, "count": len(history)}


@router.get("/{project_id}/reports/{report_id}")
async def get_project_report(
    project_id: int,
    report_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get a specific report."""
    await _get_project(session, project_id)

    result = await session.execute(
        select(ProjectReport).where(
            ProjectReport.id == report_id,
            ProjectReport.project_id == project_id,
        )
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    return {
        "id": report.id,
        "project_id": report.project_id,
        "lead_chat_id": report.lead_chat_id,
        "lead_username": report.lead_username,
        "lead_first_name": report.lead_first_name,
        "report_date": report.report_date.isoformat(),
        "report_text": report.report_text,
        "ai_summary": report.ai_summary,
        "forwarded_to_boss": report.forwarded_to_boss,
        "forwarded_at": report.forwarded_at.isoformat() if report.forwarded_at else None,
        "created_at": report.created_at.isoformat(),
    }


@router.get("/{project_id}/plans")
async def list_project_plans(
    project_id: int,
    include_inactive: bool = False,
    session: AsyncSession = Depends(get_session),
):
    """List plans for a project."""
    await _get_project(session, project_id)

    query = select(ProjectPlan).where(ProjectPlan.project_id == project_id)
    if not include_inactive:
        query = query.where(ProjectPlan.is_active == True)
    query = query.order_by(ProjectPlan.version.desc())

    result = await session.execute(query)
    plans = result.scalars().all()

    # Get item counts
    plans_response = []
    for plan in plans:
        items_result = await session.execute(
            select(ProjectProgressItem).where(ProjectProgressItem.plan_id == plan.id)
        )
        items_count = len(items_result.scalars().all())

        plans_response.append(PlanSummary(
            id=plan.id,
            title=plan.title,
            version=plan.version,
            is_active=plan.is_active,
            items_count=items_count,
            created_at=plan.created_at,
        ))

    return {"plans": plans_response, "count": len(plans_response)}


@router.get("/{project_id}/plans/{plan_id}")
async def get_project_plan(
    project_id: int,
    plan_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get a specific plan with items."""
    await _get_project(session, project_id)

    result = await session.execute(
        select(ProjectPlan).where(
            ProjectPlan.id == plan_id,
            ProjectPlan.project_id == project_id,
        )
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    # Get items
    items_result = await session.execute(
        select(ProjectProgressItem).where(
            ProjectProgressItem.plan_id == plan.id
        ).order_by(ProjectProgressItem.id)
    )
    items = items_result.scalars().all()

    return PlanDetailResponse(
        id=plan.id,
        title=plan.title,
        content=plan.content,
        version=plan.version,
        is_active=plan.is_active,
        items=[
            PlanItemResponse(
                id=item.id,
                item_text=item.item_text,
                due_date=item.due_date.isoformat() if item.due_date else None,
                priority=item.priority,
                category=item.category,
                status=item.status,
            )
            for item in items
        ],
        created_at=plan.created_at,
    )


@router.post("/{project_id}/plans")
async def create_project_plan(
    project_id: int,
    request: CreatePlanRequest,
    session: AsyncSession = Depends(get_session),
):
    """Create a new plan for a project."""
    project = await _get_project(session, project_id)

    # Deactivate previous plans
    prev_plans_result = await session.execute(
        select(ProjectPlan).where(
            ProjectPlan.project_id == project_id,
            ProjectPlan.is_active == True,
        )
    )
    for prev in prev_plans_result.scalars().all():
        prev.is_active = False

    # Get max version
    from sqlalchemy import func
    max_version_result = await session.execute(
        select(func.max(ProjectPlan.version)).where(ProjectPlan.project_id == project_id)
    )
    max_version = max_version_result.scalar() or 0

    # Create plan
    plan = ProjectPlan(
        project_id=project_id,
        title=request.title or f"Plan v{max_version + 1}",
        content=request.content,
        content_type="text",
        is_active=True,
        version=max_version + 1,
    )
    session.add(plan)
    await session.flush()

    # Parse with AI
    parsed_items = await parse_plan_into_items(request.content, project.name)
    plan.ai_parsed_items = parsed_items

    # Create progress items
    items_created = 0
    for item_data in parsed_items:
        due_date = None
        if item_data.get("due_date"):
            try:
                due_date = datetime.strptime(item_data["due_date"], "%Y-%m-%d").date()
            except ValueError:
                pass

        progress_item = ProjectProgressItem(
            plan_id=plan.id,
            project_id=project_id,
            item_text=item_data.get("item", ""),
            due_date=due_date,
            priority=item_data.get("priority"),
            category=item_data.get("category"),
            status="pending",
        )
        session.add(progress_item)
        items_created += 1

    await session.commit()

    return {
        "id": plan.id,
        "version": plan.version,
        "items_created": items_created,
        "parsed_items": parsed_items,
    }


@router.patch("/{project_id}/items/{item_id}")
async def update_progress_item(
    project_id: int,
    item_id: int,
    request: UpdateProgressItemRequest,
    session: AsyncSession = Depends(get_session),
):
    """Update a progress item status."""
    await _get_project(session, project_id)

    result = await session.execute(
        select(ProjectProgressItem).where(
            ProjectProgressItem.id == item_id,
            ProjectProgressItem.project_id == project_id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    old_status = item.status
    item.status = request.status
    item.updated_at = datetime.utcnow()

    if request.status == "completed" and old_status != "completed":
        item.completed_at = datetime.utcnow()
    elif request.status != "completed":
        item.completed_at = None

    await session.commit()

    return {
        "id": item.id,
        "old_status": old_status,
        "new_status": item.status,
    }


@router.post("/{project_id}/generate-client-report", response_model=GenerateReportResponse)
async def generate_project_client_report(
    project_id: int,
    request: GenerateReportRequest,
    session: AsyncSession = Depends(get_session),
):
    """Generate a professional client-facing report."""
    await _get_project(session, project_id)

    result = await generate_client_report(
        session,
        project_id,
        request.start_date,
        request.end_date,
        request.include_plan_status,
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return GenerateReportResponse(**result)


@router.get("/{project_id}/subscriptions")
async def list_subscriptions(
    project_id: int,
    session: AsyncSession = Depends(get_session),
):
    """List all subscriptions for a project."""
    await _get_project(session, project_id)

    result = await session.execute(
        select(ProjectReportSubscription).where(
            ProjectReportSubscription.project_id == project_id,
        ).order_by(ProjectReportSubscription.role, ProjectReportSubscription.created_at)
    )
    subs = result.scalars().all()

    return {
        "subscriptions": [
            SubscriptionResponse(
                id=sub.id,
                chat_id=sub.chat_id,
                username=sub.username,
                first_name=sub.first_name,
                role=sub.role,
                report_time=sub.report_time.strftime("%H:%M") if sub.report_time else None,
                timezone=sub.timezone,
                is_active=sub.is_active,
                last_asked_at=sub.last_asked_at,
                last_reported_at=sub.last_reported_at,
            )
            for sub in subs
        ],
        "count": len(subs),
    }


@router.post("/{project_id}/subscriptions")
async def create_subscription(
    project_id: int,
    request: CreateSubscriptionRequest,
    session: AsyncSession = Depends(get_session),
):
    """Add a new subscription to a project."""
    await _get_project(session, project_id)

    # Check for existing
    existing = await session.execute(
        select(ProjectReportSubscription).where(
            ProjectReportSubscription.project_id == project_id,
            ProjectReportSubscription.chat_id == request.chat_id,
            ProjectReportSubscription.role == request.role,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Subscription already exists")

    # Parse report_time
    report_time = None
    if request.report_time:
        try:
            parts = request.report_time.split(":")
            report_time = dt_time(int(parts[0]), int(parts[1]))
        except (ValueError, IndexError):
            raise HTTPException(status_code=400, detail="Invalid report_time format. Use HH:MM")

    sub = ProjectReportSubscription(
        project_id=project_id,
        chat_id=request.chat_id,
        username=request.username,
        first_name=request.first_name,
        role=request.role,
        report_time=report_time,
        timezone=request.timezone,
        is_active=True,
    )
    session.add(sub)
    await session.commit()

    return {
        "id": sub.id,
        "message": f"Subscription created for {request.role}",
    }


@router.patch("/{project_id}/subscriptions/{sub_id}")
async def update_subscription(
    project_id: int,
    sub_id: int,
    is_active: Optional[bool] = None,
    report_time: Optional[str] = None,
    timezone: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):
    """Update a subscription."""
    await _get_project(session, project_id)

    result = await session.execute(
        select(ProjectReportSubscription).where(
            ProjectReportSubscription.id == sub_id,
            ProjectReportSubscription.project_id == project_id,
        )
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    if is_active is not None:
        sub.is_active = is_active

    if report_time is not None:
        try:
            parts = report_time.split(":")
            sub.report_time = dt_time(int(parts[0]), int(parts[1]))
        except (ValueError, IndexError):
            raise HTTPException(status_code=400, detail="Invalid report_time format. Use HH:MM")

    if timezone is not None:
        sub.timezone = timezone

    await session.commit()

    return {"id": sub.id, "updated": True}


@router.delete("/{project_id}/subscriptions/{sub_id}")
async def delete_subscription(
    project_id: int,
    sub_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Delete a subscription."""
    await _get_project(session, project_id)

    result = await session.execute(
        select(ProjectReportSubscription).where(
            ProjectReportSubscription.id == sub_id,
            ProjectReportSubscription.project_id == project_id,
        )
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    await session.delete(sub)
    await session.commit()

    return {"deleted": True}


@router.post("/{project_id}/test-message")
async def test_send_message(
    project_id: int,
    message: str = "Привет! Это тестовое сообщение от Sally Bot для проверки системы отчетов.",
    session: AsyncSession = Depends(get_session),
):
    """Test sending a message to project's Telegram chat via Sally Bot."""
    project = await _get_project(session, project_id)

    if not project.telegram_chat_id:
        raise HTTPException(status_code=400, detail="Project has no telegram_chat_id configured")

    from app.services.sally_bot_service import sally_bot_service

    if not sally_bot_service.token:
        raise HTTPException(status_code=500, detail="Sally Bot token not configured")

    try:
        result = await sally_bot_service.send_message(
            chat_id=int(project.telegram_chat_id),
            text=message,
        )
        return {
            "success": result.get("ok", False),
            "chat_id": project.telegram_chat_id,
            "project": project.name,
            "result": result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send: {str(e)}")
