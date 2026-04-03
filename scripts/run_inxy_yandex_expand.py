"""
Inxy Yandex expansion — Run proven high-conversion queries across ALL low-risk geos.

Previous searches only covered Germany and France. This runs the best queries
(by target hit rate) across Sweden, Finland, Denmark, Norway, Canada, Australia,
Japan, New Zealand, Austria, Belgium, Ireland, Switzerland, Estonia, etc.
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
logger = logging.getLogger("inxy_yandex_expand")

PROJECT_ID = 48
COMPANY_ID = 1

# All low-risk geos (country codes for Yandex geo targeting)
TARGET_GEOS = [
    "sweden", "finland", "denmark", "norway",
    "canada", "australia", "japan", "new_zealand",
    "austria", "belgium", "ireland", "switzerland", "estonia",
    # Extended low-risk
    "netherlands", "portugal", "spain", "italy",
    "czech_republic", "poland", "malta", "cyprus",
]

# Top performing queries from actual results — proven to find targets
# Grouped by effectiveness
TOP_QUERIES = [
    # Tier 1: Highest conversion (>10% hit rate)
    "buy CS2 skins",
    "sell CS2 skins",
    "sell FIFA items online",
    "sell World of Warcraft coins online",

    # Tier 2: Good conversion (3-10%)
    "buy Steam skins",
    "buy Dota 2 items",
    "buy TF2 skins",
    "sell Fortnite gold online",
    "sell Roblox items online",
    "sell League of Legends currency online",
    "sell Valorant gold online",
    "buy game accounts online",
    "sell Path of Exile coins online",

    # Tier 3: Proven patterns, new variations
    "CS2 skin marketplace",
    "CSGO trading site",
    "buy Rust skins",
    "sell Rust skins",
    "buy PUBG items",
    "game item trading platform",
    "virtual goods marketplace",
    "buy game keys crypto",
    "CS2 case opening",
    "CSGO gambling site",
    "buy Steam gift card crypto",
    "game skin trading",
    "sell game items for crypto",

    # Tier 4: Competitor searches (high signal)
    "sites like skinport",
    "skinbaron alternatives",
    "DMarket alternatives",
    "CSFloat alternatives",
    "sites like Hellcase",
    "sites like KeyDrop",
    "Bitskins alternatives",
    "Waxpeer alternatives",

    # Tier 5: Crypto payment angle (highest value for Inxy)
    "buy skins with Bitcoin",
    "crypto skin marketplace",
    "buy game items cryptocurrency",
    "gaming marketplace crypto payment",
    "Steam skins Bitcoin",
    "CS2 skins USDT",
]


async def main():
    from app.db import async_session_maker
    from app.services.company_search_service import company_search_service
    from app.services.search_service import search_service
    from app.models.domain import (
        SearchJob, SearchJobStatus, SearchEngine,
        SearchQuery, SearchResult,
    )
    from app.models.contact import Project
    from sqlalchemy import select, func
    from datetime import datetime

    logger.info("=" * 60)
    logger.info("INXY YANDEX EXPANSION — Top queries × all geos")
    logger.info(f"Queries: {len(TOP_QUERIES)}, Geos: {len(TARGET_GEOS)}")
    logger.info("=" * 60)

    async with async_session_maker() as session:
        # Load project
        result = await session.execute(select(Project).where(Project.id == PROJECT_ID))
        project = result.scalar_one()

        # Check existing queries to avoid duplicates
        existing_q = await session.execute(
            select(SearchQuery.query_text, SearchQuery.geo).join(SearchJob).where(
                SearchJob.project_id == PROJECT_ID
            )
        )
        existing_combos = {(r[0].strip().lower(), r[1]) for r in existing_q.fetchall()}
        logger.info(f"Existing query/geo combos: {len(existing_combos)}")

        # Build new query list
        new_query_geo_pairs = []
        for query in TOP_QUERIES:
            for geo in TARGET_GEOS:
                if (query.strip().lower(), geo) not in existing_combos:
                    new_query_geo_pairs.append((query, geo))

        logger.info(f"New query/geo combos to run: {len(new_query_geo_pairs)}")
        if not new_query_geo_pairs:
            logger.info("All combos already searched. Done.")
            return

        tc = await session.execute(
            select(func.count()).select_from(SearchResult).where(
                SearchResult.project_id == PROJECT_ID, SearchResult.is_target == True
            )
        )
        before = tc.scalar() or 0
        logger.info(f"Targets before: {before}")

        # Process geo by geo (better for tracking)
        for geo in TARGET_GEOS:
            geo_queries = [q for q, g in new_query_geo_pairs if g == geo]
            if not geo_queries:
                continue

            logger.info(f"\n--- Yandex: {geo} ({len(geo_queries)} queries) ---")

            job = SearchJob(
                company_id=COMPANY_ID,
                status=SearchJobStatus.PENDING,
                search_engine=SearchEngine.YANDEX_API,
                queries_total=len(geo_queries),
                project_id=PROJECT_ID,
                config={
                    "segment": "yandex_expansion",
                    "geo": geo,
                    "query_source": "top_queries_expansion",
                    "queries_count": len(geo_queries),
                },
            )
            session.add(job)
            await session.flush()

            for q_text in geo_queries:
                sq = SearchQuery(
                    search_job_id=job.id,
                    query_text=q_text,
                    segment="yandex_expansion",
                    geo=geo,
                    language="en",
                )
                session.add(sq)
            await session.commit()

            logger.info(f"  Created job {job.id}, running search...")

            try:
                await search_service.run_search_job(session, job.id)
            except Exception as e:
                logger.error(f"  Search error: {e}")

            await session.refresh(job)
            logger.info(f"  Search done: {job.domains_found} domains, {job.domains_new} new")

            # Get new domains to analyze
            skip_set = await company_search_service._build_skip_set(session, PROJECT_ID)
            new_domains = await company_search_service._get_new_domains_from_job(session, job, skip_set)

            if new_domains:
                logger.info(f"  Analyzing {len(new_domains)} new domains...")
                try:
                    await company_search_service._scrape_and_analyze_domains(
                        session=session,
                        job=job,
                        domains=new_domains,
                        target_segments=project.target_segments,
                    )
                    await session.commit()
                except Exception as e:
                    logger.error(f"  Analysis error: {e}")

            job.status = SearchJobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            await session.commit()

            # Check targets
            tc = await session.execute(
                select(func.count()).select_from(SearchResult).where(
                    SearchResult.project_id == PROJECT_ID,
                    SearchResult.is_target == True,
                )
            )
            current = tc.scalar() or 0
            logger.info(f"  Targets: {current} (+{current - before})")

        # Final stats
        tc = await session.execute(
            select(func.count()).select_from(SearchResult).where(
                SearchResult.project_id == PROJECT_ID, SearchResult.is_target == True
            )
        )
        after = tc.scalar() or 0
        ta = await session.execute(
            select(func.count()).select_from(SearchResult).where(
                SearchResult.project_id == PROJECT_ID
            )
        )
        analyzed = ta.scalar() or 0

        logger.info(f"\n{'='*60}")
        logger.info(f"YANDEX EXPANSION COMPLETE")
        logger.info(f"Total analyzed: {analyzed}")
        logger.info(f"Targets before: {before}")
        logger.info(f"Targets after:  {after}")
        logger.info(f"New targets:    {after - before}")
        logger.info(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
