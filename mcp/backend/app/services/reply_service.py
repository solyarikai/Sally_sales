"""MCP Reply Service — fully independent reply processing.

Reuses classification/draft logic from main app (same code, own execution).
Stores replies in MCP's own database. No proxy to main backend.

Architecture:
- SmartLead polling: fetch replied leads from campaigns with tracking_enabled
- Classification: GPT-4o-mini (same prompt as main app)
- Draft generation: Gemini 2.5 Pro (same logic)
- Storage: MCPReply table in MCP DB
- Notifications: Telegram (reuse format from main app)
"""
import asyncio
import hashlib
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm.attributes import flag_modified

from app.db import async_session_maker
from app.models.reply import MCPReply
from app.models.campaign import Campaign
from app.models.project import Project

logger = logging.getLogger(__name__)

# ── Classification prompt (same as main app) ──
CLASSIFY_PROMPT = """Classify this email reply into exactly one category.

Categories:
- interested: ANY positive signal (wants more info, says yes, shares contact, asks pricing)
- meeting_request: Wants to schedule call/meeting, shares availability, mentions calendar
- not_interested: EXPLICIT decline (polite or direct refusal)
- out_of_office: Auto-reply, vacation, away message
- wrong_person: Not the right contact, suggests someone else, left the company
- unsubscribe: Wants to opt out, stop emailing
- question: Has specific questions before deciding
- other: Doesn't fit above categories

Rules:
- Short affirmative replies ("sure", "sounds good", "yes") = interested
- If person shares contact info on different channel = interested
- When in doubt between interested and question → interested

Return ONLY valid JSON: {"category": "...", "confidence": "high|medium|low", "reasoning": "..."}"""


def _strip_html(html: str) -> str:
    """Strip HTML tags from email body."""
    if not html:
        return ""
    text = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</(?:div|p|li|tr)>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    try:
        from html import unescape
        text = unescape(text)
    except Exception:
        pass
    return text.strip()


def _message_hash(text: str) -> str:
    """MD5 hash of normalized reply text for dedup."""
    normalized = (text or "")[:500].lower().strip()
    return hashlib.md5(normalized.encode()).hexdigest()


async def classify_reply(subject: str, body: str, openai_key: str) -> Dict[str, str]:
    """Classify a reply using GPT-4o-mini. Returns {category, confidence, reasoning}."""
    import httpx
    import json

    text = _strip_html(body)
    user_prompt = f"Subject: {subject}\n\nReply:\n{text[:2000]}"

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": CLASSIFY_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    "max_tokens": 100,
                    "temperature": 0,
                },
            )
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            clean = content.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1].rsplit("```", 1)[0]
            return json.loads(clean)
    except Exception as e:
        logger.warning(f"Classification failed: {e}")
        return {"category": "other", "confidence": "low", "reasoning": f"Classification error: {str(e)[:80]}"}


async def sync_campaign_replies(
    smartlead_service,
    campaign: Campaign,
    project: Project,
    openai_key: Optional[str] = None,
    session: Optional[AsyncSession] = None,
) -> Dict[str, Any]:
    """Sync replies for a single campaign from SmartLead.

    Fetches replied leads, classifies new ones, stores in MCPReply.
    """
    own_session = session is None
    if own_session:
        session = async_session_maker()

    stats = {"new": 0, "existing": 0, "classified": 0, "errors": 0}

    try:
        campaign_ext_id = int(campaign.external_id) if campaign.external_id else None
        if not campaign_ext_id:
            return stats

        # Fetch replied leads from SmartLead
        replied_leads = await smartlead_service.get_campaign_leads_with_status(
            campaign_ext_id, status="REPLIED", limit=500
        )

        for lead_data in (replied_leads or []):
            lead = lead_data.get("lead", lead_data)
            email = lead.get("email", "")
            if not email:
                continue

            # Get reply text
            reply_text = ""
            try:
                messages = await smartlead_service.get_lead_message_history(campaign_ext_id, email)
                if messages:
                    for msg in reversed(messages if isinstance(messages, list) else []):
                        if (msg.get("type") or "").upper() == "REPLY":
                            reply_text = _strip_html(msg.get("email_body") or msg.get("body") or "")
                            break
            except Exception:
                pass

            if not reply_text:
                continue

            # Dedup check
            msg_hash = _message_hash(reply_text)
            existing = await session.execute(
                select(MCPReply).where(
                    MCPReply.lead_email == email,
                    MCPReply.campaign_external_id == str(campaign_ext_id),
                    MCPReply.message_hash == msg_hash,
                )
            )
            if existing.scalar_one_or_none():
                stats["existing"] += 1
                continue

            # Classify
            classification = {"category": "other", "confidence": "low", "reasoning": ""}
            if openai_key:
                subject = lead.get("email_subject", "")
                classification = await classify_reply(subject, reply_text, openai_key)
                stats["classified"] += 1

            cat = classification.get("category", "other")

            # Store
            reply = MCPReply(
                project_id=project.id,
                campaign_id=campaign.id,
                lead_email=email,
                lead_name=f"{lead.get('first_name', '')} {lead.get('last_name', '')}".strip(),
                lead_company=lead.get("company_name", ""),
                campaign_name=campaign.name,
                campaign_external_id=str(campaign_ext_id),
                source="smartlead",
                channel="email",
                email_subject=lead.get("email_subject", ""),
                reply_text=reply_text[:5000],
                received_at=lead.get("reply_time") or lead.get("replied_at"),
                category=cat,
                category_confidence=classification.get("confidence", "low"),
                classification_reasoning=classification.get("reasoning", ""),
                needs_reply=cat in ("interested", "meeting_request", "question"),
                smartlead_lead_id=str(lead.get("id", "")),
                message_hash=msg_hash,
            )
            session.add(reply)
            stats["new"] += 1

        if own_session:
            await session.commit()
        else:
            await session.flush()

    except Exception as e:
        logger.error(f"Reply sync failed for campaign {campaign.name}: {e}")
        stats["errors"] += 1
        if own_session:
            await session.rollback()

    return stats


async def sync_all_tracked_replies(user_id: int):
    """Sync replies for all campaigns with tracking_enabled for a user."""
    async with async_session_maker() as session:
        # Get user's projects
        projects = (await session.execute(
            select(Project).where(Project.user_id == user_id, Project.is_active == True)
        )).scalars().all()

        if not projects:
            return {"message": "No projects"}

        project_ids = [p.id for p in projects]
        project_map = {p.id: p for p in projects}

        # Get tracked campaigns
        campaigns = (await session.execute(
            select(Campaign).where(
                Campaign.project_id.in_(project_ids),
                Campaign.external_id.isnot(None),
            )
        )).scalars().all()

        if not campaigns:
            return {"message": "No campaigns with external IDs"}

        # Get SmartLead service
        from app.models.integration import MCPIntegrationSetting
        from app.services.encryption import decrypt_value
        from app.services.smartlead_service import SmartLeadService

        sl_setting = (await session.execute(
            select(MCPIntegrationSetting).where(
                MCPIntegrationSetting.user_id == user_id,
                MCPIntegrationSetting.integration_name == "smartlead",
            )
        )).scalar_one_or_none()

        if not sl_setting:
            return {"message": "SmartLead not connected"}

        sl_key = decrypt_value(sl_setting.api_key_encrypted)
        svc = SmartLeadService(api_key=sl_key)

        # Get OpenAI key
        openai_setting = (await session.execute(
            select(MCPIntegrationSetting).where(
                MCPIntegrationSetting.user_id == user_id,
                MCPIntegrationSetting.integration_name == "openai",
            )
        )).scalar_one_or_none()
        openai_key = decrypt_value(openai_setting.api_key_encrypted) if openai_setting else None

        total_stats = {"campaigns": 0, "new_replies": 0, "classified": 0}

        for campaign in campaigns:
            project = project_map.get(campaign.project_id)
            if not project:
                continue

            stats = await sync_campaign_replies(svc, campaign, project, openai_key, session)
            total_stats["campaigns"] += 1
            total_stats["new_replies"] += stats["new"]
            total_stats["classified"] += stats["classified"]

        await session.commit()
        return total_stats
