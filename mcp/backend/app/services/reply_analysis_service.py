"""Background reply analysis — fetches replies from SmartLead campaigns,
classifies them, stores in DB so CRM can filter by reply status.

Runs IN PARALLEL with blacklist import when user tells their campaigns.
"""
import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.db import async_session_maker
from app.models.pipeline import ExtractedContact

logger = logging.getLogger(__name__)

# Reply classification keywords
REPLY_CATEGORIES = {
    "meeting": ["meeting", "call", "schedule", "calendar", "demo", "thursday", "friday", "monday", "tuesday", "wednesday", "time today", "available", "slot", "zoom", "teams"],
    "interested": ["interested", "tell me more", "sounds good", "like to know", "send me", "more info", "pricing", "proposal", "brochure"],
    "question": ["how", "what", "when", "where", "which", "?", "explain", "clarify", "details"],
    "not_interested": ["not interested", "no thank", "remove", "don't contact", "no need", "not looking", "pass", "decline"],
    "out_of_office": ["out of office", "ooo", "vacation", "holiday", "away", "returning", "auto-reply", "automatic reply"],
    "wrong_person": ["wrong person", "not the right", "no longer", "left the company", "moved on", "try reaching"],
    "unsubscribe": ["unsubscribe", "stop emailing", "opt out", "remove me", "don't email"],
}


def classify_reply(text: str) -> tuple[str, float]:
    """Classify a reply text into a category. Returns (category, confidence)."""
    if not text:
        return "other", 0.3

    text_lower = text.lower()

    # Check each category
    scores: Dict[str, int] = {}
    for category, keywords in REPLY_CATEGORIES.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[category] = score

    if not scores:
        return "other", 0.3

    best = max(scores, key=scores.get)
    confidence = min(0.95, 0.5 + scores[best] * 0.15)
    return best, confidence


async def analyze_campaign_replies(
    smartlead_service,
    campaign_ids: List[int],
    campaign_names: Dict[int, str],
    project_id: int,
):
    """Background task: fetch replies from campaigns, classify, store in DB.

    This runs in parallel with blacklist import.
    """
    logger.info(f"Starting background reply analysis for {len(campaign_ids)} campaigns, project {project_id}")

    total_replies = 0
    total_classified = 0

    async with async_session_maker() as session:
        try:
            for camp_id in campaign_ids:
                camp_name = campaign_names.get(camp_id, f"Campaign #{camp_id}")

                # Fetch leads who replied
                replied_leads = await smartlead_service.get_campaign_leads_with_status(
                    camp_id, status="REPLIED", limit=200
                )

                if not replied_leads:
                    continue

                for lead in replied_leads:
                    email = lead.get("email", "")
                    if not email:
                        continue

                    total_replies += 1

                    # Get reply text from lead data
                    reply_text = ""
                    if isinstance(lead.get("reply"), dict):
                        reply_text = lead["reply"].get("text", "")
                    elif isinstance(lead.get("reply"), str):
                        reply_text = lead["reply"]

                    # Classify
                    category, confidence = classify_reply(reply_text)
                    total_classified += 1

                    # Update the contact in DB if it exists
                    result = await session.execute(
                        select(ExtractedContact).where(
                            ExtractedContact.project_id == project_id,
                            ExtractedContact.email == email,
                        )
                    )
                    contact = result.scalar_one_or_none()

                    if contact:
                        # Update source_data with reply info
                        sd = contact.source_data or {}
                        sd["has_replied"] = True
                        sd["reply_category"] = category
                        sd["reply_confidence"] = confidence
                        sd["reply_text_preview"] = reply_text[:200] if reply_text else ""
                        sd["reply_time"] = lead.get("reply_time") or lead.get("replied_at") or str(datetime.utcnow())
                        sd["reply_campaign"] = camp_name
                        contact.source_data = sd

                        # Flag for ORM to detect change
                        from sqlalchemy.orm.attributes import flag_modified
                        flag_modified(contact, "source_data")

            await session.commit()
            logger.info(f"Reply analysis complete: {total_replies} replies, {total_classified} classified for project {project_id}")

        except Exception as e:
            logger.error(f"Reply analysis failed: {e}", exc_info=True)
            await session.rollback()

    return {"total_replies": total_replies, "classified": total_classified}


def start_reply_analysis_background(smartlead_service, campaign_ids, campaign_names, project_id):
    """Fire and forget — runs reply analysis in background asyncio task."""
    loop = asyncio.get_event_loop()
    task = loop.create_task(
        analyze_campaign_replies(smartlead_service, campaign_ids, campaign_names, project_id)
    )
    logger.info(f"Background reply analysis started for project {project_id}, {len(campaign_ids)} campaigns")
    return task
