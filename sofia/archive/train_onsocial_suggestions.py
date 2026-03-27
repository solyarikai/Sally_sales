"""Seed reference examples and trigger learning for OnSocial (project_id=42).

Extracts warm/qualified conversations from OnSocial campaigns,
creates ReferenceExample entries with embeddings, and triggers
the learning cycle to update the reply prompt template.

Run on Hetzner:
  docker exec leadgen-backend python /app/sofia/train_onsocial_suggestions.py
"""
import asyncio
import json
import re
import logging
import sys
sys.path.insert(0, "/app")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

ONSOCIAL_PROJECT_ID = 42

# OnSocial campaign name patterns
ONSOCIAL_CAMPAIGN_PATTERNS = [
    "onsocial", "OnSocial", "c-OnSocial",
]

# Categories worth learning from
WARM_CATEGORIES = ["interested", "meeting_request", "question"]
ALL_LEARNABLE = ["interested", "meeting_request", "question", "not_interested", "wrong_person"]


def clean_html(text):
    if not text:
        return ""
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def is_onsocial_campaign(name):
    if not name:
        return False
    name_lower = name.lower()
    return any(p.lower() in name_lower for p in ONSOCIAL_CAMPAIGN_PATTERNS)


async def main():
    from app.db.database import async_session_maker
    from app.models.reply import ProcessedReply, ThreadMessage
    from app.models.learning import ReferenceExample
    from app.services.embedding_service import get_embedding, get_embeddings_batch
    from sqlalchemy import select, func, and_
    from sqlalchemy.orm import selectinload

    async with async_session_maker() as session:
        # ── Step 1: Find all OnSocial replies ──
        logger.info("Step 1: Finding OnSocial conversations...")

        stmt = (
            select(ProcessedReply)
            .options(selectinload(ProcessedReply.thread_messages))
            .order_by(ProcessedReply.received_at)
        )
        result = await session.execute(stmt)
        all_replies = result.scalars().all()

        # Filter to OnSocial campaigns
        onsocial_replies = [r for r in all_replies if is_onsocial_campaign(r.campaign_name)]
        logger.info(f"Found {len(onsocial_replies)} OnSocial replies out of {len(all_replies)} total")

        # Category distribution
        from collections import Counter
        cat_dist = Counter(r.category for r in onsocial_replies)
        logger.info(f"OnSocial category distribution: {dict(cat_dist)}")

        # ── Step 2: Check existing reference examples ──
        existing_count = await session.execute(
            select(func.count(ReferenceExample.id)).where(
                ReferenceExample.project_id == ONSOCIAL_PROJECT_ID
            )
        )
        existing = existing_count.scalar() or 0
        logger.info(f"Existing reference examples for OnSocial: {existing}")

        # Get existing processed_reply_ids to avoid duplicates
        existing_ids_result = await session.execute(
            select(ReferenceExample.processed_reply_id).where(
                ReferenceExample.project_id == ONSOCIAL_PROJECT_ID,
                ReferenceExample.processed_reply_id.isnot(None),
            )
        )
        existing_reply_ids = set(r[0] for r in existing_ids_result.fetchall())
        logger.info(f"Already imported reply IDs: {len(existing_reply_ids)}")

        # ── Step 3: Select best conversations for learning ──
        # Priority order:
        # 1. Approved replies (operator sent them — gold standard)
        # 2. Replied externally (operator handled in SmartLead UI)
        # 3. Warm leads with multi-turn threads
        # 4. All warm leads with meaningful reply text

        candidates = []

        for r in onsocial_replies:
            if r.id in existing_reply_ids:
                continue

            lead_text = clean_html(r.reply_text or r.email_body or "")
            if len(lead_text) < 15:
                continue

            # Find operator reply in thread
            operator_reply = None
            for msg in sorted(r.thread_messages, key=lambda m: m.position):
                if msg.direction == "outbound" and msg.position > 0:
                    operator_reply = clean_html(msg.body or "")
                    break

            # If no thread reply, use draft if it was approved
            if not operator_reply and r.approval_status in ("approved",) and r.draft_reply:
                operator_reply = clean_html(r.draft_reply)

            # Determine quality score
            quality = 3  # default
            if r.approval_status == "approved":
                quality = 5  # gold: operator approved AI draft
            elif r.approval_status == "replied_externally":
                quality = 4  # good: operator replied themselves
            elif r.category in WARM_CATEGORIES and operator_reply:
                quality = 4
            elif r.category in WARM_CATEGORIES:
                quality = 3

            # For warm leads, even without operator reply, the lead message is useful
            # (helps the system understand what kinds of messages come in)
            if r.category in ALL_LEARNABLE:
                candidates.append({
                    "reply": r,
                    "lead_text": lead_text,
                    "operator_reply": operator_reply or "",
                    "quality": quality,
                    "has_operator_reply": bool(operator_reply and len(operator_reply) > 20),
                })

        # Sort by quality (highest first), then by whether they have operator reply
        candidates.sort(key=lambda c: (-c["quality"], -int(c["has_operator_reply"])))
        logger.info(f"Candidates for import: {len(candidates)}")
        logger.info(f"  With operator reply: {sum(1 for c in candidates if c['has_operator_reply'])}")
        logger.info(f"  Quality 5 (approved): {sum(1 for c in candidates if c['quality'] == 5)}")
        logger.info(f"  Quality 4 (external/warm): {sum(1 for c in candidates if c['quality'] == 4)}")
        logger.info(f"  Quality 3 (learnable): {sum(1 for c in candidates if c['quality'] == 3)}")

        # ── Step 4: Create reference examples with embeddings ──
        logger.info("\nStep 4: Creating reference examples with embeddings...")

        # Process in batches
        batch_size = 50
        total_created = 0
        total_embedded = 0

        for i in range(0, len(candidates), batch_size):
            batch = candidates[i:i + batch_size]
            logger.info(f"Processing batch {i // batch_size + 1} ({len(batch)} candidates)...")

            # Batch embed lead messages
            texts_to_embed = [c["lead_text"][:2000] for c in batch]
            embeddings = await get_embeddings_batch(texts_to_embed)

            for j, cand in enumerate(batch):
                r = cand["reply"]
                embedding = embeddings[j] if embeddings and j < len(embeddings) else None

                # Build operator_reply — if we don't have one, use a placeholder
                # that tells the system "this type of message exists but no reply was crafted"
                op_reply = cand["operator_reply"]
                if not op_reply or len(op_reply) < 20:
                    # For messages without replies, still store the lead message
                    # so the system learns what patterns exist
                    if cand["quality"] < 4:
                        continue  # Skip low-quality without operator reply
                    op_reply = f"[No operator reply recorded — category: {r.category}]"

                ref = ReferenceExample(
                    project_id=ONSOCIAL_PROJECT_ID,
                    lead_message=cand["lead_text"][:5000],
                    operator_reply=op_reply[:5000],
                    lead_context={
                        "name": f"{r.lead_first_name or ''} {r.lead_last_name or ''}".strip(),
                        "company": r.lead_company or "",
                        "channel": r.channel or "email",
                        "category": r.category or "",
                        "campaign": r.campaign_name or "",
                    },
                    channel=r.channel or "email",
                    category=r.category or "other",
                    quality_score=cand["quality"],
                    source="learned",
                    processed_reply_id=r.id,
                    embedding=embedding,
                )
                session.add(ref)
                total_created += 1
                if embedding:
                    total_embedded += 1

            await session.flush()
            logger.info(f"  Batch done: {total_created} created, {total_embedded} embedded")

        await session.commit()
        logger.info(f"\nTotal reference examples created: {total_created}")
        logger.info(f"Total with embeddings: {total_embedded}")

        # ── Step 5: Verify final state ──
        final_count = await session.execute(
            select(func.count(ReferenceExample.id)).where(
                ReferenceExample.project_id == ONSOCIAL_PROJECT_ID
            )
        )
        final_embedded = await session.execute(
            select(func.count(ReferenceExample.id)).where(
                ReferenceExample.project_id == ONSOCIAL_PROJECT_ID,
                ReferenceExample.embedding.isnot(None),
            )
        )

        logger.info(f"\n=== FINAL STATE ===")
        logger.info(f"OnSocial reference examples total: {final_count.scalar()}")
        logger.info(f"OnSocial with embeddings: {final_embedded.scalar()}")

    # ── Step 6: Trigger learning cycle via API ──
    logger.info("\nStep 6: Triggering learning cycle via API...")
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"http://localhost:8000/api/projects/{ONSOCIAL_PROJECT_ID}/learning/analyze",
                json={"max_conversations": 200, "force_all": False},
                timeout=120,
            )
            if resp.status_code == 200:
                data = resp.json()
                logger.info(f"Learning cycle started: {data}")
            else:
                logger.warning(f"Learning API returned {resp.status_code}: {resp.text[:500]}")
    except Exception as e:
        logger.warning(f"Could not trigger learning cycle (non-fatal): {e}")
        logger.info("You can trigger it manually via the UI or API later.")

    logger.info("\nDone! OnSocial suggestion system has been trained.")


if __name__ == "__main__":
    asyncio.run(main())
