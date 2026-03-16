"""API endpoints for Fireflies.ai call transcript integration."""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel
from app.db import get_session, async_session_maker
from app.models import Contact, ContactActivity
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


# ============ Endpoints ============

@router.get("/transcripts")
async def list_transcripts(
    contact_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
):
    """List call transcripts from DB."""
    query = select(CallTranscript).order_by(CallTranscript.date.desc())

    if contact_id:
        query = query.where(CallTranscript.contact_id == contact_id)

    query = query.offset(offset).limit(limit)
    result = await session.execute(query)
    transcripts = result.scalars().all()

    # Get total count
    count_query = select(func.count(CallTranscript.id))
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
    limit: int = 20,
    session: AsyncSession = Depends(get_session),
):
    """Manually sync recent transcripts from Fireflies API."""
    if not fireflies_service.is_connected():
        raise HTTPException(status_code=400, detail="Fireflies not connected")

    background_tasks.add_task(_sync_transcripts_task, limit)
    return SyncResponse(synced=0, matched=0, errors=["Sync started in background"])


@router.post("/webhook")
async def fireflies_webhook(request: Request):
    """Receive webhook from Fireflies when a transcript is ready.

    Fireflies sends: {"meetingId": "...", "eventType": "Transcription completed"}
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
        # Process in background
        import asyncio
        asyncio.create_task(_process_webhook_transcript(meeting_id))

    return {"status": "ok"}


# ============ Background Tasks ============

async def _process_webhook_transcript(meeting_id: str):
    """Fetch transcript from Fireflies and store it."""
    try:
        transcript_data = await fireflies_service.get_transcript(meeting_id)
        if not transcript_data:
            logger.error(f"Could not fetch transcript {meeting_id} from Fireflies")
            return

        async with async_session_maker() as session:
            await _store_transcript(session, transcript_data, source="webhook")
            await session.commit()
            logger.info(f"Stored Fireflies transcript: {meeting_id}")
    except Exception as e:
        logger.error(f"Error processing Fireflies webhook for {meeting_id}: {e}")


async def _sync_transcripts_task(limit: int):
    """Background task to sync transcripts from Fireflies."""
    try:
        transcripts = await fireflies_service.get_transcripts(limit=limit)
        logger.info(f"Fetched {len(transcripts)} transcripts from Fireflies")

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
                full = await fireflies_service.get_transcript(t["id"])
                if full:
                    await _store_transcript(session, full, source="manual_sync")

            await session.commit()
    except Exception as e:
        logger.error(f"Error syncing Fireflies transcripts: {e}")


async def _store_transcript(
    session: AsyncSession,
    data: dict,
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
            # Fireflies returns epoch milliseconds
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
    # Also include organizer email
    organizer_email = data.get("organizer_email") or data.get("host_email")
    if organizer_email and organizer_email not in participant_emails:
        participant_emails.append(organizer_email)

    # Try to match a contact by email
    contact_id = None
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
            },
            activity_at=call_date or datetime.utcnow(),
        )
        session.add(activity)

    return transcript
