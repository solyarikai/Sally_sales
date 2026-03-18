"""
Reply Intelligence API — structured classification of reply conversations.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select, and_, func, desc, asc, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.db import get_session, async_session_maker
from app.models.reply import ProcessedReply
from app.models.reply_analysis import ReplyAnalysis
from app.models.contact import Contact
from app.services.intelligence_service import (
    analyze_project_replies,
    get_intelligence_summary,
    get_intent_group,
    INTENT_GROUPS,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/intelligence", tags=["Intelligence"])


# ─── Response schemas ──────────────────────────────────────────

class ReplyAnalysisOut(BaseModel):
    id: int
    processed_reply_id: int
    project_id: int
    offer_responded_to: Optional[str] = None
    intent: Optional[str] = None
    warmth_score: Optional[int] = None
    campaign_segment: Optional[str] = None
    sequence_type: Optional[str] = None
    language: Optional[str] = None
    reasoning: Optional[str] = None
    interests: Optional[str] = None
    tags: Optional[List[str]] = None
    geo_tags: Optional[List[str]] = None
    # Joined from ProcessedReply
    lead_email: Optional[str] = None
    lead_name: Optional[str] = None
    lead_company: Optional[str] = None
    campaign_name: Optional[str] = None
    reply_text: Optional[str] = None
    category: Optional[str] = None
    received_at: Optional[str] = None
    approval_status: Optional[str] = None
    intent_group: Optional[str] = None
    # Joined from Contact
    lead_domain: Optional[str] = None
    contact_id: Optional[int] = None

    class Config:
        from_attributes = True


class SummaryOut(BaseModel):
    total: int
    by_group: dict
    by_offer: dict
    by_segment: dict
    by_intent: dict
    by_tag: Optional[dict] = None
    by_geo: Optional[dict] = None


class AnalyzeResult(BaseModel):
    classified: int
    ai_classified: Optional[int] = None
    project_id: int


# ─── Helpers ──────────────────────────────────────────────────

def _parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


# ─── Endpoints ─────────────────────────────────────────────────

@router.get("/", response_model=List[ReplyAnalysisOut])
async def list_intelligence(
    project_id: int = Query(..., description="Project ID"),
    intent_group: Optional[str] = Query(None, description="warm|questions|soft_objection|hard_objection|noise"),
    intent: Optional[str] = Query(None, description="Comma-separated individual intents"),
    offer: Optional[str] = Query(None, description="Comma-separated: paygate,payout,otc,general"),
    segment: Optional[str] = Query(None, description="Comma-separated segment filter"),
    tags: Optional[str] = Query(None, description="Comma-separated tag filter (array overlap)"),
    geo: Optional[str] = Query(None, description="Comma-separated geography tag filter (array overlap)"),
    interests_search: Optional[str] = Query(None, description="Full-text search in interests"),
    warmth_min: Optional[int] = Query(None, ge=0, le=5),
    warmth_max: Optional[int] = Query(None, ge=0, le=5),
    language: Optional[str] = Query(None),
    search: Optional[str] = Query(None, description="Search in reply text, lead name, company"),
    date_from: Optional[str] = Query(None, description="ISO date filter start"),
    date_to: Optional[str] = Query(None, description="ISO date filter end"),
    sort_by: Optional[str] = Query("warmth_desc", description="warmth_desc|date_desc|intent_group"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    """List analyzed replies with filtering and sorting."""
    # NOTE: Contact join removed — was doing func.lower() on both sides, defeating indexes
    # and causing full table scan on 194K contacts. Now batch-lookup contacts separately.
    query = (
        select(
            ReplyAnalysis,
            ProcessedReply.lead_email,
            (ProcessedReply.lead_first_name + " " + func.coalesce(ProcessedReply.lead_last_name, "")).label("lead_name"),
            ProcessedReply.lead_company,
            ProcessedReply.campaign_name,
            ProcessedReply.reply_text,
            ProcessedReply.category,
            ProcessedReply.received_at,
            ProcessedReply.approval_status,
        )
        .join(ProcessedReply, ReplyAnalysis.processed_reply_id == ProcessedReply.id)
        .where(ReplyAnalysis.project_id == project_id)
    )

    filters = []

    if intent_group:
        intents_list = INTENT_GROUPS.get(intent_group, [])
        if intents_list:
            filters.append(ReplyAnalysis.intent.in_(intents_list))

    if intent:
        intent_vals = [i.strip() for i in intent.split(",")]
        filters.append(ReplyAnalysis.intent.in_(intent_vals))

    if offer:
        offers = [o.strip() for o in offer.split(",")]
        filters.append(ReplyAnalysis.offer_responded_to.in_(offers))

    if segment:
        segments = [s.strip() for s in segment.split(",")]
        filters.append(ReplyAnalysis.campaign_segment.in_(segments))

    if tags:
        tag_list = [t.strip() for t in tags.split(",")]
        filters.append(ReplyAnalysis.tags.overlap(tag_list))

    if geo:
        geo_list = [g.strip() for g in geo.split(",")]
        filters.append(ReplyAnalysis.geo_tags.overlap(geo_list))

    if interests_search:
        filters.append(ReplyAnalysis.interests.ilike(f"%{interests_search}%"))

    if warmth_min is not None:
        filters.append(ReplyAnalysis.warmth_score >= warmth_min)

    if warmth_max is not None:
        filters.append(ReplyAnalysis.warmth_score <= warmth_max)

    if language:
        filters.append(ReplyAnalysis.language == language)

    if search:
        search_filter = f"%{search}%"
        filters.append(
            (ProcessedReply.reply_text.ilike(search_filter))
            | (ProcessedReply.lead_first_name.ilike(search_filter))
            | (ProcessedReply.lead_last_name.ilike(search_filter))
            | (ProcessedReply.lead_company.ilike(search_filter))
        )

    dt_from = _parse_date(date_from)
    dt_to = _parse_date(date_to)
    if dt_from:
        filters.append(ProcessedReply.received_at >= dt_from)
    if dt_to:
        filters.append(ProcessedReply.received_at <= dt_to)

    if filters:
        query = query.where(and_(*filters))

    if sort_by == "warmth_desc":
        query = query.order_by(desc(ReplyAnalysis.warmth_score), desc(ProcessedReply.received_at))
    elif sort_by == "date_desc":
        query = query.order_by(desc(ProcessedReply.received_at))
    else:
        query = query.order_by(desc(ReplyAnalysis.warmth_score), desc(ProcessedReply.received_at))

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await session.execute(query)
    rows = result.all()

    # Batch-lookup contacts by email (single IN query instead of per-row JOIN)
    emails = {row[1].lower() for row in rows if row[1]}
    contact_map: dict = {}
    if emails:
        contact_q = select(Contact.id, Contact.email, Contact.domain).where(
            func.lower(Contact.email).in_(list(emails))
        )
        for cid, cemail, cdomain in (await session.execute(contact_q)).all():
            contact_map[cemail.lower()] = (cid, cdomain)

    items = []
    for row in rows:
        analysis = row[0]
        email = row[1]
        cinfo = contact_map.get(email.lower() if email else "", (None, None))
        items.append(ReplyAnalysisOut(
            id=analysis.id,
            processed_reply_id=analysis.processed_reply_id,
            project_id=analysis.project_id,
            offer_responded_to=analysis.offer_responded_to,
            intent=analysis.intent,
            warmth_score=analysis.warmth_score,
            campaign_segment=analysis.campaign_segment,
            sequence_type=analysis.sequence_type,
            language=analysis.language,
            reasoning=analysis.reasoning,
            interests=analysis.interests,
            tags=analysis.tags,
            geo_tags=analysis.geo_tags,
            lead_email=email,
            lead_name=row[2],
            lead_company=row[3],
            campaign_name=row[4],
            reply_text=row[5],
            category=row[6],
            received_at=str(row[7]) if row[7] else None,
            approval_status=row[8],
            intent_group=get_intent_group(analysis.intent or "empty"),
            lead_domain=cinfo[1],
            contact_id=cinfo[0],
        ))

    return items


@router.get("/summary/", response_model=SummaryOut)
async def intelligence_summary(
    project_id: int = Query(..., description="Project ID"),
    date_from: Optional[str] = Query(None, description="ISO date filter start"),
    date_to: Optional[str] = Query(None, description="ISO date filter end"),
    session: AsyncSession = Depends(get_session),
):
    """Get summary statistics for the intelligence dashboard."""
    return await get_intelligence_summary(
        session, project_id,
        date_from=_parse_date(date_from),
        date_to=_parse_date(date_to),
    )


@router.post("/analyze/", response_model=AnalyzeResult)
async def trigger_analysis(
    project_id: int = Query(..., description="Project ID"),
    rebuild: bool = Query(False, description="Delete existing and re-classify all"),
    use_ai: bool = Query(True, description="Use AI (Gemini) for classification"),
    session: AsyncSession = Depends(get_session),
):
    """Classify all unanalyzed replies for a project. Use rebuild=true to re-classify everything."""
    if rebuild:
        from sqlalchemy import delete
        await session.execute(
            delete(ReplyAnalysis).where(ReplyAnalysis.project_id == project_id)
        )
        await session.flush()
        logger.info(f"Deleted all reply_analysis for project {project_id}")

    result = await analyze_project_replies(session, project_id, use_ai=use_ai)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/tags/")
async def list_tags(
    project_id: int = Query(..., description="Project ID"),
    session: AsyncSession = Depends(get_session),
):
    """Get all unique tags with counts for a project."""
    query = text("""
        SELECT tag, COUNT(*) as cnt
        FROM reply_analysis, unnest(tags) AS tag
        WHERE project_id = :pid AND tags IS NOT NULL
        GROUP BY tag
        ORDER BY cnt DESC
        LIMIT 100
    """)
    result = await session.execute(query, {"pid": project_id})
    rows = result.all()
    return [{"tag": row[0], "count": row[1]} for row in rows]


@router.get("/campaigns/")
async def intelligence_campaigns(
    project_id: int = Query(..., description="Project ID"),
    date_from: Optional[str] = Query(None, description="ISO date filter start"),
    date_to: Optional[str] = Query(None, description="ISO date filter end"),
    session: AsyncSession = Depends(get_session),
):
    """Campaign-level breakdown for debug panel — reply counts per campaign with channel info."""
    query = (
        select(
            ProcessedReply.campaign_name,
            ProcessedReply.source,
            ProcessedReply.channel,
            func.count().label("reply_count"),
        )
        .join(ReplyAnalysis, ReplyAnalysis.processed_reply_id == ProcessedReply.id)
        .where(ReplyAnalysis.project_id == project_id)
        .group_by(ProcessedReply.campaign_name, ProcessedReply.source, ProcessedReply.channel)
        .order_by(desc(func.count()))
    )

    dt_from = _parse_date(date_from)
    dt_to = _parse_date(date_to)
    if dt_from:
        query = query.where(ProcessedReply.received_at >= dt_from)
    if dt_to:
        query = query.where(ProcessedReply.received_at <= dt_to)

    result = await session.execute(query)
    rows = result.all()

    campaigns = []
    total = 0
    for name, source, channel, count in rows:
        total += count
        campaigns.append({
            "campaign_name": name or "Unknown",
            "source": source or "smartlead",
            "channel": channel or "email",
            "reply_count": count,
        })

    return {
        "campaigns": campaigns,
        "total_replies": total,
        "campaign_count": len(campaigns),
    }


@router.get("/count/")
async def intelligence_count(
    project_id: int = Query(..., description="Project ID"),
    session: AsyncSession = Depends(get_session),
):
    """Get total analyzed count for a project."""
    query = select(func.count()).where(ReplyAnalysis.project_id == project_id)
    result = await session.execute(query)
    count = result.scalar() or 0
    return {"count": count, "project_id": project_id}
