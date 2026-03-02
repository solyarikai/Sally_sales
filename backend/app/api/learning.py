"""
Learning API — learning cycles, operator corrections, and feedback.

Endpoints:
- GET    /projects/{id}/learning/overview         -> All knowledge data for page load
- GET    /projects/{id}/learning/logs             -> Paginated learning logs
- GET    /projects/{id}/learning/logs/{log_id}    -> Single log with before/after diff
- GET    /projects/{id}/learning/templates        -> Templates + usage stats
- POST   /projects/{id}/learning/analyze          -> Trigger learning cycle
- GET    /projects/{id}/learning/analyze/{log_id}/status -> Poll job progress
- POST   /projects/{id}/learning/feedback         -> Cmd+K feedback
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from typing import Optional
from pydantic import BaseModel, Field
import logging

from app.db import get_session
from app.models.contact import Project
from app.models.reply import ReplyPromptTemplateModel
from app.models.learning import LearningLog, OperatorCorrection
from app.models.project_knowledge import ProjectKnowledge
from app.services.learning_service import learning_service

router = APIRouter(prefix="/projects", tags=["learning"])
logger = logging.getLogger(__name__)


# --- Request/Response schemas ---

class AnalyzeRequest(BaseModel):
    max_conversations: int = Field(100, ge=10, le=500)
    force_all: bool = False


class FeedbackRequest(BaseModel):
    feedback_text: str = Field(..., min_length=5, max_length=5000)


# --- Helpers ---

async def _get_project(db: AsyncSession, project_id: int) -> Project:
    result = await db.execute(
        select(Project).where(and_(Project.id == project_id, Project.deleted_at.is_(None)))
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


# --- Endpoints ---

@router.get("/{project_id}/learning/overview")
async def get_learning_overview(
    project_id: int,
    db: AsyncSession = Depends(get_session),
):
    """All knowledge data for the Knowledge page initial load."""
    project = await _get_project(db, project_id)

    # ICP knowledge
    icp_result = await db.execute(
        select(ProjectKnowledge)
        .where(ProjectKnowledge.project_id == project_id, ProjectKnowledge.category == "icp")
        .order_by(ProjectKnowledge.key)
    )
    icp_entries = [
        {
            "id": r.id, "key": r.key, "title": r.title,
            "value": r.value, "source": r.source,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in icp_result.scalars().all()
    ]

    # Current template
    template_data = None
    if project.reply_prompt_template_id:
        tmpl_result = await db.execute(
            select(ReplyPromptTemplateModel).where(
                ReplyPromptTemplateModel.id == project.reply_prompt_template_id
            )
        )
        tmpl = tmpl_result.scalar_one_or_none()
        if tmpl:
            template_data = {
                "id": tmpl.id, "name": tmpl.name,
                "prompt_text": tmpl.prompt_text,
                "version": tmpl.version,
                "usage_count": tmpl.usage_count,
                "last_used_at": tmpl.last_used_at.isoformat() if tmpl.last_used_at else None,
            }

    # Recent learning logs (last 5)
    logs_result = await db.execute(
        select(LearningLog)
        .where(LearningLog.project_id == project_id)
        .order_by(LearningLog.created_at.desc())
        .limit(5)
    )
    recent_logs = [
        {
            "id": l.id, "trigger": l.trigger, "status": l.status,
            "change_type": l.change_type, "change_summary": l.change_summary,
            "conversations_analyzed": l.conversations_analyzed,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        }
        for l in logs_result.scalars().all()
    ]

    # Corrections count
    corrections_count_result = await db.execute(
        select(func.count(OperatorCorrection.id)).where(
            OperatorCorrection.project_id == project_id
        )
    )
    corrections_total = corrections_count_result.scalar() or 0

    edited_count_result = await db.execute(
        select(func.count(OperatorCorrection.id)).where(
            OperatorCorrection.project_id == project_id,
            OperatorCorrection.was_edited == True,
        )
    )
    corrections_edited = edited_count_result.scalar() or 0

    return {
        "project_id": project_id,
        "project_name": project.name,
        "icp": icp_entries,
        "template": template_data,
        "recent_logs": recent_logs,
        "corrections": {
            "total": corrections_total,
            "edited": corrections_edited,
        },
    }


@router.get("/{project_id}/learning/logs")
async def get_learning_logs(
    project_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
):
    """Paginated learning logs."""
    await _get_project(db, project_id)

    total_result = await db.execute(
        select(func.count(LearningLog.id)).where(LearningLog.project_id == project_id)
    )
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    logs_result = await db.execute(
        select(LearningLog)
        .where(LearningLog.project_id == project_id)
        .order_by(LearningLog.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    logs = [
        {
            "id": l.id, "trigger": l.trigger, "status": l.status,
            "change_type": l.change_type, "change_summary": l.change_summary,
            "conversations_analyzed": l.conversations_analyzed,
            "qualified_count": l.qualified_count,
            "conversations_email": l.conversations_email,
            "conversations_linkedin": l.conversations_linkedin,
            "tokens_used": l.tokens_used, "cost_usd": l.cost_usd,
            "feedback_text": l.feedback_text,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        }
        for l in logs_result.scalars().all()
    ]

    return {"items": logs, "total": total, "page": page, "page_size": page_size}


@router.get("/{project_id}/learning/logs/{log_id}")
async def get_learning_log_detail(
    project_id: int,
    log_id: int,
    db: AsyncSession = Depends(get_session),
):
    """Single learning log with before/after snapshots."""
    result = await db.execute(
        select(LearningLog).where(
            LearningLog.id == log_id,
            LearningLog.project_id == project_id,
        )
    )
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="Learning log not found")

    return {
        "id": log.id, "trigger": log.trigger, "status": log.status,
        "change_type": log.change_type, "change_summary": log.change_summary,
        "before_snapshot": log.before_snapshot,
        "after_snapshot": log.after_snapshot,
        "ai_reasoning": log.ai_reasoning,
        "feedback_text": log.feedback_text,
        "conversations_analyzed": log.conversations_analyzed,
        "qualified_count": log.qualified_count,
        "conversations_email": log.conversations_email,
        "conversations_linkedin": log.conversations_linkedin,
        "tokens_used": log.tokens_used, "cost_usd": log.cost_usd,
        "error_message": log.error_message,
        "template_id": log.template_id,
        "created_at": log.created_at.isoformat() if log.created_at else None,
    }


@router.get("/{project_id}/learning/templates")
async def get_learning_templates(
    project_id: int,
    db: AsyncSession = Depends(get_session),
):
    """Templates with usage stats for this project."""
    project = await _get_project(db, project_id)

    templates_result = await db.execute(
        select(ReplyPromptTemplateModel).order_by(ReplyPromptTemplateModel.created_at.desc())
    )
    templates = templates_result.scalars().all()

    # Category breakdown from corrections
    category_result = await db.execute(
        select(
            OperatorCorrection.reply_category,
            func.count(OperatorCorrection.id),
        )
        .where(OperatorCorrection.project_id == project_id)
        .group_by(OperatorCorrection.reply_category)
    )
    category_stats = {row[0]: row[1] for row in category_result.all() if row[0]}

    return {
        "active_template_id": project.reply_prompt_template_id,
        "templates": [
            {
                "id": t.id, "name": t.name, "prompt_type": t.prompt_type,
                "prompt_text": t.prompt_text,
                "is_default": t.is_default,
                "version": t.version,
                "usage_count": t.usage_count,
                "last_used_at": t.last_used_at.isoformat() if t.last_used_at else None,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in templates
        ],
        "category_stats": category_stats,
    }


@router.post("/{project_id}/learning/analyze")
async def trigger_learning(
    project_id: int,
    body: AnalyzeRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
):
    """Trigger a learning cycle. Returns log_id immediately; poll /status for progress."""
    project = await _get_project(db, project_id)

    # Create log entry
    log = LearningLog(
        project_id=project_id,
        trigger="manual",
        status="processing",
    )
    db.add(log)
    await db.flush()
    log_id = log.id

    # Run in background
    async def _run():
        from app.db.database import async_session_maker
        async with async_session_maker() as session:
            try:
                await learning_service.run_learning_cycle(
                    session, project_id,
                    max_conversations=body.max_conversations,
                    force_all=body.force_all,
                    trigger="manual",
                    log_id=log_id,
                )
                await session.commit()
            except Exception as e:
                logger.error(f"Background learning failed: {e}", exc_info=True)
                try:
                    result = await session.execute(select(LearningLog).where(LearningLog.id == log_id))
                    bg_log = result.scalar_one_or_none()
                    if bg_log:
                        bg_log.status = "failed"
                        bg_log.error_message = str(e)[:2000]
                        await session.commit()
                except Exception:
                    pass

    background_tasks.add_task(_run)

    return {
        "learning_log_id": log_id,
        "status": "processing",
        "message": f"Learning cycle started for {project.name}",
    }


@router.get("/{project_id}/learning/analyze/{log_id}/status")
async def get_learning_status(
    project_id: int,
    log_id: int,
    db: AsyncSession = Depends(get_session),
):
    """Poll learning job progress."""
    result = await db.execute(
        select(LearningLog).where(
            LearningLog.id == log_id,
            LearningLog.project_id == project_id,
        )
    )
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="Learning log not found")

    resp = {
        "id": log.id,
        "status": log.status,
        "change_summary": log.change_summary,
        "conversations_analyzed": log.conversations_analyzed,
        "error_message": log.error_message,
    }

    if log.status == "insufficient_data":
        resp["can_force"] = True
        resp["qualified_count"] = log.qualified_count

    return resp


@router.post("/{project_id}/learning/feedback")
async def submit_feedback(
    project_id: int,
    body: FeedbackRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
):
    """Submit operator feedback via Cmd+K."""
    project = await _get_project(db, project_id)

    # Create log entry immediately and commit so background task can find it
    log = LearningLog(
        project_id=project_id,
        trigger="feedback",
        feedback_text=body.feedback_text,
        status="processing",
    )
    db.add(log)
    await db.commit()
    log_id = log.id

    async def _run():
        from app.db.database import async_session_maker
        async with async_session_maker() as session:
            try:
                await learning_service.process_feedback(
                    session, project_id, body.feedback_text, log_id=log_id
                )
                await session.commit()
            except Exception as e:
                logger.error(f"Background feedback failed: {e}", exc_info=True)
                try:
                    result = await session.execute(select(LearningLog).where(LearningLog.id == log_id))
                    bg_log = result.scalar_one_or_none()
                    if bg_log:
                        bg_log.status = "failed"
                        bg_log.error_message = str(e)[:2000]
                        await session.commit()
                except Exception:
                    pass

    background_tasks.add_task(_run)

    return {
        "learning_log_id": log_id,
        "status": "processing",
        "message": "Feedback submitted, processing...",
    }
