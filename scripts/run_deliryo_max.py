"""Deliryo MAX search — find full TAM. target_goal=5000, max_queries=5000."""
import asyncio
import json
import logging
import os
import sys
from datetime import datetime

sys.path.insert(0, "/app")
os.environ.setdefault("DATABASE_URL", os.environ.get("DATABASE_URL", ""))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("deliryo_max")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


async def main():
    from app.db import async_session_maker
    from app.services.company_search_service import company_search_service
    from sqlalchemy import text

    async with async_session_maker() as session:
        row = await session.execute(text("SELECT company_id FROM projects WHERE id = 18"))
        company_id = row.scalar_one()

        logger.info("=" * 70)
        logger.info("DELIRYO MAX SEARCH — FIND FULL TAM")
        logger.info("target_goal=5000, max_queries=5000")
        logger.info("Will run until Yandex is fully exhausted (3 consecutive zero-yield iterations)")
        logger.info("=" * 70)

        start = datetime.utcnow()

        job = await company_search_service.run_project_search(
            session=session,
            project_id=18,
            company_id=company_id,
            max_queries=5000,
            target_goal=5000,
        )

        elapsed = (datetime.utcnow() - start).total_seconds()
        config = job.config or {}
        logger.info("=" * 70)
        logger.info(f"DONE in {elapsed:.0f}s ({elapsed/60:.1f} min)")
        logger.info(f"Job ID: {job.id}")
        logger.info(f"Final targets: {config.get('final_targets', '?')}")
        logger.info(f"Iterations: {config.get('iterations_run', '?')}")
        logger.info(f"Queries generated: {config.get('queries_generated', '?')}")
        logger.info(f"Config: {json.dumps(config, indent=2, default=str)}")
        logger.info("=" * 70)


asyncio.run(main())
