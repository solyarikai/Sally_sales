"""API endpoints for Outreach Statistics."""
from fastapi import APIRouter, HTTPException, Depends, Query, Body
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, delete
from typing import Optional, List
from datetime import date, datetime, timedelta
import logging

from app.db import get_session
from app.models import OutreachStats, Project
from app.api.companies import get_required_company
from app.services.outreach_stats_service import outreach_stats_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects/{project_id}/outreach-stats", tags=["outreach-stats"])


class OutreachStatCreate(BaseModel):
    period_start: date
    period_end: date
    channel: str
    segment: str
    plan_contacts: int = 0
    contacts_sent: int = 0
    contacts_accepted: int = 0
    replies_count: int = 0
    positive_replies: int = 0
    meetings_scheduled: int = 0
    meetings_completed: int = 0
    is_manual: bool = True
    notes: Optional[str] = None


class OutreachStatUpdate(BaseModel):
    plan_contacts: Optional[int] = None
    contacts_sent: Optional[int] = None
    contacts_accepted: Optional[int] = None
    replies_count: Optional[int] = None
    positive_replies: Optional[int] = None
    meetings_scheduled: Optional[int] = None
    meetings_completed: Optional[int] = None
    notes: Optional[str] = None


class PeriodParams(BaseModel):
    period_start: date
    period_end: date


@router.get("")
async def get_outreach_stats(
    project_id: int,
    period_start: Optional[date] = Query(None),
    period_end: Optional[date] = Query(None),
    channel: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_session),
    company = Depends(get_required_company),
):
    """Get outreach stats for a project, optionally filtered by period and channel."""
    # Verify project belongs to company
    project = await db.get(Project, project_id)
    if not project or project.company_id != company.id:
        raise HTTPException(status_code=404, detail="Project not found")

    # Default to last 30 days if no period specified
    if not period_start:
        period_start = date.today() - timedelta(days=30)
    if not period_end:
        period_end = date.today()

    query = select(OutreachStats).where(
        and_(
            OutreachStats.project_id == project_id,
            OutreachStats.period_start >= period_start,
            OutreachStats.period_end <= period_end,
        )
    )

    if channel:
        query = query.where(OutreachStats.channel == channel)

    query = query.order_by(OutreachStats.channel, OutreachStats.segment)

    result = await db.execute(query)
    stats = result.scalars().all()

    # Calculate totals by channel
    totals_by_channel = {}
    for stat in stats:
        if stat.channel not in totals_by_channel:
            totals_by_channel[stat.channel] = {
                "channel": stat.channel,
                "plan_contacts": 0,
                "contacts_sent": 0,
                "contacts_accepted": 0,
                "replies_count": 0,
                "positive_replies": 0,
                "meetings_scheduled": 0,
                "meetings_completed": 0,
            }
        totals_by_channel[stat.channel]["plan_contacts"] += stat.plan_contacts or 0
        totals_by_channel[stat.channel]["contacts_sent"] += stat.contacts_sent or 0
        totals_by_channel[stat.channel]["contacts_accepted"] += stat.contacts_accepted or 0
        totals_by_channel[stat.channel]["replies_count"] += stat.replies_count or 0
        totals_by_channel[stat.channel]["positive_replies"] += stat.positive_replies or 0
        totals_by_channel[stat.channel]["meetings_scheduled"] += stat.meetings_scheduled or 0
        totals_by_channel[stat.channel]["meetings_completed"] += stat.meetings_completed or 0

    # Calculate rates for totals
    for ch, total in totals_by_channel.items():
        if total["contacts_sent"] > 0:
            total["reply_rate"] = round(total["replies_count"] / total["contacts_sent"], 4)
            total["accept_rate"] = round(total["contacts_accepted"] / total["contacts_sent"], 4)
        else:
            total["reply_rate"] = 0
            total["accept_rate"] = 0

        if total["replies_count"] > 0:
            total["positive_rate"] = round(total["positive_replies"] / total["replies_count"], 4)
        else:
            total["positive_rate"] = 0

    # Grand total
    grand_total = {
        "plan_contacts": sum(t["plan_contacts"] for t in totals_by_channel.values()),
        "contacts_sent": sum(t["contacts_sent"] for t in totals_by_channel.values()),
        "contacts_accepted": sum(t["contacts_accepted"] for t in totals_by_channel.values()),
        "replies_count": sum(t["replies_count"] for t in totals_by_channel.values()),
        "positive_replies": sum(t["positive_replies"] for t in totals_by_channel.values()),
        "meetings_scheduled": sum(t["meetings_scheduled"] for t in totals_by_channel.values()),
        "meetings_completed": sum(t["meetings_completed"] for t in totals_by_channel.values()),
    }

    if grand_total["contacts_sent"] > 0:
        grand_total["reply_rate"] = round(grand_total["replies_count"] / grand_total["contacts_sent"], 4)
    else:
        grand_total["reply_rate"] = 0

    if grand_total["replies_count"] > 0:
        grand_total["positive_rate"] = round(grand_total["positive_replies"] / grand_total["replies_count"], 4)
    else:
        grand_total["positive_rate"] = 0

    return {
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "stats": [stat.to_dict() for stat in stats],
        "totals_by_channel": list(totals_by_channel.values()),
        "grand_total": grand_total,
    }


@router.post("")
async def create_outreach_stat(
    project_id: int,
    data: OutreachStatCreate = Body(...),
    db: AsyncSession = Depends(get_session),
    company = Depends(get_required_company),
):
    """Create a new outreach stat row (for manual channels like Telegram, WhatsApp)."""
    # Verify project belongs to company
    project = await db.get(Project, project_id)
    if not project or project.company_id != company.id:
        raise HTTPException(status_code=404, detail="Project not found")

    # Check for duplicate
    existing = await db.execute(
        select(OutreachStats).where(
            and_(
                OutreachStats.project_id == project_id,
                OutreachStats.period_start == data.period_start,
                OutreachStats.period_end == data.period_end,
                OutreachStats.channel == data.channel,
                OutreachStats.segment == data.segment,
            )
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Stat for this channel/segment/period already exists")

    stat = OutreachStats(
        company_id=company.id,
        project_id=project_id,
        period_start=data.period_start,
        period_end=data.period_end,
        channel=data.channel,
        segment=data.segment,
        plan_contacts=data.plan_contacts,
        contacts_sent=data.contacts_sent,
        contacts_accepted=data.contacts_accepted,
        replies_count=data.replies_count,
        positive_replies=data.positive_replies,
        meetings_scheduled=data.meetings_scheduled,
        meetings_completed=data.meetings_completed,
        is_manual=1 if data.is_manual else 0,
        data_source="manual",
        notes=data.notes,
    )
    stat.calculate_rates()

    db.add(stat)
    await db.commit()
    await db.refresh(stat)

    return stat.to_dict()


@router.patch("/{stat_id}")
async def update_outreach_stat(
    project_id: int,
    stat_id: int,
    data: OutreachStatUpdate = Body(...),
    db: AsyncSession = Depends(get_session),
    company = Depends(get_required_company),
):
    """Update an outreach stat (plan or manual values)."""
    stat = await db.get(OutreachStats, stat_id)
    if not stat or stat.project_id != project_id:
        raise HTTPException(status_code=404, detail="Stat not found")

    # Verify project belongs to company
    project = await db.get(Project, project_id)
    if not project or project.company_id != company.id:
        raise HTTPException(status_code=404, detail="Project not found")

    # Update fields
    if data.plan_contacts is not None:
        stat.plan_contacts = data.plan_contacts

    # Only allow updating fact values if it's a manual entry
    if stat.is_manual:
        if data.contacts_sent is not None:
            stat.contacts_sent = data.contacts_sent
        if data.contacts_accepted is not None:
            stat.contacts_accepted = data.contacts_accepted
        if data.replies_count is not None:
            stat.replies_count = data.replies_count
        if data.positive_replies is not None:
            stat.positive_replies = data.positive_replies
        if data.meetings_scheduled is not None:
            stat.meetings_scheduled = data.meetings_scheduled
        if data.meetings_completed is not None:
            stat.meetings_completed = data.meetings_completed

    if data.notes is not None:
        stat.notes = data.notes

    stat.calculate_rates()
    await db.commit()
    await db.refresh(stat)

    return stat.to_dict()


@router.delete("/{stat_id}")
async def delete_outreach_stat(
    project_id: int,
    stat_id: int,
    db: AsyncSession = Depends(get_session),
    company = Depends(get_required_company),
):
    """Delete an outreach stat row."""
    stat = await db.get(OutreachStats, stat_id)
    if not stat or stat.project_id != project_id:
        raise HTTPException(status_code=404, detail="Stat not found")

    # Verify project belongs to company
    project = await db.get(Project, project_id)
    if not project or project.company_id != company.id:
        raise HTTPException(status_code=404, detail="Project not found")

    await db.delete(stat)
    await db.commit()

    return {"ok": True}


@router.post("/sync")
async def sync_outreach_stats(
    project_id: int,
    period_start: date = Query(...),
    period_end: date = Query(...),
    db: AsyncSession = Depends(get_session),
    company = Depends(get_required_company),
):
    """
    Sync stats from integrations (SmartLead, GetSales, Calendly).
    Manual channels are not affected.
    """
    # Verify project belongs to company
    project = await db.get(Project, project_id)
    if not project or project.company_id != company.id:
        raise HTTPException(status_code=404, detail="Project not found")

    result = await outreach_stats_service.sync_project_stats(
        db=db,
        project_id=project_id,
        company_id=company.id,
        period_start=period_start,
        period_end=period_end,
    )

    return {
        "ok": True,
        "synced_channels": result["synced_channels"],
        "stats_count": len(result["stats"]),
        "errors": result["errors"],
    }


@router.get("/summary")
async def get_outreach_summary(
    project_id: int,
    period: str = Query("30d", description="Period: 7d, 30d, 90d, all, or custom"),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_session),
    company = Depends(get_required_company),
):
    """Get summary KPIs for the project."""
    # Verify project belongs to company
    project = await db.get(Project, project_id)
    if not project or project.company_id != company.id:
        raise HTTPException(status_code=404, detail="Project not found")

    # Calculate period
    today = date.today()
    if period == "7d":
        period_start = today - timedelta(days=7)
        period_end = today
    elif period == "30d":
        period_start = today - timedelta(days=30)
        period_end = today
    elif period == "90d":
        period_start = today - timedelta(days=90)
        period_end = today
    elif period == "all":
        period_start = date(2020, 1, 1)
        period_end = today
    elif period == "custom" and date_from and date_to:
        period_start = date_from
        period_end = date_to
    else:
        period_start = today - timedelta(days=30)
        period_end = today

    # Get stats
    result = await db.execute(
        select(OutreachStats).where(
            and_(
                OutreachStats.project_id == project_id,
                OutreachStats.period_start >= period_start,
                OutreachStats.period_end <= period_end,
            )
        )
    )
    stats = result.scalars().all()

    # Aggregate
    total_plan = sum(s.plan_contacts or 0 for s in stats)
    total_sent = sum(s.contacts_sent or 0 for s in stats)
    total_replies = sum(s.replies_count or 0 for s in stats)
    total_positive = sum(s.positive_replies or 0 for s in stats)
    total_meetings = sum(s.meetings_scheduled or 0 for s in stats)
    total_completed = sum(s.meetings_completed or 0 for s in stats)

    return {
        "project_name": project.name,
        "period": {
            "start": period_start.isoformat(),
            "end": period_end.isoformat(),
            "label": period,
        },
        "kpi": {
            "total_plan": total_plan,
            "total_contacted": total_sent,
            "total_replies": total_replies,
            "positive_replies": total_positive,
            "meetings_scheduled": total_meetings,
            "meetings_completed": total_completed,
            "reply_rate": round(total_replies / total_sent, 4) if total_sent > 0 else 0,
            "positive_rate": round(total_positive / total_replies, 4) if total_replies > 0 else 0,
            "meeting_rate": round(total_meetings / total_positive, 4) if total_positive > 0 else 0,
        },
        "last_synced": max((s.last_synced_at for s in stats if s.last_synced_at), default=None),
    }
