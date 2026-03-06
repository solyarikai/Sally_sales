"""
Run Inxy search pipeline — standalone script for separate container.

1. Sets up project + search config (idempotent)
2. Runs batch segment search with Apify proxy scraping
3. Logs progress to stdout

Run in a separate container on Hetzner:
  docker run -d --name inxy-search --network repo_default \
    -v ~/magnum-opus-project/repo/backend:/app \
    -v ~/magnum-opus-project/repo/scripts:/scripts \
    -e DATABASE_URL="postgresql+asyncpg://leadgen:leadgen_secret@postgres:5432/leadgen" \
    -e OPENAI_API_KEY="..." \
    -e APIFY_PROXY_PASSWORD="..." \
    -e YANDEX_SEARCH_API_KEY="..." \
    -e YANDEX_SEARCH_FOLDER_ID="..." \
    -e GOOGLE_GEMINI_API_KEY="..." \
    python:3.11 bash -c 'pip install -q -r /app/requirements.txt && python /scripts/run_inxy_search.py'
"""
import asyncio
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
logger = logging.getLogger("inxy_search")

# Import setup config
from setup_inxy_search import (
    PROJECT_NAME, COMPANY_ID, TARGET_SEGMENTS,
    SEARCH_CONFIG, ANTI_KEYWORDS,
)


async def setup_project():
    """Create/update Inxy project and search config. Returns project_id."""
    from app.db import async_session_maker
    from sqlalchemy import select
    from app.models.domain import ProjectSearchKnowledge
    from app.models.contact import Project

    async with async_session_maker() as session:
        result = await session.execute(
            select(Project).where(Project.name == PROJECT_NAME, Project.company_id == COMPANY_ID)
        )
        project = result.scalar_one_or_none()

        if project:
            logger.info(f"Found existing project: {project.name} (ID {project.id})")
        else:
            project = Project(
                company_id=COMPANY_ID,
                name=PROJECT_NAME,
                description="Crypto payment gateway — find gaming companies selling skins, items, cases, top-ups",
            )
            session.add(project)
            await session.flush()
            logger.info(f"Created new project: {project.name} (ID {project.id})")

        project.target_segments = TARGET_SEGMENTS
        project.auto_enrich_config = {
            "auto_extract": True,
            "auto_apollo": False,
            "apollo_titles": ["CEO", "Founder", "CTO", "Co-Founder", "Head of Payments", "COO"],
            "apollo_max_people": 5,
            "apollo_max_credits": 50,
            "scrape_method": "apify_proxy",
        }
        await session.flush()
        project_id = project.id

        result = await session.execute(
            select(ProjectSearchKnowledge).where(
                ProjectSearchKnowledge.project_id == project_id
            )
        )
        knowledge = result.scalar_one_or_none()
        if not knowledge:
            knowledge = ProjectSearchKnowledge(project_id=project_id)
            session.add(knowledge)

        knowledge.search_config = SEARCH_CONFIG
        knowledge.anti_keywords = ANTI_KEYWORDS
        await session.commit()

        logger.info(f"Project {project_id} configured with {len(SEARCH_CONFIG['segments'])} segments")
        return project_id


async def run_search(project_id: int):
    """Run batch segment search for all configured segments."""
    from app.db import async_session_maker
    from app.services.company_search_service import company_search_service
    from app.models.domain import SearchEngine

    segments = list(SEARCH_CONFIG["segments"].keys())
    logger.info(f"Starting search for {len(segments)} segments: {segments}")

    # Process segments sequentially (each creates its own jobs visible in UI)
    all_stats = []
    for seg_key in segments:
        seg_data = SEARCH_CONFIG["segments"][seg_key]
        geos = list(seg_data.get("geos", {}).keys())
        logger.info(f"\n{'='*60}")
        logger.info(f"SEGMENT: {seg_key} ({seg_data.get('label_en', '')}) — {len(geos)} geos")
        logger.info(f"{'='*60}")

        for geo_key in geos:
            logger.info(f"\n--- {seg_key}/{geo_key} ---")
            try:
                async with async_session_maker() as session:
                    stats = await company_search_service.run_segment_search(
                        session=session,
                        project_id=project_id,
                        company_id=COMPANY_ID,
                        segment_key=seg_key,
                        geo_key=geo_key,
                        search_engine=SearchEngine.YANDEX_API,
                        ai_expand_rounds=1,
                        ai_expand_count=20,
                    )
                    all_stats.append(stats)
                    logger.info(
                        f"  Result: {stats.get('targets_found', 0)} targets, "
                        f"{stats.get('domains_found', 0)} domains, "
                        f"{stats.get('total_queries', 0)} queries (job {stats.get('job_id')})"
                    )
            except Exception as e:
                logger.error(f"  FAILED: {e}")
                all_stats.append({"segment": seg_key, "geo": geo_key, "error": str(e)})

    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("SEARCH COMPLETE — SUMMARY")
    logger.info(f"{'='*60}")
    total_targets = sum(s.get("targets_found", 0) for s in all_stats)
    total_domains = sum(s.get("domains_found", 0) for s in all_stats)
    total_queries = sum(s.get("total_queries", 0) for s in all_stats)
    errors = sum(1 for s in all_stats if "error" in s)
    logger.info(f"Total targets: {total_targets}")
    logger.info(f"Total domains: {total_domains}")
    logger.info(f"Total queries: {total_queries}")
    logger.info(f"Errors: {errors}")
    logger.info(f"Segment results:")
    for s in all_stats:
        if "error" in s:
            logger.info(f"  {s['segment']}/{s['geo']}: ERROR — {s['error']}")
        else:
            logger.info(f"  {s['segment']}/{s['geo']}: {s.get('targets_found',0)} targets / {s.get('domains_found',0)} domains")


async def main():
    logger.info("=" * 60)
    logger.info("INXY SEARCH PIPELINE — STARTING")
    logger.info("=" * 60)

    # Phase 1: Setup
    project_id = await setup_project()

    # Phase 2: Search
    await run_search(project_id)

    logger.info("\nDone. Check results in UI at /search-results")


if __name__ == "__main__":
    asyncio.run(main())
