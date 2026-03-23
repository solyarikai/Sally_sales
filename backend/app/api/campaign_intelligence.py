"""
Campaign Intelligence API — GOD_SEQUENCE.

Endpoints for viewing campaign scores, extracted patterns,
generating sequences, and pushing to SmartLead.
"""
import logging
from datetime import datetime, timezone
from typing import Optional, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session, async_session_maker
from app.models.campaign_intelligence import (
    CampaignSnapshot, CampaignPattern, CampaignIntelligenceRun, GeneratedSequence,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/campaign-intelligence", tags=["Campaign Intelligence"])

COMPANY_ID = 1  # Single-tenant


# ─── Request/Response schemas ──────────────────────────────────

class RefreshRequest(BaseModel):
    market: Optional[str] = None
    force_snapshots: bool = False
    min_leads: int = 50


class GenerateRequest(BaseModel):
    project_id: int
    campaign_name: Optional[str] = None
    custom_instructions: Optional[str] = None
    step_count: int = 5


class RejectRequest(BaseModel):
    notes: Optional[str] = None


class ScoreOut(BaseModel):
    campaign_id: int
    campaign_name: str
    platform: Optional[str] = None
    channel: Optional[str] = None
    project_id: Optional[int] = None
    leads_count: int
    total_replies: int
    warm_replies: int
    meetings_count: int
    questions_count: int
    warm_reply_rate: float
    meeting_rate: float
    quality_score: float
    market: str
    min_sample_size_met: bool


class SnapshotOut(BaseModel):
    id: int
    campaign_id: int
    campaign_name: str
    project_id: Optional[int] = None
    leads_count: int
    warm_replies: int
    meetings_count: int
    warm_reply_rate: Optional[float] = None
    meeting_rate: Optional[float] = None
    quality_score: Optional[float] = None
    market: Optional[str] = None
    sequence_step_count: Optional[int] = None
    sequence_total_days: Optional[int] = None
    sequence_steps: Optional[Any] = None
    is_latest: bool
    snapshotted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PatternOut(BaseModel):
    id: int
    pattern_type: str
    pattern_key: str
    title: str
    description: str
    market: Optional[str] = None
    channel: Optional[str] = None
    confidence: Optional[float] = None
    sample_size: Optional[int] = None
    version: int
    is_active: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class RunOut(BaseModel):
    id: int
    trigger: str
    market_filter: Optional[str] = None
    campaigns_analyzed: Optional[int] = None
    top_campaigns_count: Optional[int] = None
    patterns_created: Optional[int] = None
    patterns_updated: Optional[int] = None
    patterns_total: Optional[int] = None
    model_used: Optional[str] = None
    tokens_used: Optional[int] = None
    cost_usd: Optional[float] = None
    status: str
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class GeneratedOut(BaseModel):
    id: int
    project_id: int
    campaign_name: Optional[str] = None
    sequence_steps: Any
    sequence_step_count: Optional[int] = None
    rationale: Optional[str] = None
    status: str
    patterns_used: Optional[Any] = None
    model_used: Optional[str] = None
    tokens_used: Optional[int] = None
    cost_usd: Optional[float] = None
    pushed_campaign_id: Optional[int] = None
    pushed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ─── Read endpoints ──────────────────────────────────────────

@router.get("/scores/", response_model=list[ScoreOut])
async def get_campaign_scores(
    min_leads: int = Query(50, ge=1),
    market: Optional[str] = Query(None),
    project_id: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    """Ranked campaign performance scores (live computation)."""
    from app.services.campaign_intelligence_service import score_campaigns
    scores = await score_campaigns(session, COMPANY_ID, min_leads=min_leads, project_id=project_id, market=market)
    return scores[:limit]


@router.get("/snapshots/", response_model=list[SnapshotOut])
async def get_snapshots(
    campaign_id: Optional[int] = Query(None),
    project_id: Optional[int] = Query(None),
    latest_only: bool = Query(True),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    """Campaign snapshots with frozen metrics and sequence content."""
    filters = [CampaignSnapshot.company_id == COMPANY_ID]
    if campaign_id:
        filters.append(CampaignSnapshot.campaign_id == campaign_id)
    if project_id:
        filters.append(CampaignSnapshot.project_id == project_id)
    if latest_only:
        filters.append(CampaignSnapshot.is_latest == True)

    result = await session.execute(
        select(CampaignSnapshot)
        .where(*filters)
        .order_by(desc(CampaignSnapshot.quality_score))
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/patterns/", response_model=list[PatternOut])
async def get_patterns(
    pattern_type: Optional[str] = Query(None),
    market: Optional[str] = Query(None),
    active_only: bool = Query(True),
    session: AsyncSession = Depends(get_session),
):
    """Extracted campaign patterns (best practices)."""
    filters = [CampaignPattern.company_id == COMPANY_ID]
    if pattern_type:
        filters.append(CampaignPattern.pattern_type == pattern_type)
    if market:
        filters.append(CampaignPattern.market.in_([market, None]))
    if active_only:
        filters.append(CampaignPattern.is_active == True)

    result = await session.execute(
        select(CampaignPattern)
        .where(*filters)
        .order_by(CampaignPattern.pattern_type, desc(CampaignPattern.confidence))
    )
    return result.scalars().all()


@router.get("/patterns/{pattern_id}", response_model=PatternOut)
async def get_pattern(pattern_id: int, session: AsyncSession = Depends(get_session)):
    pattern = await session.get(CampaignPattern, pattern_id)
    if not pattern:
        raise HTTPException(404, "Pattern not found")
    return pattern


@router.get("/runs/", response_model=list[RunOut])
async def get_runs(
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """Intelligence extraction run history."""
    result = await session.execute(
        select(CampaignIntelligenceRun)
        .where(CampaignIntelligenceRun.company_id == COMPANY_ID)
        .order_by(desc(CampaignIntelligenceRun.created_at))
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/generated/", response_model=list[GeneratedOut])
async def get_generated_sequences(
    project_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """List generated sequences."""
    filters = [GeneratedSequence.company_id == COMPANY_ID]
    if project_id:
        filters.append(GeneratedSequence.project_id == project_id)
    if status:
        filters.append(GeneratedSequence.status == status)

    result = await session.execute(
        select(GeneratedSequence)
        .where(*filters)
        .order_by(desc(GeneratedSequence.created_at))
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/generated/{sequence_id}", response_model=GeneratedOut)
async def get_generated_sequence(sequence_id: int, session: AsyncSession = Depends(get_session)):
    gen = await session.get(GeneratedSequence, sequence_id)
    if not gen:
        raise HTTPException(404, "Generated sequence not found")
    return gen


# ─── Action endpoints ──────────────────────────────────────────

@router.post("/refresh/", response_model=RunOut)
async def refresh_intelligence(
    body: RefreshRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    """Trigger manual score + snapshot + pattern extraction cycle."""
    from app.services.campaign_intelligence_service import run_campaign_intelligence_cycle

    # Create a placeholder run to return immediately
    run = CampaignIntelligenceRun(
        company_id=COMPANY_ID,
        trigger="manual",
        market_filter=body.market,
        min_sample_size=body.min_leads,
        status="processing",
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)

    async def _run_in_background():
        from app.db import async_session_maker
        async with async_session_maker() as bg_session:
            await run_campaign_intelligence_cycle(
                company_id=COMPANY_ID,
                force=body.force_snapshots,
            )

    background_tasks.add_task(_run_in_background)
    return run


@router.post("/generate-sequence/", response_model=GeneratedOut)
async def generate_sequence_endpoint(
    body: GenerateRequest,
    session: AsyncSession = Depends(get_session),
):
    """Generate an optimized campaign sequence using patterns + project ICP."""
    from app.services.campaign_intelligence_service import generate_sequence

    try:
        gen = await generate_sequence(
            session=session,
            project_id=body.project_id,
            company_id=COMPANY_ID,
            campaign_name=body.campaign_name,
            custom_instructions=body.custom_instructions,
            step_count=body.step_count,
        )
        return gen
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/generated/{sequence_id}/approve/", response_model=GeneratedOut)
async def approve_sequence(sequence_id: int, session: AsyncSession = Depends(get_session)):
    """Approve a generated sequence for pushing to SmartLead."""
    gen = await session.get(GeneratedSequence, sequence_id)
    if not gen:
        raise HTTPException(404, "Generated sequence not found")
    if gen.status != "draft":
        raise HTTPException(400, f"Can only approve draft sequences (current: {gen.status})")

    gen.status = "approved"
    gen.reviewed_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(gen)
    return gen


@router.post("/generated/{sequence_id}/push/")
async def push_sequence(sequence_id: int, session: AsyncSession = Depends(get_session)):
    """Push approved sequence to SmartLead as a new DRAFT campaign."""
    from app.services.campaign_intelligence_service import push_sequence_to_smartlead

    try:
        result = await push_sequence_to_smartlead(session, sequence_id)
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(500, str(e))


@router.post("/generated/{sequence_id}/reject/", response_model=GeneratedOut)
async def reject_sequence(
    sequence_id: int,
    body: RejectRequest,
    session: AsyncSession = Depends(get_session),
):
    """Reject a generated sequence with optional feedback."""
    gen = await session.get(GeneratedSequence, sequence_id)
    if not gen:
        raise HTTPException(404, "Generated sequence not found")
    if gen.status not in ("draft", "approved"):
        raise HTTPException(400, f"Cannot reject sequence in '{gen.status}' status")

    gen.status = "rejected"
    gen.operator_notes = body.notes
    gen.reviewed_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(gen)
    return gen
