"""
SSE Streaming Chat API — real-time streaming responses for the chat interface.

GET /search/chat/stream — EventSource-compatible SSE endpoint
GET /search/chat/live/{project_id} — Live updates for background task notifications
"""
import asyncio
import json
import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db import get_session, async_session_maker
from app.models.user import Company
from app.models.contact import Project
from app.models.chat import ProjectChatMessage
from app.services.chat_search_service import chat_search_service
from app.core.config import settings

router = APIRouter(prefix="/search", tags=["search"])
logger = logging.getLogger(__name__)


def _sse_event(event_type: str, data: dict) -> str:
    """Format a Server-Sent Event."""
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.get("/chat/stream")
async def stream_chat(
    message: str = Query(..., min_length=1, max_length=5000),
    project_id: int = Query(...),
    company_id: int = Query(...),
):
    """SSE streaming chat endpoint.

    EventSource can't POST or send custom headers, so we use query params.
    Yields typed events: intent, token, chunk, action, done.
    """
    async def event_generator():
        start_time = time.time()

        try:
            # Get a fresh session
            async with async_session_maker() as db:
                # Verify project
                result = await db.execute(
                    select(Project).where(
                        Project.id == project_id,
                        Project.company_id == company_id,
                    )
                )
                project = result.scalar_one_or_none()
                if not project:
                    yield _sse_event("error", {"message": "Project not found"})
                    return

                company_result = await db.execute(
                    select(Company).where(Company.id == company_id)
                )
                company = company_result.scalar_one_or_none()
                if not company:
                    yield _sse_event("error", {"message": "Company not found"})
                    return

                # Save user message
                from app.api.search_chat import _save_chat_message, _load_chat_context, _build_project_context, _build_suggestions
                await _save_chat_message(db, project_id, "user", message, f"user-{project_id}-{message[:40]}")

                # Load context
                db_context = await _load_chat_context(db, project_id)
                project_context = await _build_project_context(db, project, company)

                # Parse intent
                parsed = await chat_search_service.parse_chat_action(
                    message=message,
                    project_context=project_context,
                    context=db_context,
                )
                action = parsed.get("action", "info")

                # Yield intent event
                yield _sse_event("intent", {
                    "action": action,
                    "preview": parsed.get("reply", "")[:100],
                })

                # Route by action type
                if action == "ask":
                    # Stream the AI response token by token
                    full_text = ""
                    try:
                        from app.services.gemini_client import is_gemini_available, gemini_generate_stream
                        from app.services.project_knowledge_service import project_knowledge_service

                        summary = await project_knowledge_service.get_summary(db, project_id)
                        system_prompt = f"""You are a project assistant for "{project.name}". Answer the user's question based on the project knowledge below.

PROJECT KNOWLEDGE:
{summary[:4000]}

TARGET DESCRIPTION: {project.target_segments or 'Not defined'}

RULES:
- Answer concisely, using specific data from the knowledge base when available.
- If you don't have enough info, say so and suggest what knowledge could be added.
- Reply in the same language the user used.
- Use markdown for formatting (tables, bold, lists)."""

                        if is_gemini_available():
                            async for chunk in gemini_generate_stream(
                                system_prompt=system_prompt,
                                user_prompt=message,
                                temperature=0.3,
                                max_tokens=1500,
                            ):
                                full_text += chunk
                                yield _sse_event("token", {"text": chunk})
                        else:
                            # OpenAI streaming fallback
                            import openai
                            client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
                            stream = await client.chat.completions.create(
                                model="gpt-4o-mini",
                                messages=[
                                    {"role": "system", "content": system_prompt},
                                    {"role": "user", "content": message},
                                ],
                                temperature=0.3,
                                max_tokens=1500,
                                stream=True,
                            )
                            async for chunk in stream:
                                delta = chunk.choices[0].delta
                                if delta.content:
                                    full_text += delta.content
                                    yield _sse_event("token", {"text": delta.content})

                    except Exception as e:
                        logger.error(f"Streaming ask failed: {e}", exc_info=True)
                        full_text = parsed.get("reply", "I couldn't process your question.")
                        yield _sse_event("token", {"text": full_text})

                    suggestions = _build_suggestions(project_context)
                    duration_ms = int((time.time() - start_time) * 1000)

                    # Save to DB
                    await _save_chat_message(
                        db, project_id, "assistant", full_text,
                        action_type="answer",
                        suggestions=suggestions,
                        duration_ms=duration_ms,
                    )
                    await db.commit()

                    yield _sse_event("done", {
                        "action": "answer",
                        "reply": full_text,
                        "suggestions": suggestions,
                        "duration_ms": duration_ms,
                    })

                else:
                    # Non-streaming actions: execute handler and return result
                    from app.api.search_chat import (
                        ChatRequest, ChatResponse,
                        _handle_start_search, _handle_stop, _handle_status,
                        _handle_push, _handle_show_targets, _handle_stats,
                        _handle_lookup_domain, _handle_show_config, _handle_edit_config,
                        _handle_show_knowledge, _handle_update_knowledge,
                        _handle_verify_emails, _handle_verification_stats,
                        _handle_show_segments, _handle_toggle_verification,
                        _handle_show_contacts, _handle_new_search, _handle_ask,
                        _handle_clay_export,
                        _handle_clay_people,
                        _handle_clay_gather,
                    )
                    from fastapi import BackgroundTasks

                    body = ChatRequest(message=message, project_id=project_id)
                    bg_tasks = BackgroundTasks()

                    handlers = {
                        "start_search": lambda: _handle_start_search(parsed, body, bg_tasks, db, company, project),
                        "stop": lambda: _handle_stop(parsed, body, db, company, project),
                        "status": lambda: _handle_status(parsed, body, db, company, project),
                        "push": lambda: _handle_push(parsed, body, bg_tasks, db, company, project),
                        "show_targets": lambda: _handle_show_targets(parsed, body, db, company, project),
                        "show_stats": lambda: _handle_stats(parsed, body, db, company, project),
                        "lookup_domain": lambda: _handle_lookup_domain(parsed, body, db, company, project),
                        "show_config": lambda: _handle_show_config(parsed, body, db, company, project),
                        "edit_config": lambda: _handle_edit_config(parsed, body, db, company, project),
                        "show_knowledge": lambda: _handle_show_knowledge(parsed, body, db, company, project),
                        "update_knowledge": lambda: _handle_update_knowledge(parsed, body, db, company, project),
                        "verify_emails": lambda: _handle_verify_emails(parsed, body, bg_tasks, db, company, project),
                        "show_verification_stats": lambda: _handle_verification_stats(parsed, body, db, company, project),
                        "show_segments": lambda: _handle_show_segments(parsed, body, db, company, project),
                        "toggle_verification": lambda: _handle_toggle_verification(parsed, body, db, company, project),
                        "show_contacts": lambda: _handle_show_contacts(parsed, body, db, company, project),
                        "search": lambda: _handle_new_search(body, bg_tasks, db, company),
                        "clay_export": lambda: _handle_clay_export(parsed, body, bg_tasks, db, company, project),
                        "clay_people": lambda: _handle_clay_people(parsed, body, bg_tasks, db, company, project),
                        "clay_gather": lambda: _handle_clay_gather(parsed, body, bg_tasks, db, company, project),
                    }

                    handler = handlers.get(action)
                    if handler:
                        response = await handler()
                    else:
                        response = ChatResponse(
                            action="info",
                            reply=parsed.get("reply", "I'm not sure what you need."),
                            project_id=project_id,
                            suggestions=_build_suggestions(project_context),
                        )

                    # Run background tasks
                    for task in bg_tasks.tasks:
                        asyncio.create_task(task.func(*task.args, **task.kwargs))

                    duration_ms = int((time.time() - start_time) * 1000)

                    # Stream the reply text in chunks for visual effect
                    reply_text = response.reply or ""
                    # Send full reply as a single chunk for data actions
                    yield _sse_event("chunk", {
                        "text": reply_text,
                        "action": response.action,
                    })

                    # Save to DB
                    await _save_chat_message(
                        db, project_id, "assistant", reply_text,
                        action_type=response.action,
                        action_data=response.data,
                        suggestions=response.suggestions if response.suggestions else None,
                        duration_ms=duration_ms,
                    )
                    await db.commit()

                    yield _sse_event("done", {
                        "action": response.action,
                        "reply": reply_text,
                        "project_id": response.project_id,
                        "job_id": response.job_id,
                        "suggestions": response.suggestions or [],
                        "data": response.data,
                        "duration_ms": duration_ms,
                    })

        except Exception as e:
            logger.error(f"Chat stream error: {e}", exc_info=True)
            yield _sse_event("error", {"message": str(e)[:500]})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/chat/live/{project_id}")
async def live_chat_updates(
    project_id: int,
    after_id: int = Query(0, description="Only return messages with id > after_id"),
):
    """SSE endpoint for live chat updates (system messages from background tasks).

    Frontend subscribes on mount, receives new messages as they appear.
    """
    async def event_generator():
        last_id = after_id

        while True:
            try:
                async with async_session_maker() as session:
                    result = await session.execute(
                        select(ProjectChatMessage)
                        .where(
                            ProjectChatMessage.project_id == project_id,
                            ProjectChatMessage.id > last_id,
                            ProjectChatMessage.action_type != "cleared",
                        )
                        .order_by(ProjectChatMessage.id.asc())
                        .limit(20)
                    )
                    new_msgs = result.scalars().all()

                    for msg in new_msgs:
                        last_id = msg.id
                        yield _sse_event("message", {
                            "id": msg.id,
                            "role": msg.role,
                            "content": msg.content,
                            "action_type": msg.action_type,
                            "action_data": msg.action_data,
                            "suggestions": msg.suggestions,
                            "timestamp": msg.created_at.isoformat() if msg.created_at else None,
                        })

            except Exception as e:
                logger.error(f"Live chat poll error: {e}")

            await asyncio.sleep(3)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
