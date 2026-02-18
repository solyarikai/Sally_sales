"""
Chat-based search API — universal conversational interface for the lead generation platform.

API-first design: any client (web UI, Slack, Telegram) sends a text message
and receives a structured action response. Gemini 2.5 Pro parses intent.

Endpoints:
- POST /search/chat — Send a message to start or manage a search
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
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
from app.models.chat import ProjectChatMessage
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
    action: str
    reply: str
    project_id: Optional[int] = None
    job_id: Optional[int] = None
    target_segments: Optional[str] = None
    suggestions: List[str] = Field(default_factory=list)
    data: Optional[Dict[str, Any]] = None


# ---- Chat persistence helpers ----

async def _load_chat_context(db: AsyncSession, project_id: int, limit: int = 20) -> List[Dict[str, str]]:
    """Load recent non-system messages from DB as [{role, content}]."""
    result = await db.execute(
        select(ProjectChatMessage.role, ProjectChatMessage.content)
        .where(
            ProjectChatMessage.project_id == project_id,
            ProjectChatMessage.role.in_(["user", "assistant"]),
        )
        .order_by(ProjectChatMessage.created_at.desc())
        .limit(limit)
    )
    rows = result.fetchall()
    return [{"role": r.role, "content": r.content} for r in reversed(rows)]


async def _save_chat_message(
    db: AsyncSession, project_id: int, role: str, content: str, client_id: Optional[str] = None,
):
    """Insert a chat message. ON CONFLICT DO NOTHING for dedup via client_id."""
    if client_id:
        stmt = pg_insert(ProjectChatMessage).values(
            project_id=project_id, role=role, content=content, client_id=client_id,
        ).on_conflict_do_nothing(index_elements=["project_id", "client_id"])
        await db.execute(stmt)
    else:
        db.add(ProjectChatMessage(project_id=project_id, role=role, content=content))


# ---- Chat message endpoints ----

class SaveChatMessagesRequest(BaseModel):
    messages: List[Dict[str, str]] = Field(..., description="[{role, content, client_id}]")


@router.get("/chat/messages/{project_id}")
async def get_chat_messages(
    project_id: int,
    limit: int = Query(200, ge=1, le=1000),
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Load chat history for a project."""
    # Verify project belongs to company
    proj = await db.execute(
        select(Project).where(Project.id == project_id, Project.company_id == company.id)
    )
    if not proj.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(ProjectChatMessage)
        .where(ProjectChatMessage.project_id == project_id)
        .order_by(ProjectChatMessage.created_at.asc())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "role": r.role,
            "content": r.content,
            "client_id": r.client_id,
            "timestamp": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.post("/chat/messages/{project_id}")
async def save_chat_messages(
    project_id: int,
    body: SaveChatMessagesRequest,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Bulk-save chat messages (system messages, SSE events, etc.)."""
    proj = await db.execute(
        select(Project).where(Project.id == project_id, Project.company_id == company.id)
    )
    if not proj.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    for msg in body.messages:
        await _save_chat_message(
            db, project_id,
            role=msg.get("role", "system"),
            content=msg.get("content", ""),
            client_id=msg.get("client_id"),
        )
    await db.commit()
    return {"saved": len(body.messages)}


@router.post("/chat")
async def chat_search(
    body: ChatRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """
    Universal conversational interface. Gemini 2.5 Pro parses any message
    into a structured action: start_search, stop, status, push, show_targets,
    show_stats, search (new ICP), or info.

    Accepts natural language in English and Russian. Examples:
    - "run yandex on real_estate turkey, 2000 queries, push after"
    - "show stats by segment"
    - "how many targets do we have?"
    - "push all contacts to smartlead"
    - "stop"
    """
    if not settings.OPENAI_API_KEY and not settings.GEMINI_API_KEY:
        raise HTTPException(status_code=400, detail="No AI API key configured (need OPENAI_API_KEY or GEMINI_API_KEY)")

    project_id = body.project_id

    # Build project context for the AI parser
    project_context = None
    project = None
    if project_id:
        result = await db.execute(
            select(Project).where(Project.id == project_id, Project.company_id == company.id)
        )
        project = result.scalar_one_or_none()
        if project:
            project_context = await _build_project_context(db, project, company)

    # --- Load chat context from DB (replaces body.context) ---
    db_context = None
    if project_id:
        db_context = await _load_chat_context(db, project_id)
        # Save user message
        await _save_chat_message(db, project_id, "user", body.message, f"user-{project_id}-{body.message[:40]}")

    # --- Parse intent with Gemini 2.5 Pro ---
    parsed = await chat_search_service.parse_chat_action(
        message=body.message,
        project_context=project_context,
        context=db_context or body.context or None,
    )
    action = parsed.get("action", "info")
    logger.info(f"Chat action parsed: action={action}, engine={parsed.get('engine')}, "
                f"segments={parsed.get('segments')}, geos={parsed.get('geos')}")

    # --- Route to handler ---
    if action == "start_search":
        response = await _handle_start_search(parsed, body, background_tasks, db, company, project)
    elif action == "stop":
        response = await _handle_stop(parsed, body, db, company, project)
    elif action == "status":
        response = await _handle_status(parsed, body, db, company, project)
    elif action == "push":
        response = await _handle_push(parsed, body, background_tasks, db, company, project)
    elif action == "show_targets":
        response = await _handle_show_targets(parsed, body, db, company, project)
    elif action == "show_stats":
        response = await _handle_stats(parsed, body, db, company, project)
    elif action == "lookup_domain":
        response = await _handle_lookup_domain(parsed, body, db, company, project)
    elif action == "show_config":
        response = await _handle_show_config(parsed, body, db, company, project)
    elif action == "edit_config":
        response = await _handle_edit_config(parsed, body, db, company, project)
    elif action == "show_knowledge":
        response = await _handle_show_knowledge(parsed, body, db, company, project)
    elif action == "update_knowledge":
        response = await _handle_update_knowledge(parsed, body, db, company, project)
    elif action == "ask":
        response = await _handle_ask(parsed, body, db, company, project)
    elif action == "search":
        response = await _handle_new_search(body, background_tasks, db, company)
    else:
        response = ChatResponse(
            action="info",
            reply=parsed.get("reply", "I'm not sure what you need. Try: 'show stats', 'run yandex search', or 'push to smartlead'."),
            project_id=project_id,
            suggestions=_build_suggestions(project_context),
        )

    # --- Save assistant reply to DB ---
    resp_project_id = response.project_id or project_id
    if resp_project_id and response.reply:
        await _save_chat_message(db, resp_project_id, "assistant", response.reply)
        await db.commit()

    return response


async def _build_project_context(db: AsyncSession, project: Project, company: Company) -> Dict[str, Any]:
    """Build rich project context for the AI intent parser."""
    from sqlalchemy import text as sql_text
    from app.api.pipeline import _running_pipelines
    from app.services.search_config_service import search_config_service

    pid = project.id
    cid = company.id

    stats = await db.execute(sql_text("""
        SELECT
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE is_target) as targets,
            COUNT(*) FILTER (WHERE apollo_enriched_at IS NOT NULL) as enriched
        FROM discovered_companies
        WHERE project_id = :pid AND company_id = :cid
    """), {"pid": pid, "cid": cid})
    row = stats.fetchone()

    contacts_stats = await db.execute(sql_text("""
        SELECT
            COUNT(*) FILTER (WHERE campaigns IS NOT NULL AND campaigns::text NOT IN ('null', '[]', '{}', '')) as in_campaigns,
            COUNT(*) FILTER (WHERE (campaigns IS NULL OR campaigns::text IN ('null', '[]', '{}', '')) AND source IN ('pipeline', 'smartlead_pipeline_push')) as unpushed
        FROM contacts
        WHERE project_id = :pid AND deleted_at IS NULL
    """), {"pid": pid})
    c_row = contacts_stats.fetchone()

    # Top segments summary
    seg_stats = await db.execute(sql_text("""
        SELECT sq.segment, SUM(sq.targets_found) as targets, COUNT(sq.id) as queries
        FROM search_queries sq
        JOIN search_jobs sj ON sq.search_job_id = sj.id
        WHERE sj.project_id = :pid AND sq.segment IS NOT NULL
        GROUP BY sq.segment HAVING SUM(sq.targets_found) > 0
        ORDER BY SUM(sq.targets_found) DESC LIMIT 5
    """), {"pid": pid})
    seg_rows = seg_stats.fetchall()
    top_segments = ", ".join(f"{r.segment}({r.targets} targets/{r.queries}q)" for r in seg_rows) if seg_rows else "none yet"

    # Cost summary
    cost_stats = await db.execute(sql_text("""
        SELECT sj.search_engine, COUNT(sq.id) as queries
        FROM search_queries sq
        JOIN search_jobs sj ON sq.search_job_id = sj.id
        WHERE sj.project_id = :pid
        GROUP BY sj.search_engine
    """), {"pid": pid})
    cost_parts = []
    for cr in cost_stats.fetchall():
        eng = cr.search_engine
        q = cr.queries
        if eng == "YANDEX_API":
            cost_parts.append(f"Yandex: {q} queries (${round(q * 0.25 / 1000, 2)})")
        elif eng == "GOOGLE_SERP":
            cost_parts.append(f"Google: {q} queries (${round(q * 3.50 / 1000, 2)})")
    cost_summary = ", ".join(cost_parts) if cost_parts else "$0"

    # Pipeline status
    progress = _running_pipelines.get(pid, {})
    pipeline_running = progress.get("running", False)
    pipeline_phase = progress.get("phase", "")

    # Load search config for dynamic segments/geos in chat
    config = await search_config_service.get_config(db, pid)

    # Load knowledge summary for enriched AI context
    from app.services.project_knowledge_service import project_knowledge_service
    knowledge_summary = await project_knowledge_service.get_summary(db, pid)

    return {
        "project_id": pid,
        "project_name": project.name,
        "total_discovered": row.total if row else 0,
        "total_targets": row.targets if row else 0,
        "total_enriched": row.enriched if row else 0,
        "contacts_in_campaigns": c_row.in_campaigns if c_row else 0,
        "unpushed_contacts": c_row.unpushed if c_row else 0,
        "top_segments": top_segments,
        "cost_summary": cost_summary,
        "pipeline_running": pipeline_running,
        "pipeline_phase": pipeline_phase,
        "search_config": config or {},
        "knowledge_summary": knowledge_summary,
    }


def _build_suggestions(project_context: Optional[Dict[str, Any]]) -> List[str]:
    """Generate contextual suggestions based on project state."""
    if not project_context:
        return ["show knowledge", "show stats by segment", "run yandex search"]

    suggestions = []
    if project_context.get("pipeline_running"):
        suggestions.extend(["pipeline status", "stop"])
    else:
        if project_context.get("total_targets", 0) > 0:
            suggestions.append("show stats by segment")
        if project_context.get("unpushed_contacts", 0) > 0:
            suggestions.append(f"push {project_context['unpushed_contacts']} contacts to smartlead")
        suggestions.append("run yandex on best segments")
        if project_context.get("total_targets", 0) > 0:
            suggestions.append("show funnel")
        suggestions.append("show knowledge")

    return suggestions[:4]


async def _handle_lookup_domain(
    parsed: Dict, body: ChatRequest, db: AsyncSession, company: Company, project: Optional[Project],
) -> ChatResponse:
    """Look up everything known about specific domain(s)."""
    from app.services.domain_lookup_service import domain_lookup_service

    domains = parsed.get("domains") or []
    if not domains:
        return ChatResponse(
            action="info",
            reply="Please specify a domain to look up, e.g. 'what do we know about company.com'",
            project_id=body.project_id,
            suggestions=["show targets", "show funnel"],
        )

    project_id = project.id if project else None
    profiles = await domain_lookup_service.lookup(db, domains, company.id, project_id)
    markdown = domain_lookup_service.format_as_markdown(profiles)

    return ChatResponse(
        action="domain_lookup",
        reply=markdown,
        project_id=body.project_id,
        data=profiles,
        suggestions=["show targets", "push to smartlead", "show funnel"],
    )


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

    # Load context from DB instead of body.context
    db_context = await _load_chat_context(db, project_id)

    # Parse the message with project context
    intent = await chat_search_service.parse_search_intent(
        body.message, db_context or None, project_context=project_context,
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


async def _require_project(body: ChatRequest, db: AsyncSession, company: Company, project: Optional[Project] = None):
    """Ensure project is selected and valid."""
    if not body.project_id:
        return None, ChatResponse(action="error", reply="Please select a project first.")
    if not project:
        result = await db.execute(
            select(Project).where(Project.id == body.project_id, Project.company_id == company.id)
        )
        project = result.scalar_one_or_none()
    if not project:
        return None, ChatResponse(action="error", reply="Project not found.", project_id=body.project_id)
    return project, None


async def _handle_start_search(
    parsed: Dict, body: ChatRequest, background_tasks: BackgroundTasks,
    db: AsyncSession, company: Company, project: Optional[Project],
) -> ChatResponse:
    """Launch segment-based search pipeline with Gemini-parsed parameters."""
    from app.api.pipeline import _running_pipelines, FullPipelineRequest, _run_full_pipeline_bg
    from datetime import datetime

    proj, err = await _require_project(body, db, company, project)
    if err:
        return err
    project_id = proj.id

    if project_id in _running_pipelines and _running_pipelines[project_id].get("running"):
        phase = _running_pipelines[project_id].get("phase", "unknown")
        return ChatResponse(
            action="info",
            reply=f"Pipeline is already running (phase: {phase}). Wait for it to complete or stop it first.",
            project_id=project_id,
            suggestions=["pipeline status", "stop"],
        )

    # Build pipeline config from parsed parameters
    engine = parsed.get("engine", "yandex")
    skip_google = engine != "google" and engine != "both"
    use_both = engine == "both"

    cfg = FullPipelineRequest(
        use_segment_search=True,
        skip_google=skip_google,
        segments=parsed.get("segments"),
        geos=parsed.get("geos"),
        max_queries=parsed.get("max_queries") or body.max_queries or 1500,
        target_goal=parsed.get("target_goal") or body.target_goal or 500,
        skip_smartlead_push=parsed.get("skip_smartlead_push", False),
    )

    _running_pipelines[project_id] = {
        "running": True,
        "phase": "starting",
        "started_at": datetime.utcnow().isoformat(),
        "config": cfg.model_dump(),
    }
    background_tasks.add_task(_run_full_pipeline_bg, project_id, company.id, cfg)

    return ChatResponse(
        action="pipeline_started",
        reply=parsed.get("reply", f"Pipeline started for **{proj.name}** using {engine}. Phases: Search → Extraction → Enrichment → Push."),
        project_id=project_id,
        suggestions=["pipeline status", "stop"],
    )


async def _handle_stop(
    parsed: Dict, body: ChatRequest, db: AsyncSession, company: Company, project: Optional[Project],
) -> ChatResponse:
    """Stop a running pipeline."""
    from app.api.pipeline import _running_pipelines

    proj, err = await _require_project(body, db, company, project)
    if err:
        return err

    if proj.id in _running_pipelines and _running_pipelines[proj.id].get("running"):
        _running_pipelines[proj.id]["stop_requested"] = True
        return ChatResponse(
            action="pipeline_stopped",
            reply=parsed.get("reply", f"Stop requested for **{proj.name}** pipeline. It will finish the current batch and stop."),
            project_id=proj.id,
        )
    return ChatResponse(
        action="info",
        reply="No pipeline is currently running for this project.",
        project_id=proj.id,
        suggestions=["run yandex search", "show stats"],
    )


async def _handle_status(
    parsed: Dict, body: ChatRequest, db: AsyncSession, company: Company, project: Optional[Project],
) -> ChatResponse:
    """Show pipeline status."""
    from app.api.pipeline import _running_pipelines
    from sqlalchemy import text as sql_text

    proj, err = await _require_project(body, db, company, project)
    if err:
        return err
    project_id = proj.id

    progress = _running_pipelines.get(project_id, {})
    if not progress or not progress.get("running"):
        stats = await db.execute(sql_text("""
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE is_target) as targets,
                COUNT(*) FILTER (WHERE apollo_enriched_at IS NOT NULL) as enriched
            FROM discovered_companies
            WHERE project_id = :pid AND company_id = :cid
        """), {"pid": project_id, "cid": company.id})
        row = stats.fetchone()
        return ChatResponse(
            action="info",
            reply=f"No pipeline running for **{proj.name}**.\n\nCurrent data: {row.total} discovered, {row.targets} targets, {row.enriched} enriched.",
            project_id=project_id,
            data={"total": row.total, "targets": row.targets, "enriched": row.enriched},
            suggestions=["run yandex search", "show stats by segment", "push to smartlead"],
        )

    phase = progress.get("phase", "unknown")
    is_running = progress.get("running", False)
    parts = [f"**Phase:** {phase}", f"**Running:** {'Yes' if is_running else 'No'}"]

    if progress.get("targets_after_search"):
        parts.append(f"**Targets found:** {progress['targets_after_search']}")
    if progress.get("segment_search"):
        ss = progress["segment_search"]
        completed = ss.get("segments_completed", [])
        active = ss.get("active_segments", [])
        if active:
            parts.append(f"**Active segments:** {', '.join(active)}")
        if completed:
            parts.append(f"**Completed:** {', '.join(completed)}")
    if progress.get("enrichment_stats"):
        es = progress["enrichment_stats"]
        parts.append(f"**Enriched:** {es.get('processed', 0)}, credits: {es.get('credits_used', 0)}")
    if progress.get("smartlead_push_stats"):
        ps = progress["smartlead_push_stats"]
        parts.append(f"**SmartLead:** {ps.get('leads_pushed', 0)} pushed")

    return ChatResponse(
        action="info",
        reply=f"Pipeline status for **{proj.name}**:\n\n" + "\n".join(parts),
        project_id=project_id,
        data=progress,
        suggestions=["stop"] if is_running else ["run yandex search", "push to smartlead"],
    )


async def _handle_push(
    parsed: Dict, body: ChatRequest, background_tasks: BackgroundTasks,
    db: AsyncSession, company: Company, project: Optional[Project],
) -> ChatResponse:
    """Push contacts to SmartLead campaigns."""
    from app.api.pipeline import _running_pipelines, _bg_phase_smartlead_push, _bg_phase_crm_promote
    from datetime import datetime

    proj, err = await _require_project(body, db, company, project)
    if err:
        return err
    project_id = proj.id

    if project_id in _running_pipelines and _running_pipelines[project_id].get("running"):
        return ChatResponse(
            action="info",
            reply="Pipeline is already running. Wait for it to complete before pushing.",
            project_id=project_id,
        )

    _running_pipelines[project_id] = {
        "running": True,
        "phase": "crm_promote",
        "started_at": datetime.utcnow().isoformat(),
        "config": {"standalone_push": True},
    }

    async def run_push():
        progress = _running_pipelines[project_id]
        try:
            # First promote to CRM, then push to SmartLead
            await _bg_phase_crm_promote(project_id, company.id, progress)
            progress["phase"] = "smartlead_push"
            await _bg_phase_smartlead_push(project_id, company.id, progress)
            progress.update({"running": False, "phase": "completed"})
        except Exception as e:
            logger.error(f"SmartLead push from chat failed: {e}", exc_info=True)
            progress.update({"running": False, "phase": "error", "error": str(e)[:500]})

    background_tasks.add_task(run_push)

    return ChatResponse(
        action="push_started",
        reply=parsed.get("reply", f"Push started for **{proj.name}**. Promoting to CRM → pushing to SmartLead campaigns."),
        project_id=project_id,
        suggestions=["pipeline status"],
    )


async def _handle_show_targets(
    parsed: Dict, body: ChatRequest, db: AsyncSession, company: Company, project: Optional[Project],
) -> ChatResponse:
    """Show top target companies."""
    from sqlalchemy import text as sql_text

    proj, err = await _require_project(body, db, company, project)
    if err:
        return err
    project_id = proj.id

    targets = await db.execute(sql_text("""
        SELECT dc.domain, dc.name, dc.confidence, dc.reasoning,
               dc.contacts_count, dc.apollo_people_count, dc.status
        FROM discovered_companies dc
        WHERE dc.project_id = :pid AND dc.company_id = :cid AND dc.is_target = true
        ORDER BY dc.confidence DESC NULLS LAST
        LIMIT 20
    """), {"pid": project_id, "cid": company.id})
    rows = targets.fetchall()

    if not rows:
        return ChatResponse(
            action="info",
            reply=f"No target companies found yet for **{proj.name}**. Run a search first.",
            project_id=project_id,
            suggestions=["run yandex search"],
        )

    lines = []
    for r in rows:
        conf = f"{round(r.confidence * 100)}%" if r.confidence else "N/A"
        contacts = f" | {r.contacts_count} contacts" if r.contacts_count else ""
        name = r.name or r.domain
        lines.append(f"- **{name}** ({r.domain}) — {conf}{contacts}")

    return ChatResponse(
        action="info",
        reply=f"Top {len(rows)} targets for **{proj.name}**:\n\n" + "\n".join(lines),
        project_id=project_id,
        data={"targets_count": len(rows)},
        suggestions=["push to smartlead", "show stats by segment"],
    )


async def _handle_stats(
    parsed: Dict, body: ChatRequest, db: AsyncSession, company: Company, project: Optional[Project],
) -> ChatResponse:
    """Show performance analytics based on scope."""
    from sqlalchemy import text as sql_text

    proj, err = await _require_project(body, db, company, project)
    if err:
        return err
    project_id = proj.id
    scope = parsed.get("stats_scope", "funnel") or "funnel"

    if scope == "segment":
        rows = await db.execute(sql_text("""
            SELECT sq.segment,
                COUNT(sq.id) as queries,
                SUM(sq.domains_found) as domains,
                SUM(sq.targets_found) as targets,
                ROUND(100.0 * SUM(sq.targets_found) / NULLIF(SUM(sq.domains_found), 0), 2) as target_pct
            FROM search_queries sq
            JOIN search_jobs sj ON sq.search_job_id = sj.id
            WHERE sj.project_id = :pid AND sq.segment IS NOT NULL
            GROUP BY sq.segment ORDER BY SUM(sq.targets_found) DESC
        """), {"pid": project_id})
        data = rows.fetchall()
        lines = ["| Segment | Queries | Domains | Targets | Target % |",
                 "|---------|---------|---------|---------|----------|"]
        for r in data:
            lines.append(f"| {r.segment or 'unknown'} | {r.queries} | {r.domains} | {r.targets} | {r.target_pct or 0}% |")
        reply = f"**Stats by segment for {proj.name}:**\n\n" + "\n".join(lines)

    elif scope == "geo":
        rows = await db.execute(sql_text("""
            SELECT sq.geo,
                COUNT(sq.id) as queries,
                SUM(sq.targets_found) as targets,
                ROUND(100.0 * SUM(sq.targets_found) / NULLIF(SUM(sq.domains_found), 0), 2) as target_pct
            FROM search_queries sq
            JOIN search_jobs sj ON sq.search_job_id = sj.id
            WHERE sj.project_id = :pid AND sq.geo IS NOT NULL
            GROUP BY sq.geo ORDER BY SUM(sq.targets_found) DESC LIMIT 20
        """), {"pid": project_id})
        data = rows.fetchall()
        lines = ["| Geo | Queries | Targets | Target % |",
                 "|-----|---------|---------|----------|"]
        for r in data:
            lines.append(f"| {r.geo} | {r.queries} | {r.targets} | {r.target_pct or 0}% |")
        reply = f"**Stats by geo for {proj.name}:**\n\n" + "\n".join(lines)

    elif scope == "engine":
        rows = await db.execute(sql_text("""
            SELECT sj.search_engine,
                COUNT(sq.id) as queries,
                SUM(sq.targets_found) as targets,
                CASE
                    WHEN sj.search_engine = 'YANDEX_API' THEN ROUND(COUNT(sq.id) * 0.25 / 1000, 2)
                    WHEN sj.search_engine = 'GOOGLE_SERP' THEN ROUND(COUNT(sq.id) * 3.50 / 1000, 2)
                    ELSE 0
                END as cost_usd,
                CASE WHEN SUM(sq.targets_found) > 0 THEN
                    ROUND(
                        CASE
                            WHEN sj.search_engine = 'YANDEX_API' THEN COUNT(sq.id) * 0.25 / 1000
                            WHEN sj.search_engine = 'GOOGLE_SERP' THEN COUNT(sq.id) * 3.50 / 1000
                            ELSE 0
                        END / SUM(sq.targets_found), 2
                    )
                ELSE 0 END as cost_per_target
            FROM search_queries sq
            JOIN search_jobs sj ON sq.search_job_id = sj.id
            WHERE sj.project_id = :pid
            GROUP BY sj.search_engine
        """), {"pid": project_id})
        data = rows.fetchall()
        lines = ["| Engine | Queries | Targets | Cost ($) | $/target |",
                 "|--------|---------|---------|----------|----------|"]
        for r in data:
            lines.append(f"| {r.search_engine} | {r.queries} | {r.targets} | ${r.cost_usd} | ${r.cost_per_target} |")
        reply = f"**Engine comparison for {proj.name}:**\n\n" + "\n".join(lines)

    elif scope == "cost":
        rows = await db.execute(sql_text("""
            SELECT sj.search_engine, COUNT(sq.id) as queries,
                CASE
                    WHEN sj.search_engine = 'YANDEX_API' THEN ROUND(COUNT(sq.id) * 0.25 / 1000, 2)
                    WHEN sj.search_engine = 'GOOGLE_SERP' THEN ROUND(COUNT(sq.id) * 3.50 / 1000, 2)
                    ELSE 0
                END as cost_usd
            FROM search_queries sq
            JOIN search_jobs sj ON sq.search_job_id = sj.id
            WHERE sj.project_id = :pid
            GROUP BY sj.search_engine
        """), {"pid": project_id})
        data = rows.fetchall()
        total_cost = sum(float(r.cost_usd) for r in data)
        lines = [f"**Total search cost: ${total_cost:.2f}**\n"]
        for r in data:
            lines.append(f"- {r.search_engine}: {r.queries} queries = ${r.cost_usd}")
        reply = f"**Cost breakdown for {proj.name}:**\n\n" + "\n".join(lines)

    elif scope == "top_queries":
        rows = await db.execute(sql_text("""
            SELECT sq.query_text, sq.segment, sq.geo,
                sq.domains_found, sq.targets_found,
                ROUND(100.0 * sq.targets_found / NULLIF(sq.domains_found, 0), 1) as target_pct,
                sj.search_engine
            FROM search_queries sq
            JOIN search_jobs sj ON sq.search_job_id = sj.id
            WHERE sj.project_id = :pid AND sq.targets_found > 0
            ORDER BY sq.targets_found DESC LIMIT 15
        """), {"pid": project_id})
        data = rows.fetchall()
        lines = []
        for r in data:
            lines.append(f"- **{r.query_text}** ({r.segment}/{r.geo}) — {r.targets_found} targets ({r.target_pct}%) [{r.search_engine}]")
        reply = f"**Top queries for {proj.name}:**\n\n" + "\n".join(lines)

    else:  # funnel
        funnel = await db.execute(sql_text("""
            SELECT
                (SELECT COUNT(*) FROM discovered_companies WHERE project_id = :pid) as discovered,
                (SELECT COUNT(*) FROM discovered_companies WHERE project_id = :pid AND is_target = true) as targets,
                (SELECT COUNT(DISTINCT ec.discovered_company_id) FROM extracted_contacts ec
                 JOIN discovered_companies dc ON ec.discovered_company_id = dc.id
                 WHERE dc.project_id = :pid AND dc.is_target = true AND ec.email IS NOT NULL) as targets_with_email,
                (SELECT COUNT(*) FROM extracted_contacts ec
                 JOIN discovered_companies dc ON ec.discovered_company_id = dc.id
                 WHERE dc.project_id = :pid AND dc.is_target = true AND ec.email IS NOT NULL) as total_email_contacts,
                (SELECT COUNT(*) FROM contacts WHERE project_id = :pid AND deleted_at IS NULL) as crm_contacts,
                (SELECT COUNT(*) FROM contacts WHERE project_id = :pid AND deleted_at IS NULL
                 AND campaigns IS NOT NULL AND campaigns::text NOT IN ('null', '[]', '{}', '')) as in_campaigns
        """), {"pid": project_id})
        f = funnel.fetchone()
        reply = (
            f"**Funnel for {proj.name}:**\n\n"
            f"- Discovered companies: **{f.discovered}**\n"
            f"- Target companies: **{f.targets}** ({round(100 * f.targets / max(f.discovered, 1), 1)}%)\n"
            f"- Targets with email: **{f.targets_with_email}** ({round(100 * f.targets_with_email / max(f.targets, 1), 1)}%)\n"
            f"- Total email contacts: **{f.total_email_contacts}**\n"
            f"- CRM contacts: **{f.crm_contacts}**\n"
            f"- In SmartLead campaigns: **{f.in_campaigns}**"
        )

    return ChatResponse(
        action="stats",
        reply=reply,
        project_id=project_id,
        suggestions=_build_suggestions(None),
    )


# ---- Knowledge handlers ----

async def _handle_show_knowledge(
    parsed: Dict, body: ChatRequest, db: AsyncSession, company: Company, project: Optional[Project],
) -> ChatResponse:
    """Show project knowledge base entries."""
    from app.services.project_knowledge_service import project_knowledge_service

    proj, err = await _require_project(body, db, company, project)
    if err:
        return err

    category = parsed.get("kb_category")
    if category:
        entries = await project_knowledge_service.get_by_category(db, proj.id, category)
        if not entries:
            return ChatResponse(
                action="show_knowledge",
                reply=f"No knowledge entries in **{category}** category yet.",
                project_id=proj.id,
                suggestions=["show all knowledge", f"add {category} note"],
            )
        lines = [f"**{category.upper()} knowledge for {proj.name}:**\n"]
        for e in entries:
            title = e.get("title") or e["key"]
            val = e["value"]
            if isinstance(val, dict) and "text" in val:
                lines.append(f"- **{title}**: {val['text'][:200]}")
            else:
                import json as _json
                lines.append(f"- **{title}**: {_json.dumps(val, ensure_ascii=False)[:200]}")
        return ChatResponse(
            action="show_knowledge",
            reply="\n".join(lines),
            project_id=proj.id,
            data={"category": category, "entries": entries},
            suggestions=["show all knowledge", "update knowledge"],
        )
    else:
        summary = await project_knowledge_service.get_summary(db, proj.id)
        grouped = await project_knowledge_service.get_all(db, proj.id)
        if not grouped:
            # Auto-sync from legacy on first access
            count = await project_knowledge_service.sync_from_legacy(db, proj.id)
            if count > 0:
                summary = await project_knowledge_service.get_summary(db, proj.id)
                grouped = await project_knowledge_service.get_all(db, proj.id)
            else:
                return ChatResponse(
                    action="show_knowledge",
                    reply=f"No knowledge entries for **{proj.name}** yet. Try: 'note: our ICP is luxury real estate agencies in Dubai'",
                    project_id=proj.id,
                    suggestions=["sync knowledge", "add note"],
                )
        return ChatResponse(
            action="show_knowledge",
            reply=f"**Knowledge base for {proj.name}:**\n\n{summary}",
            project_id=proj.id,
            data={"knowledge": grouped},
            suggestions=["show icp", "show search knowledge", "add note"],
        )


async def _handle_update_knowledge(
    parsed: Dict, body: ChatRequest, db: AsyncSession, company: Company, project: Optional[Project],
) -> ChatResponse:
    """Add or update a knowledge base entry via natural language."""
    from app.services.project_knowledge_service import project_knowledge_service

    proj, err = await _require_project(body, db, company, project)
    if err:
        return err

    category = parsed.get("kb_category") or "notes"
    key = parsed.get("kb_key")
    value = parsed.get("kb_value")
    title = parsed.get("kb_title")

    if not value:
        return ChatResponse(
            action="info",
            reply="Please specify what to remember. Example: 'note: ICP targets luxury RE in Dubai'",
            project_id=proj.id,
        )

    # Auto-generate key from title or content if not provided
    if not key:
        import re
        base = title or str(value)[:50]
        key = re.sub(r'[^a-z0-9]+', '_', base.lower()).strip('_')[:80]

    # If value is a plain string, wrap it
    if isinstance(value, str):
        value = {"text": value}

    entry = await project_knowledge_service.upsert(
        db, proj.id, category, key,
        value=value, title=title, source="chat",
    )

    return ChatResponse(
        action="knowledge_updated",
        reply=parsed.get("reply", f"Saved to **{category}/{key}**: {title or key}"),
        project_id=proj.id,
        data={"entry": entry},
        suggestions=["show knowledge", "show " + category],
    )


async def _handle_ask(
    parsed: Dict, body: ChatRequest, db: AsyncSession, company: Company, project: Optional[Project],
) -> ChatResponse:
    """Answer a question using project knowledge context."""
    from app.services.project_knowledge_service import project_knowledge_service

    proj, err = await _require_project(body, db, company, project)
    if err:
        return err

    # Build context from knowledge
    summary = await project_knowledge_service.get_summary(db, proj.id)

    # Use AI to answer the question with knowledge context
    try:
        from app.services.gemini_client import is_gemini_available, gemini_generate, extract_json_from_gemini
        import json

        system_prompt = f"""You are a project assistant for "{proj.name}". Answer the user's question based on the project knowledge below.

PROJECT KNOWLEDGE:
{summary[:4000]}

TARGET DESCRIPTION: {proj.target_segments or 'Not defined'}

RULES:
- Answer concisely, using specific data from the knowledge base when available.
- If you don't have enough info, say so and suggest what knowledge could be added.
- Reply in the same language the user used.
- Return JSON: {{"reply": "your answer", "suggestions": ["follow-up suggestion 1", "follow-up suggestion 2"]}}"""

        if is_gemini_available():
            gen_result = await gemini_generate(
                system_prompt=system_prompt,
                user_prompt=body.message,
                temperature=0.3,
                max_tokens=1500,
            )
            raw = extract_json_from_gemini(gen_result["content"])
            result = json.loads(raw)
        else:
            import openai
            from app.core.config import settings
            client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": body.message},
                ],
                temperature=0.3,
                response_format={"type": "json_object"},
                max_tokens=1500,
            )
            result = json.loads(response.choices[0].message.content)

        return ChatResponse(
            action="answer",
            reply=result.get("reply", parsed.get("reply", "I couldn't find an answer in the knowledge base.")),
            project_id=proj.id,
            suggestions=result.get("suggestions", ["show knowledge", "add note"]),
        )
    except Exception as e:
        logger.error(f"Failed to answer question: {e}", exc_info=True)
        return ChatResponse(
            action="answer",
            reply=parsed.get("reply", "I couldn't process your question. Please try rephrasing."),
            project_id=proj.id,
            suggestions=["show knowledge"],
        )


# ---- Search Config handlers ----

async def _handle_show_config(
    parsed: Dict, body: ChatRequest, db: AsyncSession, company: Company, project: Optional[Project],
) -> ChatResponse:
    """Show current search configuration for the project."""
    from app.services.search_config_service import search_config_service

    proj, err = await _require_project(body, db, company, project)
    if err:
        return err

    config = await search_config_service.get_or_create_config(db, proj.id)
    summary = search_config_service.format_config_summary(config)

    return ChatResponse(
        action="show_config",
        reply=summary,
        project_id=proj.id,
        data={"search_config": config},
        suggestions=["edit config", "bootstrap config", "run search"],
    )


async def _handle_edit_config(
    parsed: Dict, body: ChatRequest, db: AsyncSession, company: Company, project: Optional[Project],
) -> ChatResponse:
    """Edit search configuration via AI interpretation."""
    from app.services.search_config_service import search_config_service

    proj, err = await _require_project(body, db, company, project)
    if err:
        return err

    # Get current config (or bootstrap if none)
    current_config = await search_config_service.get_or_create_config(db, proj.id)

    # Use the edit instruction from parsed action, fall back to original message
    edit_instruction = parsed.get("edit_instruction") or body.message

    result = await search_config_service.edit_config_via_ai(
        session=db,
        project_id=proj.id,
        user_message=edit_instruction,
        current_config=current_config,
    )

    return ChatResponse(
        action="config_updated",
        reply=f"Config updated: {result['summary']}",
        project_id=proj.id,
        data={"search_config": result["config"]},
        suggestions=["show config", "run search"],
    )


# ---- Search Config REST endpoints ----

@router.get("/config/{project_id}")
async def get_search_config(
    project_id: int,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Get full search config for a project."""
    from app.services.search_config_service import search_config_service

    proj = await db.execute(
        select(Project).where(Project.id == project_id, Project.company_id == company.id)
    )
    if not proj.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    config = await search_config_service.get_or_create_config(db, project_id)
    return {"project_id": project_id, "search_config": config}


@router.put("/config/{project_id}")
async def update_search_config(
    project_id: int,
    body: Dict[str, Any],
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Replace entire search config for a project."""
    from app.services.search_config_service import search_config_service

    proj = await db.execute(
        select(Project).where(Project.id == project_id, Project.company_id == company.id)
    )
    if not proj.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    config = await search_config_service.update_config(db, project_id, body)
    return {"project_id": project_id, "search_config": config}


@router.post("/config/{project_id}/bootstrap")
async def bootstrap_search_config(
    project_id: int,
    db: AsyncSession = Depends(get_session),
    company: Company = Depends(get_required_company),
):
    """Force AI re-bootstrap of search config from project's target_segments."""
    from app.services.search_config_service import search_config_service

    proj_result = await db.execute(
        select(Project).where(Project.id == project_id, Project.company_id == company.id)
    )
    project = proj_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.target_segments:
        raise HTTPException(status_code=400, detail="Project has no target_segments defined")

    config = await search_config_service.bootstrap_config(project.target_segments, project.name)
    await search_config_service.update_config(db, project_id, config)

    return {
        "project_id": project_id,
        "search_config": config,
        "segments_count": len(config.get("segments", {})),
        "doc_keywords_groups": len(config.get("doc_keywords", [])),
    }
