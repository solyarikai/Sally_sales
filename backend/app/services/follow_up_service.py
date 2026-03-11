"""Automated follow-up draft generation.

Creates follow-up drafts for leads who haven't responded after the operator sent a reply.
Drafts are pre-generated using AI (same as regular replies) so operators see ready-to-send
follow-ups without an extra "Generate" step.

Logic:
  1. Find approved/auto_resolved replies older than N days (default 3)
  2. Skip if lead sent a newer inbound message
  3. Skip if a follow-up was already created for this reply
  4. Generate an AI follow-up draft (using project's template + knowledge)
  5. Create a new ProcessedReply (pending) linked to the original
"""
import hashlib
import logging
import time as _time
from datetime import datetime, timedelta

from sqlalchemy import select, and_, exists, func, text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.reply import ProcessedReply, ThreadMessage

logger = logging.getLogger(__name__)

MAX_FOLLOW_UPS = 1
FOLLOW_UP_DELAY_DAYS = 3
MAX_AGE_DAYS = 60  # Don't follow up on conversations older than 60 days


async def generate_follow_up_drafts(session: AsyncSession, limit: int = 20) -> dict:
    """Find replies needing follow-up and create AI-generated draft records.

    Uses the same AI draft pipeline as regular replies — with follow-up context
    injected so the model writes a short reminder, not a full pitch.

    Returns stats dict with counts.
    """
    t0 = _time.monotonic()
    stats = {"checked": 0, "created": 0, "skipped_inbound": 0, "skipped_existing": 0, "errors": 0}

    cutoff = datetime.utcnow() - timedelta(days=FOLLOW_UP_DELAY_DAYS)
    max_age = datetime.utcnow() - timedelta(days=MAX_AGE_DAYS)

    # Find approved/auto_resolved replies that need follow-up.
    # All filtering done at SQL level — no wasted slots on already-processed candidates.
    existing_child = aliased(ProcessedReply)
    newer_inbound = aliased(ProcessedReply)

    candidates = await session.execute(
        select(ProcessedReply).where(
            and_(
                ProcessedReply.approval_status.in_(["approved", "auto_resolved"]),
                ProcessedReply.approved_at.isnot(None),
                ProcessedReply.approved_at < cutoff,
                ProcessedReply.approved_at > max_age,
                ProcessedReply.received_at > max_age,
                ProcessedReply.follow_up_number.is_(None),
                ProcessedReply.parent_reply_id.is_(None),
                ProcessedReply.category.in_(["meeting_request", "interested", "question"]),
                # No existing child follow-up
                ~exists(
                    select(existing_child.id).where(
                        existing_child.parent_reply_id == ProcessedReply.id,
                    )
                ),
                # No newer inbound from lead
                ~exists(
                    select(newer_inbound.id).where(
                        newer_inbound.lead_email == ProcessedReply.lead_email,
                        newer_inbound.received_at > ProcessedReply.approved_at,
                        newer_inbound.parent_reply_id.is_(None),
                        newer_inbound.id != ProcessedReply.id,
                    )
                ),
                # Last message in thread must be outbound (we sent something, waiting for response)
                ~exists(
                    select(ThreadMessage.id).where(
                        ThreadMessage.reply_id == ProcessedReply.id,
                        ThreadMessage.direction == "inbound",
                        ThreadMessage.position == (
                            select(func.max(ThreadMessage.position))
                            .where(ThreadMessage.reply_id == ProcessedReply.id)
                            .correlate(ProcessedReply)
                            .scalar_subquery()
                        ),
                    )
                ),
            )
        ).order_by(ProcessedReply.approved_at.asc()).limit(limit)
    )
    replies = candidates.scalars().all()
    stats["checked"] = len(replies)

    if not replies:
        elapsed = int((_time.monotonic() - t0) * 1000)
        logger.info(f"[FOLLOW-UP] No candidates ({elapsed}ms)")
        return stats

    for reply in replies:
        try:

            # Generate AI follow-up draft
            draft_text = await _generate_ai_followup_draft(session, reply)

            # Create follow-up ProcessedReply
            fu_hash = hashlib.md5(f"followup_{reply.id}_{1}".encode()).hexdigest()
            follow_up = ProcessedReply(
                automation_id=reply.automation_id,
                campaign_id=reply.campaign_id,
                campaign_name=reply.campaign_name,
                source=reply.source,
                channel=reply.channel,
                lead_email=reply.lead_email,
                lead_first_name=reply.lead_first_name,
                lead_last_name=reply.lead_last_name,
                lead_company=reply.lead_company,
                email_subject=reply.email_subject,
                email_body=f"(Follow-up — no response after {FOLLOW_UP_DELAY_DAYS} days)",
                category=reply.category,
                category_confidence="high",
                classification_reasoning=f"Auto-generated follow-up for reply #{reply.id}",
                draft_reply=draft_text,
                draft_subject=reply.draft_subject,
                draft_generated_at=datetime.utcnow(),
                processed_at=datetime.utcnow(),
                received_at=datetime.utcnow(),
                approval_status=None,  # pending — appears in operator queue
                inbox_link=reply.inbox_link,
                raw_webhook_data=reply.raw_webhook_data,
                smartlead_lead_id=reply.smartlead_lead_id,
                message_hash=fu_hash,
                parent_reply_id=reply.id,
                follow_up_number=1,
            )
            session.add(follow_up)
            await session.flush()
            stats["created"] += 1

            logger.info(
                f"[FOLLOW-UP] Created #{follow_up.id} for reply #{reply.id} "
                f"({reply.lead_email}, {reply.campaign_name})"
            )

        except Exception as e:
            logger.error(f"[FOLLOW-UP] Error processing reply #{reply.id}: {e}")
            stats["errors"] += 1

    if stats["created"] > 0:
        await session.commit()

    elapsed = int((_time.monotonic() - t0) * 1000)
    logger.info(f"[FOLLOW-UP] Done: {stats} ({elapsed}ms)")
    return stats


async def _generate_ai_followup_draft(session: AsyncSession, reply: ProcessedReply) -> str:
    """Generate an AI follow-up draft using the same pipeline as regular replies."""
    from app.services.reply_processor import generate_draft_reply
    from app.models.contact import Project
    from app.models.reply import ReplyPromptTemplateModel

    original_sent = reply.draft_reply or ""
    days_ago = (datetime.utcnow() - (reply.approved_at or reply.processed_at)).days

    followup_instruction = (
        f"\n\nКОНТЕКСТ ФОЛЛОУ-АП:\n"
        f"Это фоллоу-ап. Ты уже отправил лиду сообщение {days_ago} дней назад, но ответа не было.\n"
        f"Твоё предыдущее сообщение:\n---\n{original_sent}\n---\n"
        f"Напиши короткий фоллоу-ап. Не повторяй всё предложение заново — просто вежливо напомни и спроси, "
        f"было ли время ознакомиться. Пример формата:\n"
        f'"Здравствуйте, [имя]!\n\nПодскажите, пожалуйста, было время ознакомиться с нашим предложением?"\n'
        f"Можно адаптировать под контекст, но держи сообщение коротким (2-3 предложения максимум)."
    )

    # Look up project for sender identity + prompt template
    custom_reply_prompt = None
    sender_name = None
    sender_position = None
    sender_company = None

    if reply.campaign_name:
        try:
            project_result = await session.execute(
                select(Project).where(
                    and_(
                        Project.campaign_filters.isnot(None),
                        Project.deleted_at.is_(None),
                        sa_text(
                            "EXISTS (SELECT 1 FROM jsonb_array_elements_text(projects.campaign_filters) AS cf "
                            "WHERE LOWER(cf) = LOWER(:cname))"
                        ),
                    )
                ).params(cname=reply.campaign_name).limit(1)
            )
            project = project_result.scalar()
            if project:
                sender_name = project.sender_name
                sender_position = project.sender_position
                sender_company = project.sender_company
                if project.reply_prompt_template_id:
                    template_result = await session.execute(
                        select(ReplyPromptTemplateModel).where(
                            ReplyPromptTemplateModel.id == project.reply_prompt_template_id
                        )
                    )
                    template = template_result.scalar()
                    if template:
                        custom_reply_prompt = template.prompt_text
                # Load project knowledge
                try:
                    from app.models.project_knowledge import ProjectKnowledge
                    knowledge_result = await session.execute(
                        select(ProjectKnowledge).where(
                            ProjectKnowledge.project_id == project.id
                        )
                    )
                    knowledge_entries = knowledge_result.scalars().all()
                    if knowledge_entries:
                        from app.services.reply_processor import _format_knowledge_context
                        knowledge_context = _format_knowledge_context(knowledge_entries, category=reply.category or "other")
                        if custom_reply_prompt:
                            custom_reply_prompt += knowledge_context
                        else:
                            custom_reply_prompt = knowledge_context
                except Exception as ke:
                    logger.warning(f"[FOLLOW-UP] Knowledge loading failed (non-fatal): {ke}")
        except Exception as e:
            logger.warning(f"[FOLLOW-UP] Project lookup failed (non-fatal): {e}")

    # Append follow-up instruction
    if custom_reply_prompt:
        custom_reply_prompt += followup_instruction
    else:
        custom_reply_prompt = followup_instruction

    try:
        draft = await generate_draft_reply(
            subject=reply.email_subject or "",
            body=reply.email_body or reply.reply_text or "",
            category=reply.category or "other",
            first_name=reply.lead_first_name or "",
            last_name=reply.lead_last_name or "",
            company=reply.lead_company or "",
            custom_prompt=custom_reply_prompt,
            sender_name=sender_name,
            sender_position=sender_position,
            sender_company=sender_company,
        )
        return draft.get("body", "")
    except Exception as e:
        logger.warning(f"[FOLLOW-UP] AI draft failed for reply #{reply.id}, using template: {e}")
        # Fallback to simple template
        first_name = reply.lead_first_name or ""
        if not first_name and reply.lead_email:
            first_name = reply.lead_email.split("@")[0].split(".")[0].capitalize()
        return f"Здравствуйте, {first_name}!\n\nПодскажите, пожалуйста, было время ознакомиться с нашим предложением?"
