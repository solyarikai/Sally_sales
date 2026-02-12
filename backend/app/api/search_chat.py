"""
Chat-based search API — conversational interface for launching and managing searches.

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


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000)
    project_id: Optional[int] = None
    job_id: Optional[int] = None
    max_queries: int = Field(500, ge=1, le=5000)
    target_goal: int = Field(200, ge=1, le=10000)
    context: List[Dict[str, str]] = Field(default_factory=list, description="Prior conversation messages")


class ChatResponse(BaseModel):
    action: str  # "search_started" | "feedback_received" | "info" | "error"
    reply: str
    project_id: Optional[int] = None
    job_id: Optional[int] = None
    target_segments: Optional[str] = None
    suggestions: List[str] = Field(default_factory=list)


@router.post("/chat", response_model=ChatResponse)
async def chat_search(
    body: ChatRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """
    Conversational search interface.

    First message (no project_id): parses intent, creates project, launches search.
    Follow-up (with job_id): classifies feedback, updates knowledge.
    """
    if not settings.OPENAI_API_KEY and not settings.GEMINI_API_KEY:
        raise HTTPException(status_code=400, detail="No AI API key configured (need OPENAI_API_KEY or GEMINI_API_KEY)")

    # Follow-up message with existing job — handle as feedback
    if body.job_id:
        return await _handle_feedback(body, db, company)

    # First message or message with existing project — parse intent and launch
    return await _handle_new_search(body, background_tasks, db, company)


async def _handle_new_search(
    body: ChatRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession,
    company: Company,
) -> ChatResponse:
    """Parse intent within a project scope, update target definition, launch search."""
    from sqlalchemy import func as sqlfunc
    from app.models.domain import SearchResult, ProjectSearchKnowledge

    # Require project_id — chat always operates within a project
    project_id = body.project_id
    if not project_id:
        raise HTTPException(status_code=400, detail="Select a project first. Chat requires a project scope.")

    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.company_id == company.id,
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # ---- Build project context for AI ----
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

    # Top target domains (for context)
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

    # Parse the message with project context
    intent = await chat_search_service.parse_search_intent(
        body.message, body.context or None, project_context=project_context,
    )

    # Fallback: if AI didn't extract target_segments, use the raw message
    if not intent.get("target_segments"):
        logger.warning(f"AI failed to extract target_segments from: {body.message!r}, using raw message as fallback")
        intent["target_segments"] = body.message.strip()
        if not intent.get("reply"):
            intent["reply"] = f"Starting search: \"{body.message.strip()}\""

    # Update project's target segments with the new definition
    project.target_segments = intent["target_segments"]
    await db.commit()

    # Check search API keys
    if not settings.YANDEX_SEARCH_API_KEY or not settings.YANDEX_SEARCH_FOLDER_ID:
        return ChatResponse(
            action="error",
            reply="Search API keys not configured. Please configure Yandex Search API.",
            project_id=project_id,
            target_segments=intent["target_segments"],
        )

    # Create placeholder job
    job = SearchJob(
        company_id=company.id,
        status=SearchJobStatus.PENDING,
        search_engine=SearchEngine.YANDEX_API,
        queries_total=0,
        project_id=project_id,
        config={
            "max_queries": body.max_queries,
            "target_goal": body.target_goal,
            "target_segments": intent["target_segments"],
            "source": "chat",
        },
    )
    db.add(job)
    await db.commit()

    # Launch pipeline in background
    background_tasks.add_task(
        _run_chat_search_background,
        job.id, project_id, company.id,
        body.max_queries, body.target_goal,
    )

    # Build action-oriented reply — never ask questions, always confirm the search is running
    project_name = intent.get("project_name", "your target companies")
    geography = intent.get("geography", "")
    action_reply = intent.get("reply") or ""
    # Override conversational replies with action confirmation
    if not action_reply or "understand" in action_reply.lower() or "structured" in action_reply.lower() or "?" in action_reply:
        geo_suffix = f" in {geography}" if geography else ""
        action_reply = f"Searching for {project_name}{geo_suffix} — results will appear as websites are analyzed."

    return ChatResponse(
        action="search_started",
        reply=action_reply,
        project_id=project_id,
        job_id=job.id,
        target_segments=intent["target_segments"],
        suggestions=[
            "Exclude property portals and aggregators",
            "Focus on companies with their own portfolio",
            "Show me the top targets so far",
        ],
    )


async def _handle_feedback(
    body: ChatRequest,
    db: AsyncSession,
    company: Company,
) -> ChatResponse:
    """Process feedback for an active search."""

    # Verify job belongs to company
    result = await db.execute(
        select(SearchJob).where(
            SearchJob.id == body.job_id,
            SearchJob.company_id == company.id,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Search job not found")

    project_id = job.project_id
    target_segments = (job.config or {}).get("target_segments")

    # Load current knowledge
    knowledge_data = None
    if project_id:
        k_result = await db.execute(
            select(ProjectSearchKnowledge).where(
                ProjectSearchKnowledge.project_id == project_id
            )
        )
        knowledge = k_result.scalar_one_or_none()
        if knowledge:
            knowledge_data = {
                "good_query_patterns": knowledge.good_query_patterns or [],
                "bad_query_patterns": knowledge.bad_query_patterns or [],
                "anti_keywords": knowledge.anti_keywords or [],
                "industry_keywords": knowledge.industry_keywords or [],
            }

    # Parse the feedback
    feedback = await chat_search_service.parse_feedback(
        body.message,
        project_knowledge=knowledge_data,
        target_segments=target_segments,
    )

    # Apply knowledge updates
    updates = feedback.get("knowledge_updates", {})
    if updates and project_id:
        await _apply_knowledge_updates(db, project_id, updates)

    return ChatResponse(
        action="feedback_received",
        reply=feedback.get("reply", "Got it, I'll adjust the search accordingly."),
        project_id=project_id,
        job_id=body.job_id,
    )


async def _apply_knowledge_updates(
    db: AsyncSession,
    project_id: int,
    updates: Dict[str, Any],
):
    """Merge knowledge updates into ProjectSearchKnowledge."""
    result = await db.execute(
        select(ProjectSearchKnowledge).where(
            ProjectSearchKnowledge.project_id == project_id
        )
    )
    knowledge = result.scalar_one_or_none()

    if not knowledge:
        knowledge = ProjectSearchKnowledge(project_id=project_id)
        db.add(knowledge)

    # Merge lists (dedup)
    for field in ["anti_keywords", "industry_keywords", "good_query_patterns", "bad_query_patterns"]:
        new_items = updates.get(field, [])
        if new_items:
            existing = getattr(knowledge, field, None) or []
            merged = list(set(existing + new_items))
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
