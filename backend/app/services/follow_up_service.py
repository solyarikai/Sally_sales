"""Automated follow-up draft generation.

Creates follow-up drafts for leads who haven't responded after the operator sent a reply.
The follow-up appears in the operator queue for approval — never auto-sends.

Logic:
  1. Find approved replies older than 3 days
  2. Skip if lead sent a newer inbound message
  3. Skip if a follow-up was already created for this reply
  4. Generate a short follow-up draft
  5. Create a new ProcessedReply (pending) linked to the original
"""
import hashlib
import logging
from datetime import datetime, timedelta

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reply import ProcessedReply

logger = logging.getLogger(__name__)

# Only create 1 follow-up per reply (no infinite chains)
MAX_FOLLOW_UPS = 1

# Days after operator sends before creating follow-up
FOLLOW_UP_DELAY_DAYS = 3

# Simple follow-up template — operator can edit before sending
FOLLOW_UP_TEMPLATE = "Здравствуйте, {first_name}!\n\nПодскажите, пожалуйста, было время ознакомиться с нашим предложением?"


async def generate_follow_up_drafts(session: AsyncSession) -> dict:
    """Find approved replies needing follow-up and create draft records.

    Returns stats dict with counts.
    """
    cutoff = datetime.utcnow() - timedelta(days=FOLLOW_UP_DELAY_DAYS)
    stats = {"checked": 0, "created": 0, "skipped_inbound": 0, "skipped_existing": 0, "errors": 0}

    # Find approved replies older than 3 days that might need follow-up.
    # Only consider replies from projects that have follow-up enabled
    # (for now: any project with a reply_prompt_template — i.e., active reply automation).
    # Get approved replies older than cutoff
    candidates = await session.execute(
        select(ProcessedReply).where(
            and_(
                ProcessedReply.approval_status == "approved",
                ProcessedReply.approved_at.isnot(None),
                ProcessedReply.approved_at < cutoff,
                ProcessedReply.follow_up_number.is_(None),  # not itself a follow-up
                ProcessedReply.parent_reply_id.is_(None),   # not itself a follow-up
                ProcessedReply.category.in_(["meeting_request", "interested", "question"]),
            )
        ).order_by(ProcessedReply.approved_at.asc()).limit(50)
    )
    replies = candidates.scalars().all()
    stats["checked"] = len(replies)

    for reply in replies:
        try:
            # Check if follow-up already exists for this reply
            existing_fu = await session.execute(
                select(ProcessedReply.id).where(
                    ProcessedReply.parent_reply_id == reply.id
                ).limit(1)
            )
            if existing_fu.scalar():
                stats["skipped_existing"] += 1
                continue

            # Check if lead sent a newer inbound message (any ProcessedReply from same lead after approved_at)
            newer_inbound = await session.execute(
                select(ProcessedReply.id).where(
                    and_(
                        ProcessedReply.lead_email == reply.lead_email,
                        ProcessedReply.received_at > reply.approved_at,
                        ProcessedReply.parent_reply_id.is_(None),  # real inbound, not a follow-up
                    )
                ).limit(1)
            )
            if newer_inbound.scalar():
                stats["skipped_inbound"] += 1
                continue

            # Generate follow-up draft
            first_name = reply.lead_first_name or ""
            if not first_name and reply.lead_email:
                # Extract name from email as fallback
                first_name = reply.lead_email.split("@")[0].split(".")[0].capitalize()

            draft_text = FOLLOW_UP_TEMPLATE.format(first_name=first_name)

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
                email_subject=reply.email_subject,  # keep original subject for threading
                email_body=f"(Follow-up — no response after {FOLLOW_UP_DELAY_DAYS} days)",
                category=reply.category,
                category_confidence="high",
                classification_reasoning=f"Auto-generated follow-up for reply #{reply.id}",
                draft_reply=draft_text,
                draft_subject=reply.draft_subject,  # keep original subject
                draft_generated_at=datetime.utcnow(),
                processed_at=datetime.utcnow(),
                received_at=reply.approved_at,  # for ordering — show when original was sent
                approval_status=None,  # pending — appears in operator queue
                inbox_link=reply.inbox_link,
                raw_webhook_data=reply.raw_webhook_data,  # needed for send (lead_uuid, sender_profile_uuid)
                smartlead_lead_id=reply.smartlead_lead_id,
                message_hash=fu_hash,
                parent_reply_id=reply.id,
                follow_up_number=1,
            )
            session.add(follow_up)
            await session.flush()
            stats["created"] += 1

            logger.info(
                f"[FOLLOW-UP] Created follow-up #{follow_up.id} for reply #{reply.id} "
                f"({reply.lead_email}, campaign={reply.campaign_name})"
            )

        except Exception as e:
            logger.error(f"[FOLLOW-UP] Error processing reply #{reply.id}: {e}")
            stats["errors"] += 1

    if stats["created"] > 0:
        await session.commit()
        logger.info(f"[FOLLOW-UP] Created {stats['created']} follow-up drafts")

    return stats
