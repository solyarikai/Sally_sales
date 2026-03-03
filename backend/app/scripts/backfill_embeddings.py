"""
Backfill script: populate reference_examples from thread_messages + ProjectKnowledge golden examples.

Usage:
    python -m app.scripts.backfill_embeddings [--project-id 40] [--dry-run]

Runs inside the FastAPI app context for DB access.
"""
import asyncio
import logging
import re
import sys
from datetime import datetime

from sqlalchemy import select, and_, or_, func as sa_func
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


async def backfill_project(session: AsyncSession, project_id: int, dry_run: bool = False):
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

        # Fetch outbound thread_messages >300 chars for qualified categories
        QUALIFIED_CATS = {"interested", "meeting_request", "question"}
        query = (
            select(
                ThreadMessage.id,
                ThreadMessage.body,
                ProcessedReply.id.label("pr_id"),
                ProcessedReply.email_body,
                ProcessedReply.lead_first_name,
                ProcessedReply.lead_company,
                ProcessedReply.category,
                ProcessedReply.channel,
            )
            .join(ProcessedReply, ThreadMessage.reply_id == ProcessedReply.id)
            .where(
                ThreadMessage.direction == "outbound",
                sa_func.length(ThreadMessage.body) > 300,
                campaign_condition,
                ProcessedReply.category.in_(list(QUALIFIED_CATS)),
            )
            .order_by(ThreadMessage.id.desc())
            .limit(500)
        )
        result = await session.execute(query)
        rows = result.all()

        logger.info(f"Found {len(rows)} outbound thread_messages")

        # Deduplicate
        seen_prefixes = set()
        unique_rows = []
        for r in rows:
            clean_body = _strip_html(r.body)
            if len(clean_body) < 400:
                continue
            prefix = clean_body[:150].lower()
            if prefix in seen_prefixes:
                continue
            seen_prefixes.add(prefix)
            unique_rows.append((r, clean_body))

        logger.info(f"After dedup: {len(unique_rows)} unique examples")

        # Check existing to avoid re-inserting
        existing_tm_ids = set()
        if unique_rows:
            existing_result = await session.execute(
                select(ReferenceExample.thread_message_id).where(
                    ReferenceExample.project_id == project_id,
                    ReferenceExample.thread_message_id.isnot(None),
                )
            )
            existing_tm_ids = {r[0] for r in existing_result.all()}

        # Prepare texts for embedding
        new_rows = [(r, body) for r, body in unique_rows if r.id not in existing_tm_ids]
        logger.info(f"New examples to embed: {len(new_rows)} (skipping {len(unique_rows) - len(new_rows)} existing)")

        if new_rows and not dry_run:
            # Embed all operator replies in batch
            texts_to_embed = [body for _, body in new_rows]
            logger.info(f"Embedding {len(texts_to_embed)} texts...")
            embeddings = await get_embeddings_batch(texts_to_embed)

            # Create ReferenceExample rows
            for idx, (r, clean_body) in enumerate(new_rows):
                lead_msg = _strip_html(r.email_body or "")[:500]
                ref = ReferenceExample(
                    project_id=project_id,
                    lead_message=lead_msg or "(no lead message)",
                    operator_reply=clean_body,
                    lead_context={
                        "name": r.lead_first_name,
                        "company": r.lead_company,
                        "channel": r.channel,
                    },
                    channel=r.channel,
                    category=r.category,
                    quality_score=3,
                    source="learned",
                    embedding=embeddings[idx],
                    thread_message_id=r.id,
                    processed_reply_id=r.pr_id,
                )
                session.add(ref)

            await session.flush()
            logger.info(f"Created {len(new_rows)} reference examples from thread_messages")

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
        if existing_count > 0:
            logger.info(f"Skipping golden examples — {existing_count} already exist with source=feedback")
        else:
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
    project_id = None
    for i, arg in enumerate(args):
        if arg == "--project-id" and i + 1 < len(args):
            project_id = int(args[i + 1])

    async with async_session_maker() as session:
        if project_id:
            await backfill_project(session, project_id, dry_run)
        else:
            # All active projects
            result = await session.execute(
                select(Project.id, Project.name).where(Project.deleted_at.is_(None))
            )
            projects = result.all()
            logger.info(f"Backfilling {len(projects)} projects")
            for pid, pname in projects:
                try:
                    await backfill_project(session, pid, dry_run)
                except Exception as e:
                    logger.error(f"Failed project {pid} ({pname}): {e}")


if __name__ == "__main__":
    asyncio.run(main())
