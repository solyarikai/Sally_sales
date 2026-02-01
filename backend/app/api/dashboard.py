"""API endpoints for Dashboard statistics and activity feed."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, or_
from datetime import datetime, timedelta
from typing import List, Optional
from pydantic import BaseModel
import logging

from app.db import get_session
from app.models.reply import ReplyAutomation, ProcessedReply
from app.models.contact import Contact, Project
from app.models.user import Company

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


# ============= Schemas =============

class AutomationStats(BaseModel):
    total: int
    active: int
    paused: int
    
class ReplyStats(BaseModel):
    total: int
    today: int
    this_week: int
    pending: int
    approved: int
    dismissed: int
    by_category: dict
    
class ContactStats(BaseModel):
    total: int
    leads: int
    contacted: int
    replied: int
    qualified: int

class ActivityItem(BaseModel):
    id: str
    type: str  # reply, automation, contact, etc.
    title: str
    description: str
    timestamp: datetime
    icon: str  # emoji or icon name
    link: Optional[str] = None
    
class DashboardStats(BaseModel):
    automations: AutomationStats
    replies: ReplyStats
    contacts: ContactStats
    companies_count: int
    projects_count: int

class DashboardResponse(BaseModel):
    stats: DashboardStats
    recent_activity: List[ActivityItem]


# ============= Endpoints =============

@router.get("/stats", response_model=DashboardResponse)
async def get_dashboard_stats(
    session: AsyncSession = Depends(get_session)
):
    """Get comprehensive dashboard statistics and recent activity."""
    
    # ===== Automation Stats =====
    auto_total_result = await session.execute(
        select(func.count(ReplyAutomation.id)).where(ReplyAutomation.is_active == True)
    )
    auto_total = auto_total_result.scalar() or 0
    
    auto_active_result = await session.execute(
        select(func.count(ReplyAutomation.id)).where(
            ReplyAutomation.is_active == True,
            ReplyAutomation.active == True
        )
    )
    auto_active = auto_active_result.scalar() or 0
    
    automation_stats = AutomationStats(
        total=auto_total,
        active=auto_active,
        paused=auto_total - auto_active
    )
    
    # ===== Reply Stats =====
    reply_total_result = await session.execute(
        select(func.count(ProcessedReply.id))
    )
    reply_total = reply_total_result.scalar() or 0
    
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    reply_today_result = await session.execute(
        select(func.count(ProcessedReply.id)).where(
            ProcessedReply.processed_at >= today_start
        )
    )
    reply_today = reply_today_result.scalar() or 0
    
    week_start = today_start - timedelta(days=today_start.weekday())
    reply_week_result = await session.execute(
        select(func.count(ProcessedReply.id)).where(
            ProcessedReply.processed_at >= week_start
        )
    )
    reply_week = reply_week_result.scalar() or 0
    
    # Approval status counts
    status_query = select(
        ProcessedReply.approval_status,
        func.count(ProcessedReply.id)
    ).group_by(ProcessedReply.approval_status)
    
    status_result = await session.execute(status_query)
    status_counts = {row[0] or "pending": row[1] for row in status_result.all()}
    
    pending = status_counts.get("pending", 0) + status_counts.get(None, 0)
    approved = status_counts.get("approved", 0)
    dismissed = status_counts.get("dismissed", 0)
    
    # Category counts
    category_query = select(
        ProcessedReply.category,
        func.count(ProcessedReply.id)
    ).group_by(ProcessedReply.category)
    
    category_result = await session.execute(category_query)
    by_category = {row[0] or "unknown": row[1] for row in category_result.all()}
    
    reply_stats = ReplyStats(
        total=reply_total,
        today=reply_today,
        this_week=reply_week,
        pending=pending,
        approved=approved,
        dismissed=dismissed,
        by_category=by_category
    )
    
    # ===== Contact Stats =====
    contact_total_result = await session.execute(
        select(func.count(Contact.id)).where(Contact.is_active == True)
    )
    contact_total = contact_total_result.scalar() or 0
    
    contact_status_query = select(
        Contact.status,
        func.count(Contact.id)
    ).where(Contact.is_active == True).group_by(Contact.status)
    
    contact_status_result = await session.execute(contact_status_query)
    contact_status_counts = {row[0] or "lead": row[1] for row in contact_status_result.all()}
    
    contact_stats = ContactStats(
        total=contact_total,
        leads=contact_status_counts.get("lead", 0),
        contacted=contact_status_counts.get("contacted", 0),
        replied=contact_status_counts.get("replied", 0),
        qualified=contact_status_counts.get("qualified", 0)
    )
    
    # ===== Companies and Projects Count =====
    companies_result = await session.execute(
        select(func.count(Company.id)).where(Company.is_active == True)
    )
    companies_count = companies_result.scalar() or 0
    
    projects_result = await session.execute(
        select(func.count(Project.id)).where(Project.is_active == True)
    )
    projects_count = projects_result.scalar() or 0
    
    # ===== Recent Activity =====
    activity_items = []
    
    # Recent replies (last 10) - select specific columns to avoid lazy loading
    recent_replies_result = await session.execute(
        select(
            ProcessedReply.id,
            ProcessedReply.lead_first_name,
            ProcessedReply.lead_last_name,
            ProcessedReply.lead_email,
            ProcessedReply.category,
            ProcessedReply.email_subject,
            ProcessedReply.created_at
        )
        .order_by(desc(ProcessedReply.created_at))
        .limit(10)
    )
    recent_replies = recent_replies_result.all()
    
    for reply in recent_replies:
        lead_name = " ".join(filter(None, [reply.lead_first_name, reply.lead_last_name])) or reply.lead_email
        activity_items.append(ActivityItem(
            id=f"reply-{reply.id}",
            type="reply",
            title=f"New reply from {lead_name}",
            description=f"Category: {reply.category or 'Unknown'} - {(reply.email_subject or 'No subject')[:50]}",
            timestamp=reply.created_at or datetime.utcnow(),
            icon="📬",
            link=f"/replies?id={reply.id}"
        ))
    
    # Recent automations (last 5) - select specific columns to avoid lazy loading
    recent_auto_result = await session.execute(
        select(
            ReplyAutomation.id,
            ReplyAutomation.name,
            ReplyAutomation.active,
            ReplyAutomation.campaign_ids,
            ReplyAutomation.created_at
        )
        .where(ReplyAutomation.is_active == True)
        .order_by(desc(ReplyAutomation.created_at))
        .limit(5)
    )
    recent_autos = recent_auto_result.all()
    
    for auto in recent_autos:
        campaign_count = len(auto.campaign_ids or []) if auto.campaign_ids else 0
        activity_items.append(ActivityItem(
            id=f"automation-{auto.id}",
            type="automation",
            title=f"Automation: {auto.name}",
            description=f"{'Active' if auto.active else 'Paused'} - {campaign_count} campaigns",
            timestamp=auto.created_at or datetime.utcnow(),
            icon="⚡",
            link="/replies"
        ))
    
    # Recent contacts (last 5)
    recent_contacts_result = await session.execute(
        select(Contact)
        .where(Contact.is_active == True)
        .order_by(desc(Contact.created_at))
        .limit(5)
    )
    recent_contacts = recent_contacts_result.scalars().all()
    
    for contact in recent_contacts:
        contact_name = " ".join(filter(None, [contact.first_name, contact.last_name])) or contact.email
        activity_items.append(ActivityItem(
            id=f"contact-{contact.id}",
            type="contact",
            title=f"Contact: {contact_name}",
            description=f"{contact.company or 'No company'} - {contact.status or 'lead'}",
            timestamp=contact.created_at or datetime.utcnow(),
            icon="👤",
            link="/contacts"
        ))
    
    # Sort all activity by timestamp and take top 10
    activity_items.sort(key=lambda x: x.timestamp, reverse=True)
    activity_items = activity_items[:10]
    
    # Build response
    dashboard_stats = DashboardStats(
        automations=automation_stats,
        replies=reply_stats,
        contacts=contact_stats,
        companies_count=companies_count,
        projects_count=projects_count
    )
    
    return DashboardResponse(
        stats=dashboard_stats,
        recent_activity=activity_items
    )


@router.get("/quick-stats")
async def get_quick_stats(
    session: AsyncSession = Depends(get_session)
):
    """Get quick stats for header/sidebar display."""
    
    # Total counts only - fast query
    auto_count = (await session.execute(
        select(func.count(ReplyAutomation.id)).where(ReplyAutomation.is_active == True)
    )).scalar() or 0
    
    reply_count = (await session.execute(
        select(func.count(ProcessedReply.id))
    )).scalar() or 0
    
    contact_count = (await session.execute(
        select(func.count(Contact.id)).where(Contact.is_active == True)
    )).scalar() or 0
    
    # Pending replies
    pending_count = (await session.execute(
        select(func.count(ProcessedReply.id)).where(
            or_(
                ProcessedReply.approval_status == None,
                ProcessedReply.approval_status == "pending"
            )
        )
    )).scalar() or 0
    
    return {
        "automations": auto_count,
        "replies": reply_count,
        "contacts": contact_count,
        "pending_replies": pending_count
    }
