"""
Chat-based search API — conversational interface for launching and managing searches.

Unified intent routing: every message goes through AI classification into
search (new pipeline), refine (adjust + re-launch), or question (info only).

Endpoints:
- POST /search/chat — Send a message to start or manage a search
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import logging

from app.db import get_session, async_session_maker
from app.api.companies import get_required_company
from app.models.user import Company
from app.models.contact import Project
from app.models.domain import (
    SearchJob, SearchJobStatus, SearchEngine,
    ProjectSearchKnowledge,
)
from app.services.chat_search_service import chat_search_service
from app.core.config import settings

router = APIRouter(prefix="/search", tags=["search"])
logger = logging.getLogger(__name__)

# Max items per knowledge list to prevent unbounded growth
_MAX_KNOWLEDGE_ITEMS = 50


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000)
    project_id: Optional[int] = None
    max_queries: int = Field(500, ge=1, le=5000)
    target_goal: int = Field(200, ge=1, le=10000)
    context: List[Dict[str, str]] = Field(default_factory=list, description="Prior conversation messages")


class ChatResponse(BaseModel):
    action: str  # "search_started" | "info" | "error"
    reply: str
    project_id: Optional[int] = None
    job_id: Optional[int] = None
    target_segments: Optional[str] = None
    suggestions: List[str] = Field(default_factory=list)
    preserve_results: bool = True


@router.post("/chat", response_model=ChatResponse)
async def chat_search(
    body: ChatRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """
    Conversational search interface.

    Every message is classified by AI into one of:
    - search: cancel running jobs, set new target_segments, launch pipeline, preserve_results=false
    - refine: cancel running jobs, apply knowledge updates, demote by keywords, launch pipeline, preserve_results=true
    - question: return reply only, no pipeline changes
    """
    if not settings.OPENAI_API_KEY:
        raise HTTPException(status_code=400, detail="OPENAI_API_KEY not configured")

    # 1. Load project context
    project_id = body.project_id
    if not project_id:
        raise HTTPException(status_code=400, detail="Select a project first. Chat requires a project scope.")

    from sqlalchemy import func as sqlfunc
    from app.models.domain import SearchResult

    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.company_id == company.id,
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Existing results summary
    total_q = await db.execute(
        select(sqlfunc.count()).select_from(SearchResult)
        .where(SearchResult.project_id == project_id)
    )
    total_results = total_q.scalar() or 0

    targets_q = await db.execute(
        select(sqlfunc.count()).select_from(SearchResult)
        .where(SearchResult.project_id == project_id, SearchResult.is_target == True)
    )
    total_targets = targets_q.scalar() or 0

    # Existing knowledge
    k_result = await db.execute(
        select(ProjectSearchKnowledge).where(ProjectSearchKnowledge.project_id == project_id)
    )
    knowledge = k_result.scalar_one_or_none()

    # Top target domains
    top_targets_q = await db.execute(
        select(SearchResult.domain, SearchResult.company_info)
        .where(SearchResult.project_id == project_id, SearchResult.is_target == True)
        .order_by(SearchResult.confidence.desc())
        .limit(10)
    )
    top_targets = [
        f"{row.domain} ({(row.company_info or {}).get('name', 'N/A')})"
        for row in top_targets_q.fetchall()
    ]

    project_context = {
        "project_name": project.name,
        "existing_target_segments": project.target_segments,
        "total_results_analyzed": total_results,
        "total_targets_found": total_targets,
        "top_targets": top_targets[:10],
        "knowledge": {
            "anti_keywords": (knowledge.anti_keywords or [])[:20] if knowledge else [],
            "industry_keywords": (knowledge.industry_keywords or [])[:20] if knowledge else [],
        },
    }

    # 2. AI classify_and_process
    classified = await chat_search_service.classify_and_process(
        body.message, body.context or None, project_context=project_context,
    )

    intent = classified.get("intent", "search" if total_results == 0 else "refine")
    reply = classified.get("reply", "")
    suggestions = classified.get("suggestions", [])
    knowledge_updates = classified.get("knowledge_updates", {})
    new_target_segments = classified.get("target_segments")
    # Normalize: LLM sometimes returns dict instead of string
    if isinstance(new_target_segments, dict):
        new_target_segments = "\n".join(f"{k}: {v}" for k, v in new_target_segments.items())
    # Normalize: empty string → None
    if isinstance(new_target_segments, str) and not new_target_segments.strip():
        new_target_segments = None

    # 3. Route by intent
    if intent == "question":
        return ChatResponse(
            action="info",
            reply=reply or f"Project has {total_results} results, {total_targets} targets.",
            project_id=project_id,
            suggestions=suggestions,
            preserve_results=True,
        )

    # Track the effective target_segments BEFORE any commits (avoids reading expired ORM attribute)
    effective_target_segments = project.target_segments

    # Both "search" and "refine" cancel running jobs and launch a new pipeline
    cancelled_count = await _cancel_project_jobs(db, project_id)
    if cancelled_count > 0:
        logger.info(f"Cancelled {cancelled_count} running jobs for project {project_id}")

    if intent == "refine":
        # Apply knowledge updates
        if knowledge_updates:
            await _apply_knowledge_updates(db, project_id, knowledge_updates)

        # Demote by anti_keywords
        demoted = 0
        anti_kws = knowledge_updates.get("anti_keywords", [])
        if anti_kws:
            from app.services.company_search_service import company_search_service
            demoted = await company_search_service.demote_by_keywords(db, project_id, anti_kws)

        # If AI provided updated target_segments (e.g. "also look in France"), apply them
        if new_target_segments:
            project.target_segments = new_target_segments
            effective_target_segments = new_target_segments
            await db.commit()

        # Build reply with demotion info
        if demoted > 0 and reply:
            reply = f"{reply} Demoted {demoted} results matching excluded keywords."
        elif demoted > 0:
            reply = f"Demoted {demoted} results matching excluded keywords. Launching refined search."

        preserve_results = True
    else:
        # intent == "search"
        if not new_target_segments:
            # Fallback: use raw message
            new_target_segments = body.message.strip()
            if not reply:
                reply = f'Starting search: "{body.message.strip()}"'

        project.target_segments = new_target_segments
        effective_target_segments = new_target_segments
        await db.commit()
        preserve_results = False

    # Check search API keys
    if not settings.YANDEX_SEARCH_API_KEY or not settings.YANDEX_SEARCH_FOLDER_ID:
        return ChatResponse(
            action="error",
            reply="Search API keys not configured. Please configure Yandex Search API.",
            project_id=project_id,
            target_segments=effective_target_segments,
            preserve_results=preserve_results,
        )

    # For refine: add target_goal ON TOP of existing targets so pipeline always searches more
    # Cap at 3x requested goal to prevent unbounded growth on repeated refines
    effective_target_goal = body.target_goal
    if intent == "refine":
        effective_target_goal = min(total_targets + body.target_goal, body.target_goal * 3)

    # Create job and launch pipeline
    job = SearchJob(
        company_id=company.id,
        status=SearchJobStatus.PENDING,
        search_engine=SearchEngine.YANDEX_API,
        queries_total=0,
        project_id=project_id,
        config={
            "max_queries": body.max_queries,
            "target_goal": effective_target_goal,
            "target_segments": effective_target_segments,
            "source": "chat",
            "intent": intent,
        },
    )
    db.add(job)
    await db.commit()

    background_tasks.add_task(
        _run_chat_search_background,
        job.id, project_id, company.id,
        body.max_queries, effective_target_goal,
    )

    # Ensure reply is action-oriented (only replace if reply is empty)
    if not reply:
        reply = f"Launching {'refined ' if intent == 'refine' else ''}search — results will appear as websites are analyzed."

    return ChatResponse(
        action="search_started",
        reply=reply,
        project_id=project_id,
        job_id=job.id,
        target_segments=effective_target_segments,
        suggestions=suggestions or [
            "Exclude property portals and aggregators",
            "Focus on companies with their own portfolio",
            "Show me the top targets so far",
        ],
        preserve_results=preserve_results,
    )


async def _cancel_project_jobs(db: AsyncSession, project_id: int) -> int:
    """Cancel all PENDING/RUNNING jobs for a project. Returns count cancelled."""
    result = await db.execute(
        select(SearchJob).where(
            SearchJob.project_id == project_id,
            SearchJob.status.in_([SearchJobStatus.PENDING, SearchJobStatus.RUNNING]),
        )
    )
    jobs = list(result.scalars().all())
    for job in jobs:
        job.status = SearchJobStatus.CANCELLED
    if jobs:
        await db.commit()
    return len(jobs)


async def _apply_knowledge_updates(
    db: AsyncSession,
    project_id: int,
    updates: Dict[str, Any],
):
    """Merge knowledge updates into ProjectSearchKnowledge. Trims lists to _MAX_KNOWLEDGE_ITEMS."""
    result = await db.execute(
        select(ProjectSearchKnowledge).where(
            ProjectSearchKnowledge.project_id == project_id
        )
    )
    knowledge = result.scalar_one_or_none()

    if not knowledge:
        knowledge = ProjectSearchKnowledge(project_id=project_id)
        db.add(knowledge)

    for field in ["anti_keywords", "industry_keywords", "good_query_patterns", "bad_query_patterns"]:
        new_items = updates.get(field, [])
        if isinstance(new_items, str):
            new_items = [new_items]
        if not isinstance(new_items, list):
            continue
        if new_items:
            existing = getattr(knowledge, field, None) or []
            merged = list(set(existing + new_items))
            # Trim to max size, keeping newest items (appended at end)
            if len(merged) > _MAX_KNOWLEDGE_ITEMS:
                merged = merged[-_MAX_KNOWLEDGE_ITEMS:]
            setattr(knowledge, field, merged)

    await db.commit()


async def _run_chat_search_background(
    job_id: int,
    project_id: int,
    company_id: int,
    max_queries: int,
    target_goal: int,
):
    """Background task for chat-initiated search."""
    from app.services.company_search_service import company_search_service

    try:
        async with async_session_maker() as session:
            try:
                await company_search_service.run_project_search(
                    session=session,
                    project_id=project_id,
                    company_id=company_id,
                    max_queries=max_queries,
                    target_goal=target_goal,
                    job_id=job_id,
                )
            except Exception as e:
                logger.error(f"Chat search pipeline failed: {e}")
                result = await session.execute(
                    select(SearchJob).where(SearchJob.id == job_id)
                )
                job = result.scalar_one_or_none()
                if job and job.status not in (SearchJobStatus.COMPLETED, SearchJobStatus.CANCELLED):
                    job.status = SearchJobStatus.FAILED
                    job.error_message = str(e)[:500]
                    await session.commit()
    except Exception as e:
        logger.error(f"Background chat search crashed: {e}")
