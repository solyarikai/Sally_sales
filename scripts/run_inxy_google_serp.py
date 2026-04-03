"""
Inxy Google SERP search — Use top-performing queries via Google to find new targets.

Runs after Yandex/Apollo are exhausted. Uses Apify Google SERP scraper.
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
logger = logging.getLogger("inxy_google_serp")

PROJECT_ID = 48
COMPANY_ID = 1

# Top-performing queries from Yandex results (highest target hit rate)
TOP_QUERIES = [
    # Tier 1: Highest conversion
    "buy CS2 skins online",
    "sell CS2 skins marketplace",
    "CS2 skin trading platform",
    "CSGO skins marketplace",
    "game skin marketplace buy sell",

    # Tier 2: Competitor / alternative searches (high signal)
    "skinport alternatives",
    "skinbaron alternatives",
    "DMarket alternatives",
    "CSFloat alternatives",
    "Hellcase alternatives",
    "KeyDrop alternatives",
    "Bitskins alternatives",
    "Waxpeer alternatives",
    "top CS2 skin trading sites",
    "best CSGO skin marketplaces 2024",
    "best CSGO skin marketplaces 2025",

    # Tier 3: Game-specific item trading
    "buy Rust skins marketplace",
    "Dota 2 item trading site",
    "TF2 trading marketplace",
    "PUBG skin marketplace",
    "Fortnite item shop third party",
    "Roblox item trading marketplace",

    # Tier 4: Crypto payment angle
    "buy game skins with Bitcoin",
    "crypto payment gaming marketplace",
    "buy CS2 skins cryptocurrency",
    "game items buy crypto",

    # Tier 5: Case opening / gambling
    "CS2 case opening sites",
    "CSGO case opening website",
    "skin gambling sites",
    "esports betting crypto",

    # Tier 6: Broader gaming commerce
    "game key marketplace",
    "buy game accounts online",
    "virtual goods marketplace gaming",
    "game currency buy sell online",
    "FIFA coins buy online",
    "WoW gold marketplace",
    "game boosting service",
    "Steam gift card marketplace",
]

# Google search geo/language combos (focusing on English results globally)
SEARCH_CONFIGS = [
    {"gl": "us", "hl": "en"},  # Global English
    {"gl": "de", "hl": "en"},  # Germany
    {"gl": "fr", "hl": "en"},  # France
    {"gl": "se", "hl": "en"},  # Sweden
    {"gl": "ca", "hl": "en"},  # Canada
    {"gl": "au", "hl": "en"},  # Australia
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
    logger.info("INXY GOOGLE SERP SEARCH")
    logger.info(f"Queries: {len(TOP_QUERIES)}, Configs: {len(SEARCH_CONFIGS)}")
    logger.info("=" * 60)

    # Load project config once
    async with async_session_maker() as session:
        result = await session.execute(select(Project).where(Project.id == PROJECT_ID))
        project = result.scalar_one()
        target_segments = project.target_segments

        # Check existing queries
        existing_q = await session.execute(
            select(SearchQuery.query_text, SearchQuery.geo).join(SearchJob).where(
                SearchJob.project_id == PROJECT_ID,
                SearchJob.search_engine == SearchEngine.GOOGLE_SERP,
            )
        )
        existing_combos = {(r[0].strip().lower(), r[1]) for r in existing_q.fetchall()}
        logger.info(f"Existing Google query/geo combos: {len(existing_combos)}")

        tc = await session.execute(
            select(func.count()).select_from(SearchResult).where(
                SearchResult.project_id == PROJECT_ID, SearchResult.is_target == True
            )
        )
        before = tc.scalar() or 0
        logger.info(f"Targets before: {before}")

    # Process each geo in a separate session to isolate errors
    for config in SEARCH_CONFIGS:
        geo = config["gl"]

        # Build queries for this geo
        geo_queries = [
            q for q in TOP_QUERIES
            if (q.strip().lower(), geo) not in existing_combos
        ]

        if not geo_queries:
            logger.info(f"--- Google {geo}: all queries already run, skip ---")
            continue

        logger.info(f"\n--- Google {geo}: {len(geo_queries)} queries ---")

        try:
            async with async_session_maker() as session:
                job = SearchJob(
                    company_id=COMPANY_ID,
                    status=SearchJobStatus.PENDING,
                    search_engine=SearchEngine.GOOGLE_SERP,
                    queries_total=len(geo_queries),
                    project_id=PROJECT_ID,
                    config={
                        "segment": "google_serp_expansion",
                        "geo": geo,
                        "hl": config["hl"],
                        "query_source": "top_queries_google",
                        "queries_count": len(geo_queries),
                    },
                )
                session.add(job)
                await session.flush()

                for q_text in geo_queries:
                    sq = SearchQuery(
                        search_job_id=job.id,
                        query_text=q_text,
                        segment="google_serp_expansion",
                        geo=geo,
                        language=config["hl"],
                    )
                    session.add(sq)
                await session.commit()

                job_id = job.id
                logger.info(f"  Created job {job_id}, running search...")

                try:
                    await search_service.run_search_job(session, job_id)
                except Exception as e:
                    logger.error(f"  Search error: {e}")
                    await session.rollback()

            # Fresh session for analysis
            async with async_session_maker() as session:
                job_q = await session.execute(select(SearchJob).where(SearchJob.id == job_id))
                job = job_q.scalar_one()
                logger.info(f"  Search done: {job.domains_found} domains, {job.domains_new} new")

                skip_set = await company_search_service._build_skip_set(session, PROJECT_ID)
                new_domains = await company_search_service._get_new_domains_from_job(session, job, skip_set)

                if new_domains:
                    logger.info(f"  Analyzing {len(new_domains)} new domains...")
                    try:
                        await company_search_service._scrape_and_analyze_domains(
                            session=session,
                            job=job,
                            domains=new_domains,
                            target_segments=target_segments,
                        )
                        await session.commit()
                    except Exception as e:
                        logger.error(f"  Analysis error: {e}")
                        await session.rollback()

                job.status = SearchJobStatus.COMPLETED
                job.completed_at = datetime.utcnow()
                await session.commit()

                tc = await session.execute(
                    select(func.count()).select_from(SearchResult).where(
                        SearchResult.project_id == PROJECT_ID, SearchResult.is_target == True,
                    )
                )
                current = tc.scalar() or 0
                logger.info(f"  Targets: {current} (+{current - before})")

                # Mark combos as done so we don't retry
                for q_text in geo_queries:
                    existing_combos.add((q_text.strip().lower(), geo))

        except Exception as e:
            logger.error(f"  Geo {geo} FAILED: {e}")
            continue

    # Final stats
    async with async_session_maker() as session:
        tc = await session.execute(
            select(func.count()).select_from(SearchResult).where(
                SearchResult.project_id == PROJECT_ID, SearchResult.is_target == True
            )
        )
        after = tc.scalar() or 0

        logger.info(f"\n{'='*60}")
        logger.info(f"GOOGLE SERP COMPLETE")
        logger.info(f"Targets before: {before}")
        logger.info(f"Targets after:  {after}")
        logger.info(f"New targets:    {after - before}")
        logger.info(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
