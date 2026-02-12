"""
Deliryo Google SERP Discovery — Full Auto-Improvement Pipeline
==============================================================
Reuses the same iterative pipeline as Yandex search:
  GPT query generation → Google SERP (via Apify) → Crona scrape → GPT scoring
  → Auto-review → Update knowledge → Generate better queries → Loop

This is the same flow as run_project_search() but with SearchEngine.GOOGLE_SERP.
The search_service._scrape_single_query() handles Google via Apify SERP proxy.

Apify SERP cost: $0.0017 per Google result page.
Apify proxy password (NOT the API token): found via Apify /v2/users/me endpoint.

Deliryo ICP: companies working with Russian HNWI — family offices, wealth
management, private banking, trust services. Deliryo offers rub↔usdt.

Usage (Docker, runs alongside Apollo scoring):
  docker run -d --name deliryo-google --network repo_default \
    --restart unless-stopped \
    -v ~/magnum-opus-project/repo/backend:/app \
    -v ~/magnum-opus-project/repo/scripts:/scripts \
    -e DATABASE_URL=... -e OPENAI_API_KEY=... \
    -e CRONA_EMAIL=... -e CRONA_PASSWORD=... \
    -e APIFY_PROXY_PASSWORD=apify_proxy_zZ12PNY7illL44MXT8Cf3vKetkI5I62Oupn2 \
    python:3.11 bash -c 'pip install -q -r /app/requirements.txt && python /scripts/deliryo_google_serp.py'
"""
import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
sys.path.insert(0, "/app")
os.environ.setdefault("DATABASE_URL", os.environ.get("DATABASE_URL", ""))

# Set Apify proxy password if not in env (fallback to known value)
if not os.environ.get("APIFY_PROXY_PASSWORD"):
    os.environ["APIFY_PROXY_PASSWORD"] = "apify_proxy_zZ12PNY7illL44MXT8Cf3vKetkI5I62Oupn2"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("deliryo_google")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

PROJECT_ID = 18
COMPANY_ID = 4  # Deliryo company


async def main():
    from app.db import async_session_maker
    from app.models.domain import SearchEngine
    from app.services.company_search_service import company_search_service

    logger.info("=" * 70)
    logger.info("DELIRYO GOOGLE SERP — AUTO-IMPROVEMENT PIPELINE")
    logger.info("=" * 70)
    logger.info("Using same iterative flow as Yandex search:")
    logger.info("  GPT queries → Google SERP → Crona scrape → GPT scoring")
    logger.info("  → Auto-review → Knowledge update → Better queries → Loop")
    logger.info("=" * 70)

    async with async_session_maker() as session:
        # Count existing targets before starting
        existing = await company_search_service._count_project_targets(session, PROJECT_ID)
        logger.info(f"Existing Deliryo targets: {existing}")

        # Run the full iterative pipeline with Google SERP engine.
        # This generates GPT queries, searches Google via Apify proxy,
        # scrapes + scores via Crona/GPT, auto-reviews, updates knowledge,
        # and iterates until target_goal or search exhaustion.
        job = await company_search_service.run_project_search(
            session=session,
            project_id=PROJECT_ID,
            company_id=COMPANY_ID,
            max_queries=500,
            target_goal=1000,  # ambitious — will stop on stall anyway
            search_engine=SearchEngine.GOOGLE_SERP,
        )

        final = await company_search_service._count_project_targets(session, PROJECT_ID)

    logger.info("\n" + "=" * 70)
    logger.info("DELIRYO GOOGLE SERP — COMPLETE")
    logger.info("=" * 70)
    logger.info(f"Job ID:            #{job.id}")
    logger.info(f"Status:            {job.status}")
    logger.info(f"Queries used:      {job.queries_total}")
    logger.info(f"Targets before:    {existing}")
    logger.info(f"Targets after:     {final}")
    logger.info(f"New targets:       {final - existing}")

    config = job.config or {}
    logger.info(f"Iterations:        {config.get('iterations_run', '?')}")
    logger.info(f"GPT tokens:        {config.get('query_gen_tokens', '?')}")
    logger.info("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
