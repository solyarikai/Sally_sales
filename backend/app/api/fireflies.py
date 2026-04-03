"""API endpoints for Fireflies.ai call transcript integration.

Per-project integration: each project stores its own Fireflies API key
in project.fireflies_config, similar to Calendly integration.
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel
from app.db import get_session, async_session_maker
from app.models import Contact, ContactActivity
from app.models.contact import Project
from app.models.call_transcript import CallTranscript
from app.services.fireflies_service import fireflies_service
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/fireflies", tags=["fireflies"])


# ============ Schemas ============

class TranscriptListItem(BaseModel):
    id: int
    fireflies_id: str
    title: Optional[str] = None
    date: Optional[datetime] = None
    duration: Optional[int] = None
    organizer_email: Optional[str] = None
    participants: Optional[list] = None
    summary: Optional[str] = None
    contact_id: Optional[int] = None
    project_id: Optional[int] = None
    source: Optional[str] = None

    class Config:
        from_attributes = True


class TranscriptDetail(TranscriptListItem):
    transcript_text: Optional[str] = None
    sentences: Optional[list] = None
    speakers: Optional[list] = None
    action_items: Optional[list] = None
    keywords: Optional[list] = None
    transcript_url: Optional[str] = None
    audio_url: Optional[str] = None

    class Config:
        from_attributes = True


class SyncResponse(BaseModel):
    synced: int
    matched: int
    errors: List[str] = []


class FirefliesConnectRequest(BaseModel):
    token: str


# ============ Per-Project Endpoints (Calendly-style) ============

@router.get("/project-status")
async def fireflies_project_status(
    project_id: int = Query(...),
    db: AsyncSession = Depends(get_session),
):
    """Return Fireflies connection status for a project."""
    result = await db.execute(
        select(Project).where(
            and_(Project.id == project_id, Project.deleted_at.is_(None))
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    config = project.fireflies_config or {}
    api_key = config.get("api_key")
    connected = bool(api_key)

    user_name = config.get("user_name")
    user_email = config.get("user_email")

    # If connected but no cached user info, try fetching
    if connected and not user_name:
        try:
            user_info = await fireflies_service.get_user(api_key=api_key)
            if user_info:
                user_name = user_info.get("name")
                user_email = user_info.get("email")
        except Exception:
            pass

    return {
        "connected": connected,
        "user_name": user_name,
        "user_email": user_email,
        "webhook_url": "/api/fireflies/webhook",
    }


@router.post("/connect")
async def fireflies_connect(
    project_id: int = Query(...),
    body: FirefliesConnectRequest = Body(...),
    db: AsyncSession = Depends(get_session),
):
    """Connect Fireflies to a project by saving API key.

    Tests the key first, then saves to project.fireflies_config.
    """
    result = await db.execute(
        select(Project).where(
            and_(Project.id == project_id, Project.deleted_at.is_(None))
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    token = body.token.strip()
    if not token:
        raise HTTPException(status_code=400, detail="Token is required")

    # Test the key
    is_valid = await fireflies_service.test_connection(api_key=token)
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail="Invalid API key or failed to connect to Fireflies",
        )

    user_info = await fireflies_service.get_user(api_key=token)
    user_name = (user_info or {}).get("name", "Unknown")
    user_email = (user_info or {}).get("email", "")

    # Save to project.fireflies_config
    project.fireflies_config = {
        "api_key": token,
        "user_name": user_name,
        "user_email": user_email,
    }
    await db.commit()

    return {
        "ok": True,
        "user_name": user_name,
        "user_email": user_email,
        "webhook_url": "/api/fireflies/webhook",
        "message": f"Connected as {user_name}. Transcriptions will arrive automatically via webhook.",
    }


@router.post("/disconnect")
async def fireflies_disconnect(
    project_id: int = Query(...),
    db: AsyncSession = Depends(get_session),
):
    """Disconnect Fireflies from a project."""
    result = await db.execute(
        select(Project).where(
            and_(Project.id == project_id, Project.deleted_at.is_(None))
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project.fireflies_config = None
    await db.commit()

    return {"ok": True}


# ============ Transcript Endpoints ============

@router.get("/transcripts")
async def list_transcripts(
    project_id: Optional[int] = None,
    contact_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
):
    """List call transcripts from DB."""
    query = select(CallTranscript).order_by(CallTranscript.date.desc())

    if project_id:
        query = query.where(CallTranscript.project_id == project_id)
    if contact_id:
        query = query.where(CallTranscript.contact_id == contact_id)

    query = query.offset(offset).limit(limit)
    result = await session.execute(query)
    transcripts = result.scalars().all()

    # Get total count
    count_query = select(func.count(CallTranscript.id))
    if project_id:
        count_query = count_query.where(CallTranscript.project_id == project_id)
    if contact_id:
        count_query = count_query.where(CallTranscript.contact_id == contact_id)
    total = (await session.execute(count_query)).scalar()

    return {
        "transcripts": [TranscriptListItem.model_validate(t) for t in transcripts],
        "total": total,
    }


@router.get("/transcripts/{transcript_id}")
async def get_transcript(
    transcript_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get full transcript detail."""
    result = await session.execute(
        select(CallTranscript).where(CallTranscript.id == transcript_id)
    )
    transcript = result.scalar_one_or_none()
    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")

    return TranscriptDetail.model_validate(transcript)


@router.get("/transcripts/contact/{contact_id}")
async def get_contact_transcripts(
    contact_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get all transcripts for a specific contact."""
    result = await session.execute(
        select(CallTranscript)
        .where(CallTranscript.contact_id == contact_id)
        .order_by(CallTranscript.date.desc())
    )
    transcripts = result.scalars().all()
    return {"transcripts": [TranscriptListItem.model_validate(t) for t in transcripts]}


@router.post("/sync", response_model=SyncResponse)
async def sync_transcripts(
    background_tasks: BackgroundTasks,
    project_id: int = Query(...),
    limit: int = 20,
    session: AsyncSession = Depends(get_session),
):
    """Manually sync recent transcripts from Fireflies API for a project."""
    result = await session.execute(
        select(Project).where(
            and_(Project.id == project_id, Project.deleted_at.is_(None))
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    config = project.fireflies_config or {}
    api_key = config.get("api_key")
    if not api_key:
        raise HTTPException(status_code=400, detail="Fireflies not connected for this project")

    background_tasks.add_task(_sync_transcripts_task, api_key, project_id, limit)
    return SyncResponse(synced=0, matched=0, errors=["Sync started in background"])


# ============ Webhook ============

@router.post("/webhook")
async def fireflies_webhook(request: Request):
    """Receive webhook from Fireflies when a transcript is ready.

    Fireflies sends: {"meetingId": "...", "eventType": "Transcription completed"}

    The webhook finds the right project by matching the organizer email
    against project.fireflies_config.user_email across all projects.
    """
    # Optional token validation
    if settings.WEBHOOK_SECRET:
        token = request.query_params.get("token")
        if token != settings.WEBHOOK_SECRET:
            raise HTTPException(status_code=403, detail="Invalid webhook token")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    meeting_id = payload.get("meetingId")
    event_type = payload.get("eventType")

    logger.info(f"Fireflies webhook: event={event_type}, meetingId={meeting_id}")

    if not meeting_id:
        return {"status": "ignored", "reason": "no meetingId"}

    if event_type == "Transcription completed":
        import asyncio
        asyncio.create_task(_process_webhook_transcript(meeting_id))

    return {"status": "ok"}


# ============ Background Tasks ============

async def _find_project_for_transcript(
    session: AsyncSession,
    transcript_data: dict,
) -> Optional[tuple]:
    """Find the project that owns this transcript by matching organizer email.

    Returns (project_id, api_key) or None.
    """
    organizer_email = (
        transcript_data.get("organizer_email")
        or transcript_data.get("host_email")
        or ""
    ).lower()

    # Get all projects with fireflies_config
    result = await session.execute(
        select(Project).where(
            and_(
                Project.fireflies_config.isnot(None),
                Project.deleted_at.is_(None),
            )
        )
    )
    projects = result.scalars().all()

    # Match by user_email in config
    for project in projects:
        config = project.fireflies_config or {}
        project_email = (config.get("user_email") or "").lower()
        if project_email and organizer_email and project_email == organizer_email:
            return project.id, config.get("api_key")

    # Fallback: use first project with fireflies_config that has an api_key
    for project in projects:
        config = project.fireflies_config or {}
        api_key = config.get("api_key")
        if api_key:
            return project.id, api_key

    return None


async def _process_webhook_transcript(meeting_id: str):
    """Fetch transcript from Fireflies and store it."""
    try:
        async with async_session_maker() as session:
            # First, try all projects to find one with a working key
            result = await session.execute(
                select(Project).where(
                    and_(
                        Project.fireflies_config.isnot(None),
                        Project.deleted_at.is_(None),
                    )
                )
            )
            projects = result.scalars().all()

            if not projects:
                logger.warning(f"No projects with Fireflies config for meeting {meeting_id}")
                return

            # Try fetching transcript with first available key
            transcript_data = None
            used_key = None
            for project in projects:
                config = project.fireflies_config or {}
                api_key = config.get("api_key")
                if not api_key:
                    continue
                transcript_data = await fireflies_service.get_transcript(meeting_id, api_key=api_key)
                if transcript_data:
                    used_key = api_key
                    break

            if not transcript_data:
                logger.error(f"Could not fetch transcript {meeting_id} from Fireflies")
                return

            # Now find the right project based on organizer email
            match = await _find_project_for_transcript(session, transcript_data)
            project_id = match[0] if match else projects[0].id

            await _store_transcript(session, transcript_data, project_id=project_id, source="webhook")
            await session.commit()
            logger.info(f"Stored Fireflies transcript: {meeting_id} for project {project_id}")
    except Exception as e:
        logger.error(f"Error processing Fireflies webhook for {meeting_id}: {e}")


async def _sync_transcripts_task(api_key: str, project_id: int, limit: int):
    """Background task to sync transcripts from Fireflies for a specific project."""
    try:
        transcripts = await fireflies_service.get_transcripts(limit=limit, api_key=api_key)
        logger.info(f"Fetched {len(transcripts)} transcripts from Fireflies for project {project_id}")

        async with async_session_maker() as session:
            for t in transcripts:
                # Skip if already synced
                existing = await session.execute(
                    select(CallTranscript).where(
                        CallTranscript.fireflies_id == t["id"]
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                # Fetch full transcript
                full = await fireflies_service.get_transcript(t["id"], api_key=api_key)
                if full:
                    await _store_transcript(session, full, project_id=project_id, source="manual_sync")

            await session.commit()
    except Exception as e:
        logger.error(f"Error syncing Fireflies transcripts for project {project_id}: {e}")


async def _store_transcript(
    session: AsyncSession,
    data: dict,
    project_id: Optional[int] = None,
    source: str = "webhook",
) -> Optional[CallTranscript]:
    """Store a Fireflies transcript and link to contact if possible."""
    fireflies_id = data.get("id")
    if not fireflies_id:
        return None

    # Check for duplicate
    existing = await session.execute(
        select(CallTranscript).where(CallTranscript.fireflies_id == fireflies_id)
    )
    if existing.scalar_one_or_none():
        return None

    # Build plain text from sentences
    sentences = data.get("sentences", [])
    transcript_text = "\n".join(
        f"{s.get('speaker_name', 'Unknown')}: {s.get('text', '')}"
        for s in (sentences or [])
    )

    # Parse date
    call_date = None
    if data.get("date"):
        try:
            call_date = datetime.utcfromtimestamp(int(data["date"]) / 1000)
        except (ValueError, TypeError):
            call_date = None

    # Extract summary
    summary_data = data.get("summary", {}) or {}
    summary_text = summary_data.get("short_summary") or summary_data.get("overview") or ""
    action_items = summary_data.get("action_items")
    keywords = summary_data.get("keywords")

    # Extract attendee emails for contact matching
    attendees = data.get("meeting_attendees", []) or []
    participant_emails = [
        a.get("email") for a in attendees if a.get("email")
    ]
    organizer_email = data.get("organizer_email") or data.get("host_email")
    if organizer_email and organizer_email not in participant_emails:
        participant_emails.append(organizer_email)

    # Try to match a contact by email, scoped to project if available
    contact_id = None
    for email in participant_emails:
        if not email:
            continue
        q = select(Contact.id).where(
            func.lower(Contact.email) == email.lower()
        )
        if project_id:
            q = q.where(Contact.project_id == project_id)
        q = q.limit(1)
        result = await session.execute(q)
        matched = result.scalar_one_or_none()
        if matched:
            contact_id = matched
            break

    # If no match within project, try global
    if not contact_id and project_id:
        for email in participant_emails:
            if not email:
                continue
            result = await session.execute(
                select(Contact.id).where(
                    func.lower(Contact.email) == email.lower()
                ).limit(1)
            )
            matched = result.scalar_one_or_none()
            if matched:
                contact_id = matched
                break

    # Create transcript record
    transcript = CallTranscript(
        fireflies_id=fireflies_id,
        project_id=project_id,
        title=data.get("title"),
        date=call_date,
        duration=data.get("duration"),
        organizer_email=organizer_email,
        participants=[
            {"name": a.get("displayName") or a.get("name"), "email": a.get("email")}
            for a in attendees
        ] if attendees else data.get("participants"),
        speakers=data.get("speakers"),
        summary=summary_text,
        action_items=action_items,
        keywords=keywords,
        transcript_text=transcript_text or None,
        sentences=[
            {
                "speaker": s.get("speaker_name"),
                "text": s.get("text"),
                "start_time": s.get("start_time"),
                "end_time": s.get("end_time"),
            }
            for s in (sentences or [])
        ] if sentences else None,
        transcript_url=data.get("transcript_url"),
        audio_url=data.get("audio_url"),
        contact_id=contact_id,
        source=source,
    )
    session.add(transcript)

    # Create ContactActivity if matched
    if contact_id:
        activity = ContactActivity(
            contact_id=contact_id,
            activity_type="call_transcript",
            channel="phone",
            direction="inbound",
            source="fireflies",
            source_id=fireflies_id,
            subject=data.get("title"),
            snippet=summary_text[:500] if summary_text else None,
            extra_data={
                "duration": data.get("duration"),
                "participants": participant_emails,
                "keywords": keywords,
                "project_id": project_id,
            },
            activity_at=call_date or datetime.utcnow(),
        )
        session.add(activity)

    return transcript
