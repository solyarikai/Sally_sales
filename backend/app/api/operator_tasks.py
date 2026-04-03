"""
Operator Tasks API — 3-tab view for daily lead operations.

Tab 1: REPLIES — contacts with new inbound messages needing response
Tab 2: ALIGN MEETINGS — leads in negotiating/scheduled/rescheduled stages
Tab 3: ALIGN QUALIFIED — leads where meeting_held but no verdict yet
"""
import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Company, Contact, ContactActivity
from app.models.reply import ProcessedReply
from app.api.companies import get_required_company
from app.services.status_machine import (
    can_transition,
    transition_status,
    normalize_status,
    is_meeting_stage,
    needs_qualification,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/operator-tasks", tags=["Operator Tasks"])


# ── Schemas ──

class TaskContact(BaseModel):
    id: int
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company_name: Optional[str] = None
    job_title: Optional[str] = None
    linkedin_url: Optional[str] = None
    status: str
    last_reply_at: Optional[datetime] = None
    platform_state: Optional[dict] = None
    project_id: Optional[int] = None
    category: Optional[str] = None
    days_since: Optional[int] = None
    last_message: Optional[str] = None
    campaign_name: Optional[str] = None

    class Config:
        from_attributes = True


class TabData(BaseModel):
    tab: str
    count: int
    contacts: List[TaskContact]


class OperatorTasksResponse(BaseModel):
    replies: TabData
    align_meetings: TabData
    align_qualified: TabData


class StatusTransitionRequest(BaseModel):
    new_status: str
    force: bool = False


class StatusTransitionResponse(BaseModel):
    success: bool
    contact_id: int
    old_status: str
    new_status: str
    message: str


# ── Endpoints ──

@router.get("", response_model=OperatorTasksResponse)
async def get_operator_tasks(
    project_id: Optional[int] = Query(None, description="Filter by project"),
    limit: int = Query(50, le=200),
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Get operator tasks grouped into 3 tabs with counts."""
    base_filters = [
        Contact.company_id == company.id,
        Contact.deleted_at.is_(None),
    ]
    if project_id:
        base_filters.append(Contact.project_id == project_id)

    # ── Tab 1: REPLIES ──
    # Contacts with pending replies (ProcessedReply with approval_status = NULL/pending)
    replies_q = (
        select(
            Contact,
            ProcessedReply.category,
            ProcessedReply.reply_text,
            ProcessedReply.campaign_name,
        )
        .join(
            ProcessedReply,
            and_(
                func.lower(ProcessedReply.lead_email) == func.lower(Contact.email),
                or_(
                    ProcessedReply.approval_status.is_(None),
                    ProcessedReply.approval_status == "pending",
                ),
            ),
        )
        .where(*base_filters)
        .order_by(desc(ProcessedReply.received_at))
        .limit(limit)
    )
    replies_result = await session.execute(replies_q)
    replies_rows = replies_result.all()

    replies_contacts = []
    seen_reply_ids = set()
    for row in replies_rows:
        contact = row[0]
        if contact.id in seen_reply_ids:
            continue
        seen_reply_ids.add(contact.id)
        replies_contacts.append(TaskContact(
            id=contact.id,
            email=contact.email,
            first_name=contact.first_name,
            last_name=contact.last_name,
            company_name=contact.company_name,
            job_title=contact.job_title,
            linkedin_url=contact.linkedin_url,
            status=contact.status or "",
            last_reply_at=contact.last_reply_at,
            platform_state=contact.platform_state,
            project_id=contact.project_id,
            category=row[1],
            last_message=(row[2] or "")[:200],
            campaign_name=row[3],
        ))

    # Count total (not just limited)
    replies_count_q = (
        select(func.count(func.distinct(Contact.id)))
        .join(
            ProcessedReply,
            and_(
                func.lower(ProcessedReply.lead_email) == func.lower(Contact.email),
                or_(
                    ProcessedReply.approval_status.is_(None),
                    ProcessedReply.approval_status == "pending",
                ),
            ),
        )
        .where(*base_filters)
    )
    replies_count = (await session.execute(replies_count_q)).scalar() or 0

    # ── Tab 2: ALIGN MEETINGS ──
    meeting_statuses = [
        "negotiating_meeting", "scheduled", "meeting_rescheduled",
        "scheduling",  # legacy
    ]
    meetings_q = (
        select(Contact)
        .where(
            *base_filters,
            Contact.status.in_(meeting_statuses),
        )
        .order_by(desc(Contact.last_reply_at))
        .limit(limit)
    )
    meetings_result = await session.execute(meetings_q)
    meetings_rows = meetings_result.scalars().all()

    meetings_contacts = []
    for contact in meetings_rows:
        days = None
        if contact.last_reply_at:
            days = (datetime.utcnow() - contact.last_reply_at).days
        meetings_contacts.append(TaskContact(
            id=contact.id,
            email=contact.email,
            first_name=contact.first_name,
            last_name=contact.last_name,
            company_name=contact.company_name,
            job_title=contact.job_title,
            linkedin_url=contact.linkedin_url,
            status=contact.status or "",
            last_reply_at=contact.last_reply_at,
            platform_state=contact.platform_state,
            project_id=contact.project_id,
            days_since=days,
        ))

    meetings_count_q = (
        select(func.count(Contact.id))
        .where(
            *base_filters,
            Contact.status.in_(meeting_statuses),
        )
    )
    meetings_count = (await session.execute(meetings_count_q)).scalar() or 0

    # ── Tab 3: ALIGN QUALIFIED ──
    qualified_q = (
        select(Contact)
        .where(
            *base_filters,
            Contact.status == "meeting_held",
        )
        .order_by(desc(Contact.last_reply_at))
        .limit(limit)
    )
    qualified_result = await session.execute(qualified_q)
    qualified_rows = qualified_result.scalars().all()

    qualified_contacts = []
    for contact in qualified_rows:
        days = None
        if contact.last_reply_at:
            days = (datetime.utcnow() - contact.last_reply_at).days
        qualified_contacts.append(TaskContact(
            id=contact.id,
            email=contact.email,
            first_name=contact.first_name,
            last_name=contact.last_name,
            company_name=contact.company_name,
            job_title=contact.job_title,
            linkedin_url=contact.linkedin_url,
            status=contact.status or "",
            last_reply_at=contact.last_reply_at,
            platform_state=contact.platform_state,
            project_id=contact.project_id,
            days_since=days,
        ))

    qualified_count_q = (
        select(func.count(Contact.id))
        .where(
            *base_filters,
            Contact.status == "meeting_held",
        )
    )
    qualified_count = (await session.execute(qualified_count_q)).scalar() or 0

    return OperatorTasksResponse(
        replies=TabData(tab="replies", count=replies_count, contacts=replies_contacts),
        align_meetings=TabData(tab="align_meetings", count=meetings_count, contacts=meetings_contacts),
        align_qualified=TabData(tab="align_qualified", count=qualified_count, contacts=qualified_contacts),
    )


@router.patch("/{contact_id}/status", response_model=StatusTransitionResponse)
async def transition_contact_status(
    contact_id: int,
    body: StatusTransitionRequest,
    session: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Transition a contact's status with state machine validation."""
    result = await session.execute(
        select(Contact).where(
            and_(
                Contact.id == contact_id,
                Contact.company_id == company.id,
                Contact.deleted_at.is_(None),
            )
        )
    )
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    old_status = contact.status or "to_be_sent"
    new_status, success, message = transition_status(
        old_status, body.new_status, force=body.force
    )

    if not success:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid transition: {old_status} → {body.new_status}. {message}"
        )

    contact.status = new_status

    # Record activity for the status change
    activity = ContactActivity(
        contact_id=contact.id,
        company_id=contact.company_id,
        activity_type="status_changed",
        channel="manual",
        direction=None,
        source="operator",
        body=f"{old_status} → {new_status}",
        snippet=f"Status: {old_status} → {new_status}",
        activity_at=datetime.utcnow(),
    )
    session.add(activity)
    await session.commit()

    return StatusTransitionResponse(
        success=True,
        contact_id=contact.id,
        old_status=old_status,
        new_status=new_status,
        message=message,
    )
