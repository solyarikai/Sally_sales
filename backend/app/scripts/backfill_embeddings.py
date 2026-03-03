"""
Backfill script: populate reference_examples from thread_messages + ProjectKnowledge golden examples.

Usage:
    python -m app.scripts.backfill_embeddings [--project-id 40] [--dry-run] [--rebuild]

    --rebuild: Delete all existing reference_examples for the project and re-create from scratch.

Runs inside the FastAPI app context for DB access.

Key design decisions:
  - SKIP position 0 outbound messages (initial campaign outreach, not replies)
  - For each outbound message, pair it with the PRECEDING inbound message as lead_message
    (this captures the actual "lead said X → operator replied Y" pattern)
  - Embed the LEAD MESSAGE (not operator reply) — so semantic search finds similar
    incoming situations and returns corresponding operator responses
"""
import asyncio
import logging
import re
import sys
from datetime import datetime

from sqlalchemy import select, and_, or_, func as sa_func, delete
from sqlalchemy.ext.asyncio import AsyncSession

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_html_re_br = re.compile(r'<br\s*/?>', re.IGNORECASE)
_html_re_div = re.compile(r'</div>', re.IGNORECASE)
_html_re_li_close = re.compile(r'</li>', re.IGNORECASE)
_html_re_li_open = re.compile(r'<li[^>]*>', re.IGNORECASE)
_html_re_tags = re.compile(r'<[^>]+>')


def _strip_html(text: str) -> str:
    if not text:
        return ""
    import html
    t = _html_re_br.sub('\n', text)
    t = _html_re_div.sub('\n', t)
    t = _html_re_li_close.sub('\n', t)
    t = _html_re_li_open.sub('- ', t)
    t = _html_re_tags.sub('', t)
    t = html.unescape(t)
    t = re.sub(r'\n{3,}', '\n\n', t)
    t = re.sub(r'  +', ' ', t)
    return t.strip()


async def backfill_project(session: AsyncSession, project_id: int, dry_run: bool = False, rebuild: bool = False):
    """Backfill reference_examples for a single project."""
    from app.models.contact import Project
    from app.models.reply import ProcessedReply, ThreadMessage
    from app.models.learning import ReferenceExample
    from app.models.project_knowledge import ProjectKnowledge
    from app.services.embedding_service import get_embeddings_batch

    # Get project
    proj_result = await session.execute(
        select(Project).where(Project.id == project_id, Project.deleted_at.is_(None))
    )
    project = proj_result.scalar_one_or_none()
    if not project:
        logger.error(f"Project {project_id} not found")
        return

    logger.info(f"=== Backfilling project: {project.name} (id={project_id}) ===")

    # If rebuild, delete all existing reference examples
    if rebuild and not dry_run:
        del_result = await session.execute(
            delete(ReferenceExample).where(ReferenceExample.project_id == project_id)
        )
        logger.info(f"REBUILD: Deleted {del_result.rowcount} existing reference examples")

    # Build campaign filter
    campaign_parts = []
    campaign_names = [c.lower() for c in (project.campaign_filters or []) if isinstance(c, str)]
    if campaign_names:
        campaign_parts.append(sa_func.lower(ProcessedReply.campaign_name).in_(campaign_names))
    pname = (project.name or "").lower()
    if pname and len(pname) > 2:
        campaign_parts.append(sa_func.lower(ProcessedReply.campaign_name).like(f"{pname}%"))

    if not campaign_parts:
        logger.warning(f"No campaign filters for project {project_id}, skipping thread_messages")
    else:
        campaign_condition = or_(*campaign_parts)

        # Fetch ALL thread_messages for qualifying replies (both inbound and outbound)
        # We need both to pair outbound responses with their preceding inbound messages
        QUALIFIED_CATS = {"interested", "meeting_request", "question"}
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
            .limit(2000)
        )
        result = await session.execute(query)
        all_messages = result.all()

        logger.info(f"Found {len(all_messages)} total thread_messages")

        # Group by reply_id (thread)
        threads = {}
        for msg in all_messages:
            reply_id = msg.reply_id
            if reply_id not in threads:
                threads[reply_id] = []
            threads[reply_id].append(msg)

        # Build reference examples: only include outbound messages that appear AFTER
        # the first inbound message in the thread (these are genuine operator responses,
        # not automated campaign follow-ups)
        examples_to_create = []
        for reply_id, messages in threads.items():
            # Sort by position within thread
            messages.sort(key=lambda m: m.position)

            # Find the first inbound message position
            first_inbound_pos = None
            for msg in messages:
                if msg.direction == "inbound":
                    first_inbound_pos = msg.position
                    break

            if first_inbound_pos is None:
                continue  # No inbound messages in thread — skip entirely

            for i, msg in enumerate(messages):
                if msg.direction != "outbound":
                    continue
                if msg.position <= first_inbound_pos:
                    continue  # Skip all outbound before first lead reply (campaign sequence)

                clean_body = _strip_html(msg.body)
                if len(clean_body) < 400:
                    continue

                # Find the preceding inbound message (the one the operator is responding to)
                preceding_inbound = None
                for j in range(i - 1, -1, -1):
                    if messages[j].direction == "inbound":
                        preceding_inbound = messages[j]
                        break

                if not preceding_inbound:
                    continue  # No preceding inbound — shouldn't happen but skip

                lead_msg = _strip_html(preceding_inbound.body or "")

                # Truncate lead message for storage (but keep enough for embedding)
                lead_msg_for_embed = lead_msg[:2000] if lead_msg else ""
                lead_msg_for_storage = lead_msg[:1000] if lead_msg else "(no lead message)"

                examples_to_create.append({
                    "tm_id": msg.id,
                    "pr_id": msg.pr_id,
                    "lead_message": lead_msg_for_storage,
                    "lead_msg_for_embed": lead_msg_for_embed,
                    "operator_reply": clean_body,
                    "lead_first_name": msg.lead_first_name,
                    "lead_company": msg.lead_company,
                    "channel": msg.channel,
                    "category": msg.category,
                })

        logger.info(f"Found {len(examples_to_create)} outbound follow-up messages (position > 0, >400 chars)")

        # Deduplicate by operator reply prefix
        seen_prefixes = set()
        unique_examples = []
        for ex in examples_to_create:
            prefix = ex["operator_reply"][:150].lower()
            if prefix in seen_prefixes:
                continue
            seen_prefixes.add(prefix)
            unique_examples.append(ex)

        logger.info(f"After dedup: {len(unique_examples)} unique examples")

        # Check existing to avoid re-inserting
        if not rebuild:
            existing_tm_ids = set()
            if unique_examples:
                existing_result = await session.execute(
                    select(ReferenceExample.thread_message_id).where(
                        ReferenceExample.project_id == project_id,
                        ReferenceExample.thread_message_id.isnot(None),
                    )
                )
                existing_tm_ids = {r[0] for r in existing_result.all()}
            unique_examples = [ex for ex in unique_examples if ex["tm_id"] not in existing_tm_ids]
            logger.info(f"New examples to embed: {len(unique_examples)}")

        if unique_examples and not dry_run:
            # Embed LEAD MESSAGES (not operator replies!)
            # This way semantic search finds similar incoming leads and returns operator responses
            texts_to_embed = []
            for ex in unique_examples:
                embed_text = ex["lead_msg_for_embed"]
                if not embed_text or len(embed_text) < 20:
                    # Fallback: if lead message is too short, use operator reply
                    embed_text = ex["operator_reply"][:2000]
                texts_to_embed.append(embed_text)

            logger.info(f"Embedding {len(texts_to_embed)} lead messages...")
            embeddings = await get_embeddings_batch(texts_to_embed)

            # Create ReferenceExample rows
            for idx, ex in enumerate(unique_examples):
                ref = ReferenceExample(
                    project_id=project_id,
                    lead_message=ex["lead_message"],
                    operator_reply=ex["operator_reply"],
                    lead_context={
                        "name": ex["lead_first_name"],
                        "company": ex["lead_company"],
                        "channel": ex["channel"],
                    },
                    channel=ex["channel"],
                    category=ex["category"],
                    quality_score=3,
                    source="learned",
                    embedding=embeddings[idx] if idx < len(embeddings) else None,
                    thread_message_id=ex["tm_id"],
                    processed_reply_id=ex["pr_id"],
                )
                session.add(ref)

            await session.flush()
            logger.info(f"Created {len(unique_examples)} reference examples from thread_messages")

    # --- Backfill golden examples from ProjectKnowledge ---
    pk_result = await session.execute(
        select(ProjectKnowledge).where(
            ProjectKnowledge.project_id == project_id,
            ProjectKnowledge.category == "examples",
        )
    )
    golden = pk_result.scalars().all()
    logger.info(f"Found {len(golden)} golden examples in ProjectKnowledge")

    if golden and not dry_run:
        # Check existing
        existing_feedback = await session.execute(
            select(ReferenceExample.id).where(
                ReferenceExample.project_id == project_id,
                ReferenceExample.source == "feedback",
            )
        )
        existing_count = len(existing_feedback.all())
        if existing_count > 0 and not rebuild:
            logger.info(f"Skipping golden examples — {existing_count} already exist with source=feedback")
        else:
            # For golden examples, embed the example text itself (it represents the ideal reply
            # for a specific category, so matching by category content is correct)
            texts = [str(g.value)[:8000] for g in golden]
            embeddings = await get_embeddings_batch(texts)
            for idx, g in enumerate(golden):
                ref = ReferenceExample(
                    project_id=project_id,
                    lead_message=f"[Golden example: {g.key}]",
                    operator_reply=str(g.value),
                    lead_context={"source_key": g.key},
                    category=g.key.split("_")[0] if "_" in g.key else "general",
                    quality_score=5,
                    source="feedback",
                    embedding=embeddings[idx],
                )
                session.add(ref)
            await session.flush()
            logger.info(f"Created {len(golden)} reference examples from golden examples")

    if not dry_run:
        await session.commit()
        logger.info(f"Committed all changes for project {project_id}")
    else:
        logger.info(f"DRY RUN — no changes committed")


async def main():
    from app.db.database import async_session_maker
    from app.models.contact import Project

    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    rebuild = "--rebuild" in args
    project_id = None
    for i, arg in enumerate(args):
        if arg == "--project-id" and i + 1 < len(args):
            project_id = int(args[i + 1])

    async with async_session_maker() as session:
        if project_id:
            await backfill_project(session, project_id, dry_run, rebuild)
        else:
            # All active projects
            result = await session.execute(
                select(Project.id, Project.name).where(Project.deleted_at.is_(None))
            )
            projects = result.all()
            logger.info(f"Backfilling {len(projects)} projects")
            for pid, pname in projects:
                try:
                    await backfill_project(session, pid, dry_run, rebuild)
                except Exception as e:
                    logger.error(f"Failed project {pid} ({pname}): {e}")


if __name__ == "__main__":
    asyncio.run(main())
