"""Replies API — MCP's own reply data from MCPReply table.

Fully independent from main backend. No proxy needed.
Compatible with main app's TasksPage component (@main alias).
"""
from fastapi import APIRouter, Query, Depends
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from app.db import get_session
from app.models.reply import MCPReply
from app.models.project import Project
from app.models.user import MCPUser
from app.auth.dependencies import get_optional_user

router = APIRouter(prefix="/replies", tags=["replies"])


async def _get_user_project_ids(user, session) -> list[int]:
    if not user:
        return []
    result = await session.execute(select(Project.id).where(Project.user_id == user.id))
    return [pid for (pid,) in result.all()]


@router.get("")
@router.get("/")
async def list_replies(
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    needs_reply: Optional[bool] = None,
    needs_followup: Optional[bool] = None,
    category: Optional[str] = None,
    project_id: Optional[int] = None,
    campaign_name: Optional[str] = None,
    campaign_name_contains: Optional[str] = None,
    lead_email: Optional[str] = None,
    search: Optional[str] = None,
    received_since: Optional[str] = None,
    group_by_contact: Optional[bool] = None,
    include_all: Optional[bool] = None,
    user: MCPUser = Depends(get_optional_user),
    session: AsyncSession = Depends(get_session),
):
    """List replies from MCP's own database."""
    pids = await _get_user_project_ids(user, session)
    if not pids:
        return {"replies": [], "total": 0, "page": page, "page_size": page_size}

    query = select(MCPReply).where(MCPReply.project_id.in_(pids))

    if project_id:
        query = query.where(MCPReply.project_id == project_id)
    if category:
        query = query.where(MCPReply.category == category)
    if needs_reply is not None:
        query = query.where(MCPReply.needs_reply == needs_reply)
    if needs_followup:
        query = query.where(MCPReply.needs_reply == True, MCPReply.category.in_(["interested", "meeting_request", "question"]))
    if campaign_name:
        query = query.where(MCPReply.campaign_name == campaign_name)
    if campaign_name_contains:
        query = query.where(MCPReply.campaign_name.ilike(f"%{campaign_name_contains}%"))
    if lead_email:
        query = query.where(MCPReply.lead_email == lead_email)
    if search:
        from sqlalchemy import or_
        query = query.where(or_(
            MCPReply.lead_email.ilike(f"%{search}%"),
            MCPReply.lead_name.ilike(f"%{search}%"),
            MCPReply.lead_company.ilike(f"%{search}%"),
        ))

    # Count
    count_q = select(func.count()).select_from(query.subquery())
    total = (await session.execute(count_q)).scalar() or 0

    # Fetch
    query = query.order_by(desc(MCPReply.received_at)).offset((page - 1) * page_size).limit(page_size)
    result = await session.execute(query)
    replies = result.scalars().all()

    return {
        "replies": [
            {
                "id": r.id,
                "lead_email": r.lead_email,
                "lead_name": r.lead_name,
                "lead_company": r.lead_company,
                "company_name": r.lead_company,
                "campaign_name": r.campaign_name,
                "category": r.category,
                "category_confidence": r.category_confidence,
                "email_subject": r.email_subject,
                "email_body": r.reply_text,
                "reply_text": r.reply_text,
                "received_at": str(r.received_at) if r.received_at else None,
                "needs_reply": r.needs_reply,
                "approval_status": r.approval_status,
                "channel": r.channel,
                "source": r.source,
                "draft_reply": r.draft_reply,
            }
            for r in replies
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/counts")
async def reply_counts(
    project_id: Optional[int] = None,
    include_all: Optional[bool] = None,
    received_since: Optional[str] = None,
    campaign_name_contains: Optional[str] = None,
    user: MCPUser = Depends(get_optional_user),
    session: AsyncSession = Depends(get_session),
):
    """Reply counts by category from MCP's own data."""
    pids = await _get_user_project_ids(user, session)
    if not pids:
        return {"total": 0, "category_counts": {}}

    base = select(MCPReply.category, func.count(MCPReply.id)).where(MCPReply.project_id.in_(pids))
    if project_id:
        base = base.where(MCPReply.project_id == project_id)
    if campaign_name_contains:
        base = base.where(MCPReply.campaign_name.ilike(f"%{campaign_name_contains}%"))

    base = base.group_by(MCPReply.category)
    result = await session.execute(base)
    cats = {row[0]: row[1] for row in result.all() if row[0]}

    total_q = select(func.count(MCPReply.id)).where(MCPReply.project_id.in_(pids))
    if campaign_name_contains:
        total_q = total_q.where(MCPReply.campaign_name.ilike(f"%{campaign_name_contains}%"))
    total = (await session.execute(total_q)).scalar() or 0

    return {"total": total, "category_counts": cats}


@router.get("/{reply_id}")
async def get_reply(
    reply_id: int,
    user: MCPUser = Depends(get_optional_user),
    session: AsyncSession = Depends(get_session),
):
    """Single reply detail."""
    from fastapi import HTTPException
    reply = await session.get(MCPReply, reply_id)
    if not reply:
        raise HTTPException(404)
    # User-scope
    if user:
        pids = await _get_user_project_ids(user, session)
        if reply.project_id not in pids:
            raise HTTPException(404)
    return {
        "id": reply.id,
        "lead_email": reply.lead_email,
        "lead_name": reply.lead_name,
        "category": reply.category,
        "reply_text": reply.reply_text,
        "draft_reply": reply.draft_reply,
        "campaign_name": reply.campaign_name,
        "received_at": str(reply.received_at) if reply.received_at else None,
    }


@router.post("/sync")
async def trigger_sync(
    user: MCPUser = Depends(get_optional_user),
    session: AsyncSession = Depends(get_session),
):
    """Trigger reply sync for all tracked campaigns."""
    if not user:
        from fastapi import HTTPException
        raise HTTPException(401)
    from app.services.reply_service import sync_all_tracked_replies
    result = await sync_all_tracked_replies(user.id)
    return result
