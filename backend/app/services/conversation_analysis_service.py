"""
Conversation Analysis Service — Get project conversations and generate auto-reply prompts.
"""
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, String, exists

from app.models.contact import Contact, ContactActivity, Project
from app.models.reply import ReplyPromptTemplateModel
from app.services.openai_service import openai_service

logger = logging.getLogger(__name__)

ANALYSIS_SYSTEM_PROMPT = """You are an expert outbound sales reply strategist. You will receive real conversation threads between our SDR team and prospects from a specific outbound campaign project.

Your task: Generate a DETAILED reply prompt template that an AI assistant will use to draft replies to incoming prospect messages.

CRITICAL REQUIREMENTS for the prompt template:
1. EXTRACT the exact product/service name, key value propositions, and pitch angles from the outbound messages you see
2. IDENTIFY the language(s) used — reply in the SAME language as the prospect's message
3. For each reply category below, provide a SPECIFIC strategy with example phrasing (not generic placeholders):
   - INTERESTED: How to move to a call/demo, what to offer next, scheduling language
   - QUESTIONS: How to answer common questions about pricing, features, geography, compliance
   - NOT_INTERESTED: Polite close that leaves door open, no begging
   - MEETING_REQUEST: Confirm, suggest times, share booking link if available
   - REDIRECT (e.g. "contact us at email@..."): Thank them and follow up at that channel
   - OBJECTION (e.g. "we already have a solution"): Brief differentiator, offer comparison
4. Keep the tone matching what you observe — if outbound is casual/emoji-heavy, keep it; if formal, stay formal
5. Include the specific company/product context: what we sell, to whom, key differentiators
6. The template should instruct the AI to personalize using: prospect's first name, their company name, their specific reply content, and the channel (email vs LinkedIn)
7. For LinkedIn replies keep it SHORT (2-4 sentences max). For email replies allow slightly longer responses.

Output ONLY the prompt template instructions (no JSON, no markdown headers, no meta-commentary). The output will be injected as system instructions for the reply-drafting AI."""


async def get_project_conversations(
    session: AsyncSession,
    project_id: int,
    max_conversations: int = 10,
) -> List[Dict[str, Any]]:
    """
    Get formatted conversation threads for contacts in a project.

    Finds contacts with has_replied=True matching project's campaign_filters,
    fetches their ContactActivity records (both inbound + outbound, chronological),
    and formats into readable text.
    """
    # Get project and its campaign filters
    result = await session.execute(
        select(Project).where(
            and_(Project.id == project_id, Project.deleted_at.is_(None))
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        logger.warning(f"Project {project_id} not found")
        return []

    logger.info(f"get_project_conversations: project={project.name}, filters={len(project.campaign_filters or [])}")

    # Require contacts to have at least one activity record
    has_activities = exists(
        select(ContactActivity.id).where(ContactActivity.contact_id == Contact.id)
    )

    # Build query for contacts matching campaign filters
    if project.campaign_filters and len(project.campaign_filters) > 0:
        campaign_conditions = [
            Contact.platform_state.cast(String).ilike(f'%{cf}%')
            for cf in project.campaign_filters
        ]
        contact_query = (
            select(Contact)
            .where(
                and_(
                    or_(*campaign_conditions),
                    Contact.last_reply_at.isnot(None),
                    Contact.deleted_at.is_(None),
                    has_activities,
                )
            )
            .order_by(Contact.last_reply_at.desc())
            .limit(max_conversations)
        )
    else:
        contact_query = (
            select(Contact)
            .where(
                and_(
                    Contact.project_id == project_id,
                    Contact.last_reply_at.isnot(None),
                    Contact.deleted_at.is_(None),
                    has_activities,
                )
            )
            .order_by(Contact.last_reply_at.desc())
            .limit(max_conversations)
        )

    logger.info(f"Executing contacts query...")
    contacts_result = await session.execute(contact_query)
    contacts = contacts_result.scalars().all()

    conversations = []
    for contact in contacts:
        # Get all activities for this contact, chronological
        activities_result = await session.execute(
            select(ContactActivity)
            .where(ContactActivity.contact_id == contact.id)
            .order_by(ContactActivity.activity_at.asc())
        )
        activities = activities_result.scalars().all()

        if not activities:
            continue

        messages = []
        for act in activities:
            sender = "US" if act.direction == "outbound" else "PROSPECT"
            body = act.body or act.snippet or "(no content)"
            messages.append({
                "sender": sender,
                "channel": act.channel,
                "type": act.activity_type,
                "body": body[:500],
                "at": act.activity_at.isoformat() if act.activity_at else "",
            })

        conversations.append({
            "contact_id": contact.id,
            "email": contact.email,
            "name": f"{contact.first_name or ''} {contact.last_name or ''}".strip(),
            "company": contact.company_name,
            "job_title": contact.job_title,
            "messages": messages,
        })

    return conversations


def format_conversations_for_prompt(conversations: List[Dict[str, Any]]) -> str:
    """Format conversations list into readable text for GPT analysis."""
    parts = []
    for i, conv in enumerate(conversations, 1):
        header = f"--- Conversation #{i}: {conv['name']} ({conv.get('company', 'N/A')}) ---"
        parts.append(header)
        for msg in conv["messages"]:
            parts.append(f"[{msg['sender']}] ({msg['channel']}) {msg['body']}")
        parts.append("")

    return "\n".join(parts)


def format_conversations_debug(conversations: List[Dict[str, Any]]) -> str:
    """Format conversations for debug/review output."""
    parts = []
    for i, conv in enumerate(conversations, 1):
        parts.append(f"=== Conversation #{i} ===")
        parts.append(f"Contact: {conv['name']} | {conv['email']}")
        parts.append(f"Company: {conv.get('company', 'N/A')} | Title: {conv.get('job_title', 'N/A')}")
        parts.append(f"Messages ({len(conv['messages'])}):")
        for msg in conv["messages"]:
            parts.append(f"  [{msg['sender']}] ({msg['channel']}, {msg['at'][:10]})")
            parts.append(f"    {msg['body'][:300]}")
        parts.append("")

    return "\n".join(parts)


async def generate_auto_reply_prompt(
    session: AsyncSession,
    project_id: int,
    max_conversations: int = 10,
) -> Optional[Dict[str, Any]]:
    """
    Analyze project conversations and generate an auto-reply prompt template.

    1. Calls get_project_conversations() to get formatted conversations
    2. Sends to GPT-4o-mini with system prompt asking to analyze patterns
    3. Stores result in ReplyPromptTemplateModel
    4. Links to project via reply_prompt_template_id
    """
    # Get project
    result = await session.execute(
        select(Project).where(
            and_(Project.id == project_id, Project.deleted_at.is_(None))
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        return None

    conversations = await get_project_conversations(session, project_id, max_conversations)
    if not conversations:
        return {"error": "No conversations with replies found for this project"}

    formatted = format_conversations_for_prompt(conversations)

    user_prompt = f"""Project: {project.name}
Campaign filters: {', '.join(project.campaign_filters or [])}

Here are {len(conversations)} recent conversation threads from this project:

{formatted}

Based on these real conversations, generate a reply prompt template for this specific project."""

    if not openai_service.is_connected():
        return {"error": "OpenAI not configured"}

    try:
        prompt_text = await openai_service.complete(
            prompt=user_prompt,
            system_prompt=ANALYSIS_SYSTEM_PROMPT,
            model="gpt-4o-mini",
            temperature=0.7,
            max_tokens=1500,
        )
    except Exception as e:
        logger.error(f"GPT analysis failed for project {project_id}: {e}")
        return {"error": f"GPT analysis failed: {e}"}

    # Store as ReplyPromptTemplateModel
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    template = ReplyPromptTemplateModel(
        name=f"{project.name} - Auto-Reply - {timestamp}",
        prompt_type="reply",
        prompt_text=prompt_text,
        is_default=False,
    )
    session.add(template)
    await session.flush()

    # Link to project
    project.reply_prompt_template_id = template.id
    project.updated_at = datetime.utcnow()

    return {
        "template_id": template.id,
        "template_name": template.name,
        "prompt_text": prompt_text,
        "conversations_analyzed": len(conversations),
    }
