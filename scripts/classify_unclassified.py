"""
Classify all search_results with matched_segment IS NULL using GPT-4o-mini.
Uses existing company_info + reasoning to assign segment — no re-scraping needed.
Batches 10 results per GPT call for efficiency.

Cost estimate: ~23k results / 10 per batch = ~2,400 calls
~400 tokens per call = ~1M tokens total ≈ $0.15-0.30

Usage: docker exec leadgen-backend python scripts/classify_unclassified.py
"""
import asyncio
import json
import logging
import os
import sys
import time

import httpx
import asyncpg

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql+asyncpg://leadgen:leadgen_secret@leadgen-postgres:5432/leadgen")
# Convert SQLAlchemy URL to asyncpg format
PG_DSN = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
PROJECT_ID = 18
BATCH_SIZE = 10  # Results per GPT call
CONCURRENCY = 15  # Parallel GPT calls
SEGMENTS = [
    "real_estate", "investment", "legal", "migration",
    "family_office", "crypto", "importers", "other_hnwi", "not_target",
]

SYSTEM_PROMPT = f"""You classify companies into segments. Given company info, assign the best matching segment.

SEGMENTS:
- real_estate: Property agencies, brokers, developers selling to Russian/CIS buyers abroad
- investment: Investment boutiques, private banking, wealth managers, IFAs, asset management, family offices
- legal: International tax, corporate structuring, trusts, offshore, VED lawyers, cross-border M&A
- migration: Immigration agencies, residence permits, citizenship by investment, golden visa, relocation
- family_office: Single/multi family offices, wealth planning for UHNWI
- crypto: OTC desks, crypto funds, mining companies, licensed exchanges
- importers: Auto importers, equipment importers, VED companies, import/export
- other_hnwi: Serves wealthy clients but doesn't fit above segments
- not_target: Not a target company (aggregator, directory, news, job board, irrelevant)

Respond with ONLY a JSON array of segment strings, one per company in order. Example: ["real_estate", "legal", "not_target"]"""


async def classify_batch(client: httpx.AsyncClient, batch: list[dict]) -> list[str]:
    """Classify a batch of companies via GPT-4o-mini."""
    items = []
    for r in batch:
        info = r.get("company_info") or {}
        name = info.get("name", r.get("domain", "?"))
        desc = info.get("description", "")
        services = ", ".join(info.get("services", [])[:5]) if info.get("services") else ""
        industry = info.get("industry", "")
        location = info.get("location", "")
        reasoning = (r.get("reasoning") or "")[:150]

        parts = [f"Domain: {r.get('domain', '?')}"]
        if name: parts.append(f"Name: {name}")
        if desc: parts.append(f"Desc: {desc[:120]}")
        if services: parts.append(f"Services: {services}")
        if industry: parts.append(f"Industry: {industry}")
        if location: parts.append(f"Location: {location}")
        if reasoning: parts.append(f"Analysis: {reasoning}")
        items.append("\n".join(parts))

    prompt = "Classify these companies:\n\n" + "\n---\n".join(
        f"[{i+1}] {item}" for i, item in enumerate(items)
    )

    for attempt in range(4):
        try:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.0,
                    "max_tokens": 200,
                },
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
            )
            if resp.status_code == 429:
                wait = 2.0 * (2 ** attempt)
                logger.warning(f"OpenAI 429, backing off {wait:.0f}s")
                await asyncio.sleep(wait)
                continue
            resp.raise_for_status()
            break
        except Exception as e:
            if attempt < 3:
                await asyncio.sleep(2.0)
                continue
            logger.error(f"GPT call failed: {e}")
            return ["not_target"] * len(batch)

    try:
        content = resp.json()["choices"][0]["message"]["content"]
        # Parse JSON array from response
        start = content.find("[")
        end = content.rfind("]")
        if start != -1 and end != -1:
            segments = json.loads(content[start:end+1])
            # Validate
            result = []
            for s in segments:
                s = s.strip().lower().replace(" ", "_")
                result.append(s if s in SEGMENTS else "not_target")
            # Pad if GPT returned fewer
            while len(result) < len(batch):
                result.append("not_target")
            return result[:len(batch)]
    except Exception as e:
        logger.error(f"Failed to parse GPT response: {e}")

    return ["not_target"] * len(batch)


async def main():
    if not OPENAI_API_KEY:
        print("ERROR: OPENAI_API_KEY not set")
        sys.exit(1)

    pool = await asyncpg.create_pool(PG_DSN, min_size=5, max_size=20)

    # Count unclassified
    async with pool.acquire() as conn:
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM search_results WHERE project_id = $1 AND matched_segment IS NULL",
            PROJECT_ID,
        )
    logger.info(f"Found {total} unclassified results to process")

    if total == 0:
        logger.info("Nothing to classify!")
        return

    # Fetch all unclassified in pages
    PAGE = 500
    offset = 0
    all_rows = []
    async with pool.acquire() as conn:
        while True:
            rows = await conn.fetch(
                """SELECT id, domain, company_info, reasoning, is_target
                   FROM search_results
                   WHERE project_id = $1 AND matched_segment IS NULL
                   ORDER BY id
                   LIMIT $2 OFFSET $3""",
                PROJECT_ID, PAGE, offset,
            )
            if not rows:
                break
            all_rows.extend([dict(r) for r in rows])
            offset += PAGE
            if len(rows) < PAGE:
                break

    logger.info(f"Loaded {len(all_rows)} rows, creating {len(all_rows) // BATCH_SIZE + 1} batches")

    # Process in batches with concurrency
    semaphore = asyncio.Semaphore(CONCURRENCY)
    classified = 0
    errors = 0
    segment_counts = {}
    start_time = time.time()

    async def process_batch(batch_rows):
        nonlocal classified, errors
        async with semaphore:
            batch_dicts = []
            for row in batch_rows:
                ci = row.get("company_info")
                if isinstance(ci, str):
                    try:
                        ci = json.loads(ci)
                    except:
                        ci = {}
                batch_dicts.append({
                    "id": row["id"],
                    "domain": row["domain"],
                    "company_info": ci or {},
                    "reasoning": row["reasoning"],
                    "is_target": row["is_target"],
                })

            async with httpx.AsyncClient(timeout=30) as client:
                segments = await classify_batch(client, batch_dicts)

            # Update DB
            async with pool.acquire() as conn:
                for row_dict, seg in zip(batch_dicts, segments):
                    try:
                        await conn.execute(
                            "UPDATE search_results SET matched_segment = $1 WHERE id = $2",
                            seg, row_dict["id"],
                        )
                        segment_counts[seg] = segment_counts.get(seg, 0) + 1
                        classified += 1
                    except Exception as e:
                        logger.error(f"DB update failed for id={row_dict['id']}: {e}")
                        errors += 1

            if classified % 200 == 0 and classified > 0:
                elapsed = time.time() - start_time
                rate = classified / elapsed
                eta = (total - classified) / rate if rate > 0 else 0
                logger.info(
                    f"Progress: {classified}/{total} ({classified*100//total}%) "
                    f"rate={rate:.1f}/s ETA={eta:.0f}s errors={errors}"
                )

    # Create batches
    batches = []
    for i in range(0, len(all_rows), BATCH_SIZE):
        batches.append(all_rows[i:i + BATCH_SIZE])

    # Run all batches with concurrency
    tasks = [process_batch(batch) for batch in batches]
    await asyncio.gather(*tasks, return_exceptions=True)

    elapsed = time.time() - start_time
    logger.info(f"\n=== DONE in {elapsed:.1f}s ===")
    logger.info(f"Classified: {classified}, Errors: {errors}")
    logger.info(f"Segment breakdown:")
    for seg, cnt in sorted(segment_counts.items(), key=lambda x: -x[1]):
        logger.info(f"  {seg}: {cnt}")

    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
