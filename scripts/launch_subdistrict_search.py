"""Launch Archistruct subdistrict search with comprehensive district list.
Updates target_segments with all Dubai/Abu Dhabi subdistricts, then runs pipeline.
Run inside Docker container with DB access."""
import asyncio
import sys
import os
import logging

sys.path.insert(0, "/app")
os.environ.setdefault("DATABASE_URL", os.environ.get("DATABASE_URL", ""))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("subdistrict_search")

# Comprehensive subdistrict list to append to ГЕОГРАФИЯ section
SUBDISTRICT_ADDITION = """

РАЙОНЫ И СООБЩЕСТВА (для поисковых запросов — искать подрядчиков по каждому району):

Dubai districts:
Palm Jumeirah, Dubai Hills Estate, Emirates Hills, Al Barari, Meydan, District One,
Jumeirah Golf Estates, Damac Hills, Damac Hills 2, Arabian Ranches, Arabian Ranches 2,
Arabian Ranches 3, MBR City, Tilal Al Ghaf, DAMAC Lagoons, The Valley, Jumeirah Bay,
La Mer, Pearl Jumeirah, Jumeirah Islands, Jumeirah Park, JVC, JVT, The Springs,
The Meadows, The Lakes, Al Furjan, Mudon, Villanova, Nad Al Sheba, Sobha Hartland,
Victory Heights, Falcon City, The Villa Dubailand, Sustainable City, Living Legends,
Green Community, Town Square, Al Barsha, Umm Suqeim, Dubai South, Dubai Creek Harbour,
Hatta, The World Islands, Bluewaters, Remraam

Abu Dhabi districts:
Saadiyat Island, Yas Island, Al Reem Island, Al Raha Beach, Al Raha Gardens,
Khalifa City, Al Reef, Al Shamkha, MBZ City, Jubail Island, Nurai Island,
Hudayriyat Island, Al Bateen, Al Gurm, Ghantoot, Al Samha, Masdar City,
Hidd Al Saadiyat
"""


async def main():
    from sqlalchemy import select
    from app.db import async_session_maker
    from app.models.contact import Project
    from app.services.company_search_service import company_search_service

    project_id = 24
    company_id = 1
    max_queries = 2000
    target_goal = 500

    async with async_session_maker() as session:
        # 1. Update target_segments with subdistrict list
        result = await session.execute(
            select(Project).where(Project.id == project_id)
        )
        project = result.scalar_one_or_none()
        if not project:
            logger.error(f"Project {project_id} not found!")
            return

        current_segments = project.target_segments or ""
        if "РАЙОНЫ И СООБЩЕСТВА" not in current_segments:
            project.target_segments = current_segments + SUBDISTRICT_ADDITION
            await session.commit()
            logger.info(f"Updated target_segments with {len(SUBDISTRICT_ADDITION)} chars of subdistrict data")
        else:
            logger.info("Subdistrict data already present in target_segments, skipping update")

        # 2. Run the search pipeline
        logger.info(f"Starting subdistrict search (project_id={project_id}, "
                     f"max_queries={max_queries}, target_goal={target_goal})")

        try:
            job = await company_search_service.run_project_search(
                session=session,
                project_id=project_id,
                company_id=company_id,
                max_queries=max_queries,
                target_goal=target_goal,
            )
            logger.info(f"Search completed! Job ID: {job.id}")
            logger.info(f"Config: {job.config}")
        except Exception as e:
            logger.error(f"Search failed: {e}", exc_info=True)
            raise


if __name__ == "__main__":
    asyncio.run(main())
