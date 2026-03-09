"""
Inxy Apollo TARGETED search — Use SINGLE gaming-specific keyword tags
to find relevant companies. Apollo keyword_tags is AND-matched, so
multi-tag combos return almost nothing for niche terms.

Strategy: search with 1 keyword at a time for high-signal gaming tags.
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
logger = logging.getLogger("inxy_apollo_targeted")

PROJECT_ID = 48
COMPANY_ID = 1

# Low-risk geos (extended list)
LOW_RISK_LOCATIONS = [
    "Germany", "France", "Sweden", "Finland", "Denmark", "Norway",
    "Canada", "Australia", "Japan", "New Zealand", "Austria",
    "Belgium", "Ireland", "Switzerland", "Estonia", "Iceland",
    "Netherlands", "Portugal", "Spain", "Italy", "Czech Republic",
    "Poland", "Lithuania", "Latvia", "Malta", "Cyprus", "Luxembourg",
]

# Single keyword tags — each one searched alone across all geos
# These are the ACTUAL Apollo keyword_tags found on team's 87 gaming companies
SINGLE_KEYWORD_SEARCHES = [
    # Direct from Phase 1 enrichment (found on real gaming companies)
    "cs2 skins",
    "cs2 skins marketplace",
    "skin marketplace",
    "buy skins",
    "sell skins",
    "skin trading platform",
    "virtual items",
    "in-game items",
    "crypto casino",
    "online gambling",
    "case opening",

    # Broader gaming tags
    "game items",
    "virtual goods",
    "game marketplace",
    "steam trading",
    "csgo",
    "game keys",
    "game accounts",
    "loot box",
    "esports betting",
    "skin gambling",
    "rust skins",

    # Crypto + gaming
    "cryptocurrency payments",
    "crypto gaming",
    "bitcoin gambling",
    "blockchain gaming",
]


async def main():
    from app.db import async_session_maker
    from app.services.apollo_service import apollo_service
    from app.services.company_search_service import company_search_service
    from app.models.domain import (
        SearchJob, SearchJobStatus, SearchEngine, SearchResult,
    )
    from app.models.contact import Project
    from sqlalchemy import select, func
    from datetime import datetime

    logger.info("=" * 60)
    logger.info("INXY APOLLO TARGETED — Single-keyword gaming search")
    logger.info("=" * 60)

    all_found_domains = set()
    search_count = 0
    total_searches = len(SINGLE_KEYWORD_SEARCHES) * len(LOW_RISK_LOCATIONS)

    for keyword in SINGLE_KEYWORD_SEARCHES:
        keyword_total = 0
        for location in LOW_RISK_LOCATIONS:
            search_count += 1
            try:
                orgs = await apollo_service.search_organizations_all_pages(
                    keyword_tags=[keyword],
                    locations=[location],
                    max_pages=5,
                    per_page=100,
                )

                new_in_search = 0
                for org in orgs:
                    domain = org.get("primary_domain") or ""
                    if domain and "." in domain:
                        d = domain.lower().strip()
                        if d not in all_found_domains:
                            new_in_search += 1
                        all_found_domains.add(d)

                keyword_total += new_in_search
                if new_in_search > 0:
                    logger.info(f"  [{search_count}/{total_searches}] '{keyword}' / {location}: +{new_in_search} new")

            except Exception as e:
                logger.error(f"  [{search_count}/{total_searches}] '{keyword}' / {location}: error: {e}")

            await asyncio.sleep(0.15)

        if keyword_total > 0:
            logger.info(f"  >>> '{keyword}' total: +{keyword_total} new domains")

    logger.info(f"\nTargeted search found {len(all_found_domains)} unique domains total")

    if not all_found_domains:
        logger.info("No domains found. Done.")
        return

    # Filter and analyze
    async with async_session_maker() as session:
        result = await session.execute(select(Project).where(Project.id == PROJECT_ID))
        project = result.scalar_one()

        skip_set = await company_search_service._build_skip_set(session, PROJECT_ID)
        new_domains = [d for d in all_found_domains if d not in skip_set]
        logger.info(f"New domains to analyze: {len(new_domains)} (skip_set: {len(skip_set)})")

        if not new_domains:
            logger.info("All domains already analyzed.")
            return

        tc = await session.execute(
            select(func.count()).select_from(SearchResult).where(
                SearchResult.project_id == PROJECT_ID, SearchResult.is_target == True
            )
        )
        before = tc.scalar() or 0

        job = SearchJob(
            company_id=COMPANY_ID,
            status=SearchJobStatus.PENDING,
            search_engine=SearchEngine.YANDEX_API,
            queries_total=0,
            domains_found=len(all_found_domains),
            domains_new=len(new_domains),
            project_id=PROJECT_ID,
            config={
                "segment": "apollo_targeted_gaming",
                "geo": "low_risk_extended",
                "query_source": "apollo_single_keyword_gaming",
                "total_apollo_domains": len(all_found_domains),
                "keywords_used": SINGLE_KEYWORD_SEARCHES,
            },
        )
        session.add(job)
        await session.flush()
        logger.info(f"Created job {job.id}")
        await session.commit()

        BATCH = 50
        for i in range(0, len(new_domains), BATCH):
            batch = new_domains[i:i + BATCH]
            batch_num = i // BATCH + 1
            total_batches = (len(new_domains) + BATCH - 1) // BATCH
            logger.info(f"Batch {batch_num}/{total_batches}: analyzing {len(batch)} domains...")
            try:
                await company_search_service._scrape_and_analyze_domains(
                    session=session,
                    job=job,
                    domains=batch,
                    target_segments=project.target_segments,
                )
                await session.commit()

                tc = await session.execute(
                    select(func.count()).select_from(SearchResult).where(
                        SearchResult.project_id == PROJECT_ID,
                        SearchResult.is_target == True,
                    )
                )
                current = tc.scalar() or 0
                logger.info(f"  Batch {batch_num} done. Targets: {current} (+{current - before})")
            except Exception as e:
                logger.error(f"  Batch {batch_num} error: {e}")

        job.status = SearchJobStatus.COMPLETED
        job.completed_at = datetime.utcnow()
        await session.commit()

        tc = await session.execute(
            select(func.count()).select_from(SearchResult).where(
                SearchResult.project_id == PROJECT_ID, SearchResult.is_target == True
            )
        )
        after = tc.scalar() or 0
        logger.info(f"\n{'='*60}")
        logger.info(f"TARGETED APOLLO COMPLETE")
        logger.info(f"Targets before: {before}")
        logger.info(f"Targets after:  {after}")
        logger.info(f"New targets:    {after - before}")
        logger.info(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
