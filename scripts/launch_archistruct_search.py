"""Launch a large Archistruct search job with improved prompts.
Run inside Docker container with DB access."""
import asyncio
import sys
import os
import logging

# Add backend to path
sys.path.insert(0, "/app")
os.environ.setdefault("DATABASE_URL", os.environ.get("DATABASE_URL", ""))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("archistruct_search")

async def main():
    from app.db import async_session_maker
    from app.services.company_search_service import company_search_service

    async with async_session_maker() as session:
        logger.info("Starting Archistruct search (project_id=24, max_queries=2000, target_goal=1000)")

        try:
            job = await company_search_service.run_project_search(
                session=session,
                project_id=24,
                company_id=1,
                max_queries=2000,
                target_goal=1000,
            )
            logger.info(f"Search completed! Job ID: {job.id}")
            logger.info(f"Config: {job.config}")
        except Exception as e:
            logger.error(f"Search failed: {e}", exc_info=True)
            raise

if __name__ == "__main__":
    asyncio.run(main())
