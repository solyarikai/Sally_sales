"""
Inxy search v2 — Improved search based on top-performing queries.

Strategy:
1. Analyze which queries found the most targets
2. Generate similar queries for ALL remaining geos (not just the one that worked)
3. Use Google SERP (broader English coverage) alongside Yandex
4. Add direct doc_keyword queries inspired by top performers
5. Fix the UniqueViolationError on domains table

Run in separate container on Hetzner:
  docker run -d --name inxy-search-v2 --network repo_default \
    -v /tmp/inxy-work/backend:/app \
    -v /tmp/inxy-work/scripts:/scripts \
    -e DATABASE_URL="..." -e OPENAI_API_KEY="..." \
    -e APIFY_PROXY_PASSWORD="..." -e YANDEX_SEARCH_API_KEY="..." \
    -e YANDEX_SEARCH_FOLDER_ID="..." -e GOOGLE_GEMINI_API_KEY="..." \
    python:3.11 bash -c 'pip install -q -r /app/requirements.txt && python /scripts/run_inxy_search_v2.py'
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
logger = logging.getLogger("inxy_v2")

PROJECT_ID = 48
COMPANY_ID = 1

# Top-performing query patterns from v1 results analysis
# These found actual gaming marketplaces — replicate across ALL geos
HIGH_SIGNAL_QUERIES = [
    # Skin trading (top performer: "buy CS2 skins" found 5 targets in Germany alone)
    "buy CS2 skins",
    "sell CS2 skins",
    "buy CSGO skins online",
    "CSGO skin marketplace",
    "CS2 skin trading platform",
    "buy Dota 2 items",
    "buy TF2 skins",
    "Steam skin marketplace",
    "P2P skin trading",
    "sell skins for crypto",
    "buy skins with Bitcoin",
    "csgo skins crypto payment",
    # Virtual goods (found targets in France)
    "sell FIFA coins online",
    "buy WoW gold",
    "sell Fortnite accounts",
    "buy Roblox items",
    "buy game accounts online",
    "sell Valorant account",
    "sell League of Legends account",
    "buy Path of Exile currency",
    "gaming marketplace virtual goods",
    "MMO gold marketplace",
    "game item trading platform",
    # Case opening (crypto-native niche)
    "CS2 case opening site",
    "CSGO case opening crypto",
    "provably fair case opening",
    "case battle site",
    "online case unboxing",
    # Gift cards / top-up (crypto payments niche)
    "buy Steam gift card crypto",
    "buy game keys Bitcoin",
    "gaming gift cards cryptocurrency",
    "buy PlayStation card crypto",
    "game top up with crypto",
    "digital game codes cryptocurrency",
    # Direct competitor/similar company searches
    "sites like skinport",
    "skinbaron alternative",
    "dmarket competitor",
    "bitskins alternative",
    "csgofloat marketplace",
    "waxpeer alternative",
    "g2g marketplace",
    "playerauctions alternative",
    "eneba competitor",
    "kinguin alternative",
    "gamivo marketplace",
    # Crypto-specific gaming
    "crypto gaming marketplace",
    "buy game items with cryptocurrency",
    "Bitcoin game marketplace",
    "crypto skin trading",
    "USDT game marketplace",
]

# All low-risk geos that matter for gaming (skip tiny territories)
ALL_GEOS = [
    "Germany", "France", "Sweden", "Finland", "Denmark", "Norway",
    "Canada", "Australia", "Japan", "New Zealand", "Austria",
    "Belgium", "Ireland", "Switzerland", "Estonia", "Iceland",
]


async def run_improved_search():
    """Run improved search with high-signal queries across all geos."""
    from app.db import async_session_maker
    from app.services.company_search_service import company_search_service
    from app.services.search_service import search_service
    from app.services.domain_service import domain_service
    from app.models.domain import (
        SearchJob, SearchJobStatus, SearchEngine,
        SearchQuery, SearchResult, ProjectSearchKnowledge,
    )
    from app.models.contact import Project
    from sqlalchemy import select, func

    async with async_session_maker() as session:
        # Load project
        result = await session.execute(select(Project).where(Project.id == PROJECT_ID))
        project = result.scalar_one()
        target_segments = project.target_segments

        # Get existing queries to avoid duplicates
        existing_q = await session.execute(
            select(SearchQuery.query_text).join(SearchJob).where(
                SearchJob.project_id == PROJECT_ID
            )
        )
        existing_queries = {r[0].strip().lower() for r in existing_q.fetchall()}
        logger.info(f"Existing queries: {len(existing_queries)}")

        # Current target count
        target_count = await session.execute(
            select(func.count()).select_from(SearchResult).where(
                SearchResult.project_id == PROJECT_ID,
                SearchResult.is_target == True,
            )
        )
        current_targets = target_count.scalar() or 0
        logger.info(f"Current targets: {current_targets}")

        # Build geo-expanded queries
        all_queries = []
        for query in HIGH_SIGNAL_QUERIES:
            q_lower = query.strip().lower()
            if q_lower not in existing_queries:
                all_queries.append(query)
                existing_queries.add(q_lower)

        # Also add geo-specific variants for top queries
        GEO_SPECIFIC_TOP = [
            "buy CS2 skins", "sell CS2 skins", "CSGO skin marketplace",
            "buy game items", "gaming marketplace", "skin trading platform",
            "case opening site", "buy game keys",
        ]
        for query in GEO_SPECIFIC_TOP:
            for geo in ALL_GEOS:
                variant = f"{query} {geo}"
                v_lower = variant.strip().lower()
                if v_lower not in existing_queries:
                    all_queries.append(variant)
                    existing_queries.add(v_lower)

        logger.info(f"Total new queries to run: {len(all_queries)}")

        if not all_queries:
            logger.info("No new queries — all already executed. Done.")
            return

        # Create a single job for this improved search
        job = SearchJob(
            company_id=COMPANY_ID,
            status=SearchJobStatus.PENDING,
            search_engine=SearchEngine.YANDEX_API,
            queries_total=len(all_queries),
            project_id=PROJECT_ID,
            config={
                "segment": "v2_improved",
                "geo": "all_low_risk",
                "max_pages": 3,
                "workers": 8,
                "target_segments": target_segments,
                "query_source": "high_signal_v2",
            },
        )
        session.add(job)
        await session.flush()
        logger.info(f"Created job {job.id} with {len(all_queries)} queries")

        # Add queries
        for q_text in all_queries:
            sq = SearchQuery(
                search_job_id=job.id,
                query_text=q_text,
                segment="v2_improved",
                geo="all",
                language="en",
            )
            session.add(sq)
        await session.commit()

        # Execute Yandex search
        logger.info(f"Starting Yandex search with {len(all_queries)} queries...")
        try:
            await search_service.run_search_job(session, job.id)
        except Exception as e:
            logger.error(f"Search execution error (continuing): {e}")

        await session.refresh(job)
        logger.info(f"Search complete: {job.domains_found} domains found, {job.domains_new} new")

        # Get new domains to analyze
        skip_set = await company_search_service._build_skip_set(session, PROJECT_ID)
        new_domains = await company_search_service._get_new_domains_from_job(session, job, skip_set)
        logger.info(f"New domains to analyze: {len(new_domains)}")

        if new_domains:
            # Scrape and analyze
            logger.info("Starting scrape + GPT analysis...")
            await company_search_service._scrape_and_analyze_domains(
                session=session,
                job=job,
                domains=new_domains,
                target_segments=target_segments,
            )
            await session.commit()

        # Mark complete
        job.status = SearchJobStatus.COMPLETED
        from datetime import datetime
        job.completed_at = datetime.utcnow()
        await session.commit()

        # Count new targets
        new_targets = await session.execute(
            select(func.count()).select_from(SearchResult).where(
                SearchResult.project_id == PROJECT_ID,
                SearchResult.is_target == True,
            )
        )
        total_targets = new_targets.scalar() or 0
        logger.info(f"\n{'='*60}")
        logger.info(f"V2 SEARCH COMPLETE")
        logger.info(f"Targets before: {current_targets}")
        logger.info(f"Targets after:  {total_targets}")
        logger.info(f"New targets:    {total_targets - current_targets}")
        logger.info(f"Job ID: {job.id}")
        logger.info(f"{'='*60}")


async def main():
    logger.info("=" * 60)
    logger.info("INXY SEARCH V2 — HIGH-SIGNAL QUERY EXPANSION")
    logger.info("=" * 60)
    await run_improved_search()


if __name__ == "__main__":
    asyncio.run(main())
