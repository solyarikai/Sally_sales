"""
Client Dashboard API — aggregated endpoint for client-facing reports.

Returns all data needed for the client dashboard in one request:
- KPI summary (contacted, replies, positive, meetings)
- Stats by channel (plan vs fact)
- Stats by segment (detailed breakdown)
- Leads list (contacts with replies)
- Meetings list
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc, case
from typing import Optional, List, Dict, Any
from datetime import date, datetime, timedelta
from pydantic import BaseModel
import logging

from app.db import get_session
from app.models import Contact, Project, Campaign, Meeting, OutreachStats
from app.models.meeting import MeetingStatus, MeetingOutcome
from app.api.companies import get_required_company

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects/{project_id}/client-dashboard", tags=["client-dashboard"])


class LeadEntry(BaseModel):
    id: int
    date: Optional[str] = None
    name: str
    title: Optional[str] = None
    company: Optional[str] = None
    contact: str  # email or linkedin
    website: Optional[str] = None
    channel: Optional[str] = None
    segment: Optional[str] = None
    answer_preview: Optional[str] = None
    status: str  # positive, neutral, negative, meeting_booked, meeting_done
    meeting_date: Optional[str] = None
    comment: Optional[str] = None


class MeetingEntry(BaseModel):
    id: int
    contact_name: str
    contact_title: Optional[str] = None
    contact_company: Optional[str] = None
    scheduled_at: str
    status: str
    outcome: Optional[str] = None
    channel: Optional[str] = None
    segment: Optional[str] = None
    client_notes: Optional[str] = None


class ChannelStats(BaseModel):
    channel: str
    segment: Optional[str] = None
    plan: int = 0
    sent: int = 0
    accepted: int = 0
    accept_rate: float = 0.0
    replies: int = 0
    reply_rate: float = 0.0
    positive: int = 0
    positive_rate: float = 0.0
    meetings: int = 0
    meeting_rate: float = 0.0


class KPIData(BaseModel):
    total_plan: int = 0
    total_contacted: int = 0
    total_replies: int = 0
    positive_replies: int = 0
    meetings_scheduled: int = 0
    meetings_completed: int = 0
    reply_rate: float = 0.0
    positive_rate: float = 0.0
    meeting_rate: float = 0.0


class MeetingSummary(BaseModel):
    total: int = 0
    scheduled: int = 0
    completed: int = 0
    no_show: int = 0
    cancelled: int = 0
    qualified: int = 0
    follow_up: int = 0
    negotiation: int = 0
    closed_won: int = 0
    closed_lost: int = 0


class ClientDashboardResponse(BaseModel):
    project_name: str
    period: Dict[str, str]
    kpi: KPIData
    by_channel: List[ChannelStats]
    by_segment: List[ChannelStats]
    leads: List[LeadEntry]
    meetings: List[MeetingEntry]
    meetings_summary: MeetingSummary


def _calculate_period(period: str, date_from: Optional[date], date_to: Optional[date]) -> tuple[date, date]:
    """Calculate period start and end dates."""
    today = date.today()
    if period == "7d":
        return today - timedelta(days=7), today
    elif period == "30d":
        return today - timedelta(days=30), today
    elif period == "90d":
        return today - timedelta(days=90), today
    elif period == "all":
        return date(2020, 1, 1), today
    elif period == "custom" and date_from and date_to:
        return date_from, date_to
    else:
        return today - timedelta(days=30), today


def _contact_status_to_display(status: str) -> str:
    """Map contact status to display status for client."""
    positive_statuses = {"interested", "meeting_request", "positive", "qualified", "meeting_scheduled", "closed_won"}
    negative_statuses = {"not_interested", "unsubscribed", "bounced", "not_fit", "closed_lost"}
    meeting_statuses = {"meeting_scheduled", "meeting_booked"}

    if status in meeting_statuses:
        return "meeting_booked"
    elif status in positive_statuses:
        return "positive"
    elif status in negative_statuses:
        return "negative"
    else:
        return "neutral"


def _get_channel_from_source(source: str) -> str:
    """Extract channel from contact source."""
    if not source:
        return "unknown"
    source_lower = source.lower()
    if "smartlead" in source_lower or "email" in source_lower:
        return "email"
    elif "getsales" in source_lower or "linkedin" in source_lower:
        return "linkedin"
    elif "telegram" in source_lower or "tg" in source_lower:
        return "telegram"
    elif "whatsapp" in source_lower or "wa" in source_lower:
        return "whatsapp"
    else:
        return source


@router.get("", response_model=ClientDashboardResponse)
async def get_client_dashboard(
    project_id: int,
    period: str = Query("30d", description="Period: 7d, 30d, 90d, all, custom"),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_session),
    company = Depends(get_required_company),
):
    """
    Get aggregated client dashboard data.

    Returns KPIs, channel stats, segment breakdown, leads, and meetings.
    """
    # Verify project belongs to company
    project = await db.get(Project, project_id)
    if not project or project.company_id != company.id:
        raise HTTPException(status_code=404, detail="Project not found")

    period_start, period_end = _calculate_period(period, date_from, date_to)
    period_start_dt = datetime.combine(period_start, datetime.min.time())
    period_end_dt = datetime.combine(period_end, datetime.max.time())

    # ============= OUTREACH STATS (by channel and segment) =============
    stats_result = await db.execute(
        select(OutreachStats).where(
            and_(
                OutreachStats.project_id == project_id,
                OutreachStats.period_start >= period_start,
                OutreachStats.period_end <= period_end,
            )
        ).order_by(OutreachStats.channel, OutreachStats.segment)
    )
    stats_rows = stats_result.scalars().all()

    # Build by_segment list (detailed)
    by_segment: List[ChannelStats] = []
    for stat in stats_rows:
        by_segment.append(ChannelStats(
            channel=stat.channel,
            segment=stat.segment,
            plan=stat.plan_contacts or 0,
            sent=stat.contacts_sent or 0,
            accepted=stat.contacts_accepted or 0,
            accept_rate=stat.accept_rate or 0.0,
            replies=stat.replies_count or 0,
            reply_rate=stat.reply_rate or 0.0,
            positive=stat.positive_replies or 0,
            positive_rate=stat.positive_rate or 0.0,
            meetings=stat.meetings_scheduled or 0,
            meeting_rate=stat.meeting_rate or 0.0,
        ))

    # Build by_channel totals
    channel_totals: Dict[str, Dict] = {}
    for stat in stats_rows:
        ch = stat.channel
        if ch not in channel_totals:
            channel_totals[ch] = {
                "plan": 0, "sent": 0, "accepted": 0, "replies": 0,
                "positive": 0, "meetings": 0
            }
        channel_totals[ch]["plan"] += stat.plan_contacts or 0
        channel_totals[ch]["sent"] += stat.contacts_sent or 0
        channel_totals[ch]["accepted"] += stat.contacts_accepted or 0
        channel_totals[ch]["replies"] += stat.replies_count or 0
        channel_totals[ch]["positive"] += stat.positive_replies or 0
        channel_totals[ch]["meetings"] += stat.meetings_scheduled or 0

    by_channel: List[ChannelStats] = []
    for ch, totals in channel_totals.items():
        sent = totals["sent"]
        replies = totals["replies"]
        positive = totals["positive"]
        by_channel.append(ChannelStats(
            channel=ch,
            plan=totals["plan"],
            sent=sent,
            accepted=totals["accepted"],
            accept_rate=round(totals["accepted"] / sent, 4) if sent > 0 else 0.0,
            replies=replies,
            reply_rate=round(replies / sent, 4) if sent > 0 else 0.0,
            positive=positive,
            positive_rate=round(positive / replies, 4) if replies > 0 else 0.0,
            meetings=totals["meetings"],
            meeting_rate=round(totals["meetings"] / positive, 4) if positive > 0 else 0.0,
        ))

    # ============= KPI AGGREGATION =============
    total_plan = sum(t["plan"] for t in channel_totals.values())
    total_sent = sum(t["sent"] for t in channel_totals.values())
    total_replies = sum(t["replies"] for t in channel_totals.values())
    total_positive = sum(t["positive"] for t in channel_totals.values())
    total_meetings = sum(t["meetings"] for t in channel_totals.values())

    # Get completed meetings count
    completed_meetings = await db.scalar(
        select(func.count(Meeting.id)).where(
            and_(
                Meeting.project_id == project_id,
                Meeting.status == MeetingStatus.COMPLETED,
                Meeting.scheduled_at >= period_start_dt,
                Meeting.scheduled_at <= period_end_dt,
            )
        )
    )

    kpi = KPIData(
        total_plan=total_plan,
        total_contacted=total_sent,
        total_replies=total_replies,
        positive_replies=total_positive,
        meetings_scheduled=total_meetings,
        meetings_completed=completed_meetings or 0,
        reply_rate=round(total_replies / total_sent, 4) if total_sent > 0 else 0.0,
        positive_rate=round(total_positive / total_replies, 4) if total_replies > 0 else 0.0,
        meeting_rate=round(total_meetings / total_positive, 4) if total_positive > 0 else 0.0,
    )

    # ============= LEADS (contacts with replies in period) =============
    leads_query = select(Contact).where(
        and_(
            Contact.project_id == project_id,
            Contact.last_reply_at.isnot(None),
            Contact.last_reply_at >= period_start_dt,
            Contact.last_reply_at <= period_end_dt,
            Contact.deleted_at.is_(None),
        )
    ).order_by(desc(Contact.last_reply_at)).limit(200)

    leads_result = await db.execute(leads_query)
    leads_rows = leads_result.scalars().all()

    leads: List[LeadEntry] = []
    for contact in leads_rows:
        # Get meeting date if exists
        meeting_date = None
        meeting_result = await db.execute(
            select(Meeting.scheduled_at).where(
                and_(
                    Meeting.contact_id == contact.id,
                    Meeting.status != MeetingStatus.CANCELLED,
                )
            ).order_by(desc(Meeting.scheduled_at)).limit(1)
        )
        meeting_row = meeting_result.scalar_one_or_none()
        if meeting_row:
            meeting_date = meeting_row.strftime("%Y-%m-%d")

        # Get answer preview from activities or platform_state
        answer_preview = None
        if contact.platform_state:
            for platform_data in contact.platform_state.values():
                if isinstance(platform_data, dict):
                    answer_preview = platform_data.get("last_reply_text", "")[:100]
                    if answer_preview:
                        break

        name = f"{contact.first_name or ''} {contact.last_name or ''}".strip() or contact.email.split("@")[0]

        leads.append(LeadEntry(
            id=contact.id,
            date=contact.last_reply_at.strftime("%Y-%m-%d") if contact.last_reply_at else None,
            name=name,
            title=contact.job_title,
            company=contact.company_name,
            contact=contact.email or contact.linkedin_url or "",
            website=f"https://{contact.domain}" if contact.domain else None,
            channel=_get_channel_from_source(contact.source),
            segment=contact.segment,
            answer_preview=answer_preview,
            status=_contact_status_to_display(contact.status),
            meeting_date=meeting_date,
            comment=contact.notes or contact.sheet_client_comment,
        ))

    # ============= MEETINGS =============
    meetings_query = select(Meeting).where(
        and_(
            Meeting.project_id == project_id,
            Meeting.scheduled_at >= period_start_dt,
            Meeting.scheduled_at <= period_end_dt,
        )
    ).order_by(desc(Meeting.scheduled_at)).limit(100)

    meetings_result = await db.execute(meetings_query)
    meetings_rows = meetings_result.scalars().all()

    meetings: List[MeetingEntry] = []
    for meeting in meetings_rows:
        meetings.append(MeetingEntry(
            id=meeting.id,
            contact_name=meeting.invitee_name,
            contact_title=meeting.invitee_title,
            contact_company=meeting.invitee_company,
            scheduled_at=meeting.scheduled_at.isoformat() if meeting.scheduled_at else "",
            status=meeting.status.value if meeting.status else "scheduled",
            outcome=meeting.outcome.value if meeting.outcome else None,
            channel=meeting.channel,
            segment=meeting.segment,
            client_notes=meeting.client_notes,
        ))

    # ============= MEETINGS SUMMARY =============
    meetings_summary = MeetingSummary(
        total=len(meetings_rows),
        scheduled=sum(1 for m in meetings_rows if m.status == MeetingStatus.SCHEDULED),
        completed=sum(1 for m in meetings_rows if m.status == MeetingStatus.COMPLETED),
        no_show=sum(1 for m in meetings_rows if m.status == MeetingStatus.NO_SHOW),
        cancelled=sum(1 for m in meetings_rows if m.status == MeetingStatus.CANCELLED),
        qualified=sum(1 for m in meetings_rows if m.outcome == MeetingOutcome.QUALIFIED),
        follow_up=sum(1 for m in meetings_rows if m.outcome == MeetingOutcome.FOLLOW_UP),
        negotiation=sum(1 for m in meetings_rows if m.outcome == MeetingOutcome.NEGOTIATION),
        closed_won=sum(1 for m in meetings_rows if m.outcome == MeetingOutcome.CLOSED_WON),
        closed_lost=sum(1 for m in meetings_rows if m.outcome == MeetingOutcome.CLOSED_LOST),
    )

    return ClientDashboardResponse(
        project_name=project.name,
        period={
            "from": period_start.isoformat(),
            "to": period_end.isoformat(),
            "label": period,
        },
        kpi=kpi,
        by_channel=by_channel,
        by_segment=by_segment,
        leads=leads,
        meetings=meetings,
        meetings_summary=meetings_summary,
    )
