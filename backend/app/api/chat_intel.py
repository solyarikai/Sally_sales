"""Chat Intelligence API — Telegram chat logs + Gemini-analyzed insights per cluster."""
import json
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, Query
from sqlalchemy import select, func, text, desc

from app.core.config import settings
from app.db import async_session_maker
from app.models.telegram_chat import TelegramChat, TelegramChatMessage, TelegramChatInsight

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat-intel", tags=["chat-intel"])

# The 7 clusters discovered from Rizzult chat analysis
CLUSTERS = [
    {
        "id": "contract_legal",
        "name": "Contract & Legal",
        "description": "Contract negotiation, invoicing, legal terms, DocuSign",
        "keywords": ["договор", "контракт", "оплат", "invoice", "подпис", "legal", "юрист", "рефанд", "DocuSign"],
        "icon": "file-text",
    },
    {
        "id": "onboarding",
        "name": "Onboarding & Setup",
        "description": "ICP definition, domain warming, LinkedIn setup, tool configuration",
        "keywords": ["ICP", "прогрев", "warming", "настро", "setup", "GoLogin", "SmartLead", "Calendly", "HubSpot", "подключ"],
        "icon": "settings",
    },
    {
        "id": "lead_ops",
        "name": "Lead Operations",
        "description": "Lead-by-lead coordination, responses, follow-ups, LinkedIn profiles",
        "keywords": ["лид", "lead", "ответ", "reply", "follow", "LinkedIn", "написал", "ответил", "interested", "meeting book"],
        "icon": "users",
    },
    {
        "id": "segments",
        "name": "Segments & Strategy",
        "description": "Segment planning, ICP expansion, positioning, messaging templates",
        "keywords": ["сегмент", "segment", "гипотез", "hypothesis", "fintech", "foodtech", "QSR", "mobility", "messaging", "позициониров"],
        "icon": "target",
    },
    {
        "id": "reporting",
        "name": "Reporting & Metrics",
        "description": "Weekly reports, reply rates, conversion stats, cost per meeting",
        "keywords": ["отчет", "report", "статистик", "конверси", "reply rate", "meeting rate", "cost per", "CPM", "процент"],
        "icon": "bar-chart",
    },
    {
        "id": "infrastructure",
        "name": "Technical Infrastructure",
        "description": "HubSpot sync, GoLogin, domain issues, mailbox setup, integrations",
        "keywords": ["sync", "синхрон", "ошибк", "error", "домен", "mailbox", "почтов", "GoLogin", "API", "интеграц"],
        "icon": "cpu",
    },
    {
        "id": "scaling",
        "name": "Scaling & Growth",
        "description": "Team expansion, new channels, volume targets, WhatsApp, cold calling",
        "keywords": ["масштаб", "scaling", "x2", "новы", "расшир", "WhatsApp", "cold call", "звонк", "команд", "team"],
        "icon": "trending-up",
    },
]


def _classify_message(text: str) -> Optional[str]:
    """Quick keyword-based classification for display. Gemini does the real analysis."""
    if not text:
        return None
    text_lower = text.lower()
    best_cluster = None
    best_score = 0
    for cluster in CLUSTERS:
        score = sum(1 for kw in cluster["keywords"] if kw.lower() in text_lower)
        if score > best_score:
            best_score = score
            best_cluster = cluster["id"]
    return best_cluster if best_score > 0 else None


@router.get("/projects/{project_id}/messages")
async def get_chat_messages(
    project_id: int,
    limit: int = Query(100, le=500),
    offset: int = Query(0),
    cluster: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
):
    """Get telegram chat messages for a project, with optional cluster/search filter."""
    async with async_session_maker() as session:
        # Find chat linked to project
        chat_result = await session.execute(
            select(TelegramChat).where(TelegramChat.project_id == project_id)
        )
        chat = chat_result.scalar_one_or_none()
        if not chat:
            # Try to find any chat (for now, return first active chat)
            chat_result = await session.execute(
                select(TelegramChat).where(TelegramChat.is_active == 1).limit(1)
            )
            chat = chat_result.scalar_one_or_none()

        if not chat:
            return {"messages": [], "total": 0, "clusters": CLUSTERS}

        # Build query
        q = select(TelegramChatMessage).where(
            TelegramChatMessage.chat_id == chat.chat_id
        )

        if search:
            q = q.where(TelegramChatMessage.text.ilike(f"%{search}%"))

        # Count
        count_q = select(func.count()).select_from(
            q.subquery()
        )
        total = (await session.execute(count_q)).scalar() or 0

        # Fetch messages
        q = q.order_by(desc(TelegramChatMessage.sent_at)).offset(offset).limit(limit)
        result = await session.execute(q)
        messages = result.scalars().all()

        msg_list = []
        for m in messages:
            cluster_id = _classify_message(m.text)
            if cluster and cluster_id != cluster:
                continue
            msg_list.append({
                "id": m.id,
                "message_id": m.message_id,
                "sender_name": m.sender_name,
                "sender_username": m.sender_username,
                "text": m.text,
                "sent_at": m.sent_at.isoformat() if m.sent_at else None,
                "message_type": m.message_type,
                "cluster": cluster_id,
            })

        return {
            "messages": msg_list,
            "total": total,
            "chat_title": chat.chat_title,
            "chat_id": chat.chat_id,
            "clusters": CLUSTERS,
        }


@router.get("/projects/{project_id}/stats")
async def get_chat_stats(project_id: int):
    """Get chat statistics: message counts by sender, cluster, date."""
    async with async_session_maker() as session:
        chat_result = await session.execute(
            select(TelegramChat).where(TelegramChat.project_id == project_id)
        )
        chat = chat_result.scalar_one_or_none()
        if not chat:
            chat_result = await session.execute(
                select(TelegramChat).where(TelegramChat.is_active == 1).limit(1)
            )
            chat = chat_result.scalar_one_or_none()

        if not chat:
            return {"total": 0, "by_sender": [], "by_month": [], "date_range": None}

        # Total
        total = (await session.execute(
            select(func.count()).where(TelegramChatMessage.chat_id == chat.chat_id)
        )).scalar() or 0

        # By sender
        sender_q = await session.execute(
            select(
                TelegramChatMessage.sender_name,
                func.count().label("count")
            ).where(
                TelegramChatMessage.chat_id == chat.chat_id
            ).group_by(TelegramChatMessage.sender_name).order_by(desc("count"))
        )
        by_sender = [{"name": r[0], "count": r[1]} for r in sender_q.all()]

        # By month
        month_q = await session.execute(
            select(
                func.to_char(TelegramChatMessage.sent_at, 'YYYY-MM').label("month"),
                func.count().label("count")
            ).where(
                TelegramChatMessage.chat_id == chat.chat_id
            ).group_by("month").order_by("month")
        )
        by_month = [{"month": r[0], "count": r[1]} for r in month_q.all()]

        # Date range
        range_q = await session.execute(
            select(
                func.min(TelegramChatMessage.sent_at),
                func.max(TelegramChatMessage.sent_at),
            ).where(TelegramChatMessage.chat_id == chat.chat_id)
        )
        range_row = range_q.one()

        return {
            "total": total,
            "chat_title": chat.chat_title,
            "by_sender": by_sender,
            "by_month": by_month,
            "date_range": {
                "first": range_row[0].isoformat() if range_row[0] else None,
                "last": range_row[1].isoformat() if range_row[1] else None,
            } if range_row[0] else None,
        }


@router.get("/projects/{project_id}/insights")
async def get_insights(project_id: int):
    """Get Gemini-generated insights per cluster."""
    async with async_session_maker() as session:
        chat_result = await session.execute(
            select(TelegramChat).where(TelegramChat.project_id == project_id)
        )
        chat = chat_result.scalar_one_or_none()
        if not chat:
            chat_result = await session.execute(
                select(TelegramChat).where(TelegramChat.is_active == 1).limit(1)
            )
            chat = chat_result.scalar_one_or_none()

        if not chat:
            return {"insights": [], "clusters": CLUSTERS}

        result = await session.execute(
            select(TelegramChatInsight).where(
                TelegramChatInsight.chat_id == chat.chat_id
            ).order_by(desc(TelegramChatInsight.created_at))
        )
        insights = result.scalars().all()

        return {
            "insights": [{
                "id": i.id,
                "topic": i.topic,
                "summary": i.summary,
                "key_points": i.key_points,
                "action_items": i.action_items,
                "created_at": i.created_at.isoformat() if i.created_at else None,
            } for i in insights],
            "clusters": CLUSTERS,
        }


@router.post("/projects/{project_id}/analyze")
async def analyze_chat(project_id: int):
    """Run Gemini 2.5 Pro analysis on chat messages, generating insights per cluster."""
    if not settings.GEMINI_API_KEY:
        return {"error": "GEMINI_API_KEY not configured"}

    async with async_session_maker() as session:
        chat_result = await session.execute(
            select(TelegramChat).where(TelegramChat.project_id == project_id)
        )
        chat = chat_result.scalar_one_or_none()
        if not chat:
            chat_result = await session.execute(
                select(TelegramChat).where(TelegramChat.is_active == 1).limit(1)
            )
            chat = chat_result.scalar_one_or_none()

        if not chat:
            return {"error": "No chat found for this project"}

        # Fetch last 500 messages for analysis
        msg_result = await session.execute(
            select(TelegramChatMessage).where(
                TelegramChatMessage.chat_id == chat.chat_id,
                TelegramChatMessage.text.isnot(None),
            ).order_by(desc(TelegramChatMessage.sent_at)).limit(500)
        )
        messages = list(reversed(msg_result.scalars().all()))

        if not messages:
            return {"error": "No messages to analyze"}

        # Build conversation text
        conv_text = "\n".join(
            f"[{m.sent_at.strftime('%Y-%m-%d %H:%M')}] {m.sender_name}: {m.text}"
            for m in messages if m.text
        )

        cluster_descriptions = "\n".join(
            f"- {c['id']}: {c['name']} — {c['description']}"
            for c in CLUSTERS
        )

        prompt = f"""You are analyzing a B2B client communication chat between Sally (lead gen agency) and their client.

Here are the communication clusters to analyze:
{cluster_descriptions}

For EACH cluster, provide:
1. **summary**: 2-3 sentence summary of current status and recent activity
2. **key_points**: List of 3-5 key observations (strings)
3. **action_items**: List of specific actionable next steps for the operator (strings). Be concrete — "Follow up with X about Y" not "Improve communication"

Focus on what's ACTIONABLE for the operator RIGHT NOW. What should they do next? What's falling through the cracks? What opportunities are being missed?

Respond in JSON format:
{{
  "clusters": [
    {{
      "topic": "cluster_id",
      "summary": "...",
      "key_points": ["...", "..."],
      "action_items": ["...", "..."]
    }}
  ]
}}

Here is the chat history (last 500 messages):

{conv_text[:80000]}"""

        # Call Gemini 2.5 Pro
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent?key={settings.GEMINI_API_KEY}",
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {
                            "maxOutputTokens": 8000,
                            "temperature": 0.3,
                            "responseMimeType": "application/json",
                        },
                    },
                )
                data = resp.json()
                logger.info(f"Gemini response keys: {list(data.keys())}")
                if "error" in data:
                    logger.error(f"Gemini API error: {data['error']}")
                    return {"error": f"Gemini API error: {data['error'].get('message', data['error'])}"}
                candidates = data.get("candidates", [])
                if not candidates:
                    logger.error(f"Gemini no candidates: {json.dumps(data)[:500]}")
                    return {"error": "Gemini returned no candidates"}
                content = candidates[0].get("content", {})
                parts = content.get("parts", [])
                if not parts:
                    logger.error(f"Gemini no parts: {json.dumps(candidates[0])[:500]}")
                    return {"error": "Gemini returned no content parts"}
                raw_text = parts[0]["text"]
                analysis = json.loads(raw_text)
        except Exception as e:
            logger.error(f"Gemini analysis failed: {e}", exc_info=True)
            return {"error": f"Gemini analysis failed: {str(e)}"}

        # Store insights
        insights_created = []
        for cluster_data in analysis.get("clusters", []):
            insight = TelegramChatInsight(
                chat_id=chat.chat_id,
                topic=cluster_data["topic"],
                summary=cluster_data.get("summary", ""),
                key_points=cluster_data.get("key_points"),
                action_items=cluster_data.get("action_items"),
                first_message_at=messages[0].sent_at if messages else None,
                last_message_at=messages[-1].sent_at if messages else None,
            )
            session.add(insight)
            insights_created.append({
                "topic": insight.topic,
                "summary": insight.summary,
                "key_points": insight.key_points,
                "action_items": insight.action_items,
            })

        await session.commit()
        logger.info(f"Chat analysis complete: {len(insights_created)} cluster insights created")

        return {
            "insights": insights_created,
            "messages_analyzed": len(messages),
        }
