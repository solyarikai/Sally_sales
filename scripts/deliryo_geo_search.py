"""
Deliryo GEO Search — New geographies + Real Estate segment
===========================================================
Runs Yandex first (cheapest), then Google SERP, both with updated ICP:
- HNWI service providers (wealth mgmt, family offices, private banking)
- Real estate agencies selling luxury property to Russian HNWI

New geos: Thailand, UAE, Turkey, France, Spain, Cyprus, Greece,
Indonesia, Georgia, Montenegro.

Excludes all already-found targets and campaign contacts via skip set.

Usage:
  docker run -d --name deliryo-geo --network repo_default \
    --restart unless-stopped \
    -v ~/magnum-opus-project/repo/backend:/app \
    -v ~/magnum-opus-project/repo/scripts:/scripts \
    -v ~/magnum-opus-project/repo/google-credentials.json:/app/google-credentials.json:ro \
    -e DATABASE_URL=postgresql+asyncpg://leadgen:leadgen_secret@postgres:5432/leadgen \
    -e OPENAI_API_KEY=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 \
    -e YANDEX_SEARCH_API_KEY=AQVNyM68azFp-ua5Gx9UKCi2kjd9ceASfYLYLYhd \
    -e YANDEX_SEARCH_FOLDER_ID=b1ghcrnch8s4l0saftba \
    -e CRONA_EMAIL=pn@getsally.io \
    -e CRONA_PASSWORD=Qweqweqwe1 \
    -e APIFY_PROXY_PASSWORD=apify_proxy_zZ12PNY7illL44MXT8Cf3vKetkI5I62Oupn2 \
    python:3.11 bash -c 'pip install -q -r /app/requirements.txt && python /scripts/deliryo_geo_search.py'
"""
import asyncio
import json
import logging
import os
import sys
from datetime import datetime

sys.path.insert(0, "/app")
os.environ.setdefault("DATABASE_URL", os.environ.get("DATABASE_URL", ""))

# Set Apify proxy password
if not os.environ.get("APIFY_PROXY_PASSWORD"):
    os.environ["APIFY_PROXY_PASSWORD"] = "apify_proxy_zZ12PNY7illL44MXT8Cf3vKetkI5I62Oupn2"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("deliryo_geo")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

PROJECT_ID = 18
COMPANY_ID = 1


async def main():
    from app.db import async_session_maker
    from app.models.domain import SearchEngine
    from app.services.company_search_service import company_search_service

    start = datetime.utcnow()

    async with async_session_maker() as session:
        existing_before = await company_search_service._count_project_targets(session, PROJECT_ID)
        logger.info(f"Existing Deliryo targets before: {existing_before}")

    # ============================================================
    # PARALLEL: Yandex + Google SERP simultaneously
    # ============================================================
    logger.info("=" * 70)
    logger.info("RUNNING YANDEX + GOOGLE SERP IN PARALLEL")
    logger.info("=" * 70)
    logger.info("New geos + real estate + HNWI consultation segments")
    logger.info("max_queries=1000 each, target_goal=1000")
    logger.info("=" * 70)

    async def run_yandex():
        async with async_session_maker() as session:
            job = await company_search_service.run_project_search(
                session=session,
                project_id=PROJECT_ID,
                company_id=COMPANY_ID,
                max_queries=1000,
                target_goal=1000,
                search_engine=SearchEngine.YANDEX_API,
            )
            targets = await company_search_service._count_project_targets(session, PROJECT_ID)
        logger.info(f"YANDEX DONE — job #{job.id}, status={job.status}, targets now={targets}")
        return job, targets

    async def run_google():
        async with async_session_maker() as session:
            job = await company_search_service.run_project_search(
                session=session,
                project_id=PROJECT_ID,
                company_id=COMPANY_ID,
                max_queries=1000,
                target_goal=1000,
                search_engine=SearchEngine.GOOGLE_SERP,
            )
            targets = await company_search_service._count_project_targets(session, PROJECT_ID)
        logger.info(f"GOOGLE DONE — job #{job.id}, status={job.status}, targets now={targets}")
        return job, targets

    (yandex_job, after_yandex), (google_job, after_google) = await asyncio.gather(
        run_yandex(), run_google()
    )

    yandex_config = yandex_job.config or {}
    google_config = google_job.config or {}
    elapsed = (datetime.utcnow() - start).total_seconds()

    logger.info("")
    logger.info("=" * 70)
    logger.info("DELIRYO GEO SEARCH — COMPLETE")
    logger.info("=" * 70)
    logger.info(f"Total time:     {elapsed:.0f}s ({elapsed/60:.1f} min)")
    logger.info(f"Targets before: {existing_before}")
    logger.info(f"Targets after:  {max(after_yandex, after_google)} (+{max(after_yandex, after_google) - existing_before})")
    logger.info("=" * 70)
    logger.info(f"Yandex job #{yandex_job.id}: {yandex_config.get('queries_generated', '?')} queries, "
                f"{yandex_config.get('iterations_run', '?')} iterations")
    logger.info(f"Google job #{google_job.id}: {google_config.get('queries_generated', '?')} queries, "
                f"{google_config.get('iterations_run', '?')} iterations")
    logger.info("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
