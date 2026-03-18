"""
Add ALL unique operator replies as golden reference examples.

Extracts operator's actual sends from thread_messages, strips HTML,
deduplicates against existing reference_examples, and inserts new ones
with embeddings as source='feedback', quality_score=5.

Usage:
    python -m app.scripts.add_operator_golden --project-id 40 [--dry-run]
"""
import asyncio
import logging
import re
import sys
import html as html_module

from sqlalchemy import select, and_, or_, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_html_re_br = re.compile(r'<br\s*/?>', re.IGNORECASE)
_html_re_div = re.compile(r'</div>', re.IGNORECASE)
_html_re_p = re.compile(r'</p>', re.IGNORECASE)
_html_re_li_close = re.compile(r'</li>', re.IGNORECASE)
_html_re_li_open = re.compile(r'<li[^>]*>', re.IGNORECASE)
_html_re_tags = re.compile(r'<[^>]+>')


def strip_html(text: str) -> str:
    if not text:
        return ""
    t = _html_re_br.sub('\n', text)
    t = _html_re_div.sub('\n', t)
    t = _html_re_p.sub('\n', t)
    t = _html_re_li_close.sub('\n', t)
    t = _html_re_li_open.sub('- ', t)
    t = _html_re_tags.sub('', t)
    t = html_module.unescape(t)
    t = re.sub(r'\n{3,}', '\n\n', t)
    t = re.sub(r'  +', ' ', t)
    return t.strip()


async def add_golden_examples(session: AsyncSession, project_id: int, dry_run: bool = False):
    from app.models.contact import Project
    from app.models.reply import ProcessedReply, ThreadMessage
    from app.models.learning import ReferenceExample
    from app.services.embedding_service import get_embeddings_batch

    # Get project
    proj_result = await session.execute(
        select(Project).where(Project.id == project_id, Project.deleted_at.is_(None))
    )
    project = proj_result.scalar_one_or_none()
    if not project:
        logger.error(f"Project {project_id} not found")
        return

    logger.info(f"=== Adding golden examples for: {project.name} (id={project_id}) ===")

    # Get existing golden example processed_reply_ids to avoid duplicates
    existing_result = await session.execute(
        select(ReferenceExample.processed_reply_id).where(
            ReferenceExample.project_id == project_id,
            ReferenceExample.source == "feedback",
            ReferenceExample.processed_reply_id.isnot(None),
        )
    )
    existing_pr_ids = {r[0] for r in existing_result.all()}
    logger.info(f"Existing golden examples: {len(existing_pr_ids)} (will skip these)")

    # Build campaign filter
    campaign_parts = []
    campaign_names = [c.lower() for c in (project.campaign_filters or []) if isinstance(c, str)]
    if campaign_names:
        campaign_parts.append(sa_func.lower(ProcessedReply.campaign_name).in_(campaign_names))
    pname = (project.name or "").lower()
    if pname and len(pname) > 2:
        campaign_parts.append(sa_func.lower(ProcessedReply.campaign_name).like(f"{pname}%"))

    if not campaign_parts:
        logger.error("No campaign filters for project")
        return

    campaign_condition = or_(*campaign_parts)
    QUALIFIED_CATS = {"interested", "meeting_request", "question"}

    # Get ALL thread messages for qualifying replies
    query = (
        select(
            ThreadMessage.id,
            ThreadMessage.body,
            ThreadMessage.direction,
            ThreadMessage.position,
            ThreadMessage.reply_id,
            ProcessedReply.id.label("pr_id"),
            ProcessedReply.email_body,
            ProcessedReply.lead_first_name,
            ProcessedReply.lead_company,
            ProcessedReply.category,
            ProcessedReply.channel,
        )
        .join(ProcessedReply, ThreadMessage.reply_id == ProcessedReply.id)
        .where(
            campaign_condition,
            ProcessedReply.category.in_(list(QUALIFIED_CATS)),
        )
        .order_by(ThreadMessage.reply_id, ThreadMessage.position)
        .limit(5000)
    )
    result = await session.execute(query)
    all_messages = result.all()
    logger.info(f"Found {len(all_messages)} thread messages")

    # Group by reply_id
    threads = {}
    for msg in all_messages:
        reply_id = msg.reply_id
        if reply_id not in threads:
            threads[reply_id] = []
        threads[reply_id].append(msg)

    # Extract first operator reply after first inbound per thread
    examples_to_add = []
    for reply_id, messages in threads.items():
        if reply_id in existing_pr_ids:
            continue  # Already a golden example

        messages.sort(key=lambda m: m.position)

        # Find first inbound
        first_inbound = None
        for msg in messages:
            if msg.direction == "inbound":
                first_inbound = msg
                break
        if first_inbound is None:
            continue

        # Find first outbound after first inbound (operator's actual response)
        operator_reply_msg = None
        for msg in messages:
            if msg.direction == "outbound" and msg.position > first_inbound.position:
                operator_reply_msg = msg
                break
        if operator_reply_msg is None:
            continue

        # Strip HTML
        lead_msg = strip_html(first_inbound.body or first_inbound.email_body or "")
        operator_reply = strip_html(operator_reply_msg.body or "")

        # Quality filters
        if len(operator_reply) < 50:
            continue  # Too short, probably not a real reply
        if len(lead_msg) < 10:
            lead_msg = "(short reply)"

        # Truncate lead message for storage
        lead_msg = lead_msg[:2000]

        examples_to_add.append({
            "pr_id": reply_id,
            "tm_id": operator_reply_msg.id,
            "lead_message": lead_msg,
            "operator_reply": operator_reply,
            "lead_first_name": operator_reply_msg.lead_first_name or "",
            "lead_company": operator_reply_msg.lead_company or "",
            "channel": operator_reply_msg.channel or "email",
            "category": operator_reply_msg.category or "question",
        })

    logger.info(f"Found {len(examples_to_add)} new operator replies to add as golden")

    # Deduplicate by operator reply prefix (catch near-identical sends)
    seen_prefixes = set()
    unique_examples = []
    for ex in examples_to_add:
        prefix = ex["operator_reply"][:200].lower().strip()
        if prefix in seen_prefixes:
            continue
        seen_prefixes.add(prefix)
        unique_examples.append(ex)

    logger.info(f"After dedup: {len(unique_examples)} unique examples")

    if not unique_examples:
        logger.info("Nothing to add")
        return

    if dry_run:
        for ex in unique_examples:
            logger.info(
                f"  [DRY] pr_id={ex['pr_id']} channel={ex['channel']} cat={ex['category']} "
                f"name={ex['lead_first_name']} co={ex['lead_company']} "
                f"lead_len={len(ex['lead_message'])} reply_len={len(ex['operator_reply'])}"
            )
        logger.info(f"DRY RUN — would add {len(unique_examples)} golden examples")
        return

    # Embed lead messages
    texts_to_embed = []
    for ex in unique_examples:
        text = ex["lead_message"][:2000]
        if len(text) < 20:
            text = ex["operator_reply"][:2000]
        texts_to_embed.append(text)

    logger.info(f"Embedding {len(texts_to_embed)} lead messages...")
    embeddings = await get_embeddings_batch(texts_to_embed)
    logger.info(f"Got {len(embeddings)} embeddings")

    # Insert as golden examples (source=feedback, quality=5)
    created = 0
    for idx, ex in enumerate(unique_examples):
        ref = ReferenceExample(
            project_id=project_id,
            lead_message=ex["lead_message"],
            operator_reply=ex["operator_reply"],
            lead_context={
                "name": ex["lead_first_name"],
                "company": ex["lead_company"],
                "channel": ex["channel"],
                "category": ex["category"],
            },
            channel=ex["channel"],
            category=ex["category"],
            quality_score=5,
            source="feedback",
            embedding=embeddings[idx] if idx < len(embeddings) else None,
            thread_message_id=ex["tm_id"],
            processed_reply_id=ex["pr_id"],
        )
        session.add(ref)
        created += 1

    await session.flush()
    await session.commit()
    logger.info(f"Created {created} golden reference examples")

    # Final stats
    total_result = await session.execute(
        select(sa_func.count(ReferenceExample.id)).where(
            ReferenceExample.project_id == project_id,
        )
    )
    total = total_result.scalar()
    golden_result = await session.execute(
        select(sa_func.count(ReferenceExample.id)).where(
            ReferenceExample.project_id == project_id,
            ReferenceExample.source == "feedback",
        )
    )
    golden = golden_result.scalar()
    logger.info(f"Final stats: {golden} golden + {total - golden} learned = {total} total examples")


async def main():
    from app.db.database import async_session_maker

    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    project_id = None
    for i, arg in enumerate(args):
        if arg == "--project-id" and i + 1 < len(args):
            project_id = int(args[i + 1])

    if not project_id:
        logger.error("Usage: python -m app.scripts.add_operator_golden --project-id 40 [--dry-run]")
        return

    async with async_session_maker() as session:
        await add_golden_examples(session, project_id, dry_run)


if __name__ == "__main__":
    asyncio.run(main())
