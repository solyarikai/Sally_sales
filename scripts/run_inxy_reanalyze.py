"""
Inxy re-analysis — Re-score existing non-target results that mention gaming keywords
using updated, more permissive target_segments criteria.

Previous GPT analysis was too strict:
- Rejected single-game currency sellers (FIFA coins, WoW gold)
- Rejected global platforms for not serving "low-risk countries" specifically
- Required crypto integration (but targets are POTENTIAL crypto adopters)
"""
import asyncio
import json
import logging
import sys
import os

sys.path.insert(0, "/app")
os.chdir("/app")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("inxy_reanalyze")

PROJECT_ID = 48
BATCH_SIZE = 20


async def main():
    from app.db import async_session_maker
    from app.models.domain import SearchResult
    from app.models.contact import Project
    from app.core.config import settings
    from sqlalchemy import select, func, or_, text
    import httpx

    async with async_session_maker() as session:
        # Load updated project
        result = await session.execute(select(Project).where(Project.id == PROJECT_ID))
        project = result.scalar_one()
        target_segments = project.target_segments

        # Find gaming-related non-targets to re-analyze
        candidates = await session.execute(
            select(SearchResult).where(
                SearchResult.project_id == PROJECT_ID,
                SearchResult.is_target == False,
                SearchResult.reasoning.isnot(None),
                or_(
                    SearchResult.reasoning.ilike("%game item%"),
                    SearchResult.reasoning.ilike("%in-game%"),
                    SearchResult.reasoning.ilike("%virtual item%"),
                    SearchResult.reasoning.ilike("%gaming good%"),
                    SearchResult.reasoning.ilike("%sells game%"),
                    SearchResult.reasoning.ilike("%game currency%"),
                    SearchResult.reasoning.ilike("%skin%"),
                    SearchResult.reasoning.ilike("%case opening%"),
                    SearchResult.reasoning.ilike("%loot box%"),
                    SearchResult.reasoning.ilike("%marketplace for%"),
                    SearchResult.reasoning.ilike("%trading platform%"),
                    SearchResult.reasoning.ilike("%game key%"),
                    SearchResult.reasoning.ilike("%game account%"),
                    SearchResult.reasoning.ilike("%digital good%"),
                    SearchResult.reasoning.ilike("%boosting%"),
                    SearchResult.reasoning.ilike("%game coin%"),
                    SearchResult.reasoning.ilike("%gold sell%"),
                    SearchResult.reasoning.ilike("%top-up%"),
                    SearchResult.reasoning.ilike("%top up%"),
                    SearchResult.reasoning.ilike("%gift card%"),
                    SearchResult.reasoning.ilike("%gambling%"),
                    SearchResult.reasoning.ilike("%casino%"),
                    SearchResult.reasoning.ilike("%betting%"),
                    SearchResult.domain.ilike("%skin%"),
                    SearchResult.domain.ilike("%game%"),
                    SearchResult.domain.ilike("%loot%"),
                    SearchResult.domain.ilike("%.gg"),
                    SearchResult.domain.ilike("%mmo%"),
                    SearchResult.domain.ilike("%cs%"),
                    SearchResult.domain.ilike("%trade%"),
                    SearchResult.domain.ilike("%rust%"),
                    SearchResult.domain.ilike("%dota%"),
                ),
            ).order_by(SearchResult.confidence.desc())
        )
        all_candidates = candidates.scalars().all()

        # Filter out already reclassified
        to_reanalyze = [c for c in all_candidates if "RECLASSIFIED" not in (c.reasoning or "")]
        logger.info(f"Found {len(to_reanalyze)} gaming-related non-targets to re-analyze")

        tc = await session.execute(
            select(func.count()).select_from(SearchResult).where(
                SearchResult.project_id == PROJECT_ID, SearchResult.is_target == True
            )
        )
        before = tc.scalar() or 0
        logger.info(f"Targets before: {before}")

        reclassified = 0
        client = httpx.AsyncClient(timeout=30)

        for i in range(0, len(to_reanalyze), BATCH_SIZE):
            batch = to_reanalyze[i:i + BATCH_SIZE]
            batch_num = i // BATCH_SIZE + 1
            total_batches = (len(to_reanalyze) + BATCH_SIZE - 1) // BATCH_SIZE

            # Build GPT prompt for re-analysis
            items = []
            for sr in batch:
                items.append({
                    "domain": sr.domain,
                    "old_reasoning": sr.reasoning[:300] if sr.reasoning else "",
                    "old_confidence": sr.confidence,
                })

            prompt = f"""You are re-analyzing companies for Inxy, a crypto payment gateway targeting gaming digital goods sellers.

TARGET CRITERIA (UPDATED — be MORE permissive):
{target_segments}

IMPORTANT RE-ANALYSIS RULES:
- If a company sells ANY digital gaming goods (skins, items, currency, accounts, keys, gift cards, top-ups, boosting) — it IS a target
- Single-game currency sellers ARE targets (e.g., FIFA coins, WoW gold, Roblox Robux)
- Game boosting services ARE targets (they accept payments)
- Geography of the company does NOT matter — only whether they sell gaming goods
- Russian-language sites that sell gaming goods ARE targets (they still might add crypto payments)
- Do NOT require the company to already accept crypto — the whole point is they are POTENTIAL adopters
- Aggregators/comparison sites for gaming goods ARE targets (they might integrate payments)
- Game account sellers ARE targets

For each company below, re-evaluate whether it should be a TARGET.
Return JSON array: [{{"domain": "...", "is_target": true/false, "confidence": 0.0-1.0, "reason": "brief reason"}}]

Companies to re-analyze:
{json.dumps(items, indent=2)}"""

            try:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
                    json={
                        "model": "gpt-4o-mini",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.1,
                        "response_format": {"type": "json_object"},
                    },
                    timeout=60,
                )
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                results = json.loads(content)

                # Handle both array and object with array
                if isinstance(results, dict):
                    results = results.get("results", results.get("companies", []))

                batch_reclassified = 0
                for r in results:
                    if r.get("is_target"):
                        domain = r["domain"]
                        for sr in batch:
                            if sr.domain == domain:
                                sr.is_target = True
                                sr.confidence = r.get("confidence", 0.6)
                                sr.reasoning = (sr.reasoning or "") + f" [RE-ANALYZED: {r.get('reason', 'gaming goods seller')}]"
                                batch_reclassified += 1
                                reclassified += 1
                                break

                if batch_reclassified > 0:
                    await session.commit()

                logger.info(f"Batch {batch_num}/{total_batches}: {batch_reclassified}/{len(batch)} reclassified as targets")

            except Exception as e:
                logger.error(f"Batch {batch_num} error: {e}")

        await session.commit()

        tc = await session.execute(
            select(func.count()).select_from(SearchResult).where(
                SearchResult.project_id == PROJECT_ID, SearchResult.is_target == True
            )
        )
        after = tc.scalar() or 0

        logger.info(f"\n{'='*60}")
        logger.info(f"RE-ANALYSIS COMPLETE")
        logger.info(f"Candidates reviewed: {len(to_reanalyze)}")
        logger.info(f"Reclassified as targets: {reclassified}")
        logger.info(f"Targets before: {before}")
        logger.info(f"Targets after:  {after}")
        logger.info(f"{'='*60}")

        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
