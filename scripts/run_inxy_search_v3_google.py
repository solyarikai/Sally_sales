"""
Inxy search v3 — Two phases:
Phase 1: Complete missing Yandex segment/geo combos (v1 crashed before finishing)
Phase 2: Google SERP with top-performing queries only (validate then scale)
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
logger = logging.getLogger("inxy_v3")

PROJECT_ID = 48
COMPANY_ID = 1

# All segments and their geos from the search config
SEGMENT_GEOS = {
    "skin_marketplaces": [
        "germany", "france", "sweden", "finland", "denmark",
        "canada", "australia", "austria", "switzerland",
    ],
    "case_opening": [
        "germany", "sweden", "finland", "denmark",
        "canada", "australia", "switzerland",
    ],
    "virtual_goods": [
        "germany", "france", "sweden", "canada",
        "australia", "japan", "new_zealand",
    ],
    "topup_giftcards": [
        "germany", "france", "canada", "australia",
        "japan", "switzerland", "austria", "belgium",
    ],
}

# Already searched combos (from v1)
DONE_COMBOS = {
    ("skin_marketplaces", "germany"),
    ("skin_marketplaces", "france"),
    ("case_opening", "germany"),
    ("virtual_goods", "germany"),
    ("virtual_goods", "france"),
    ("topup_giftcards", "germany"),
}

# Top performing Google queries (start small, validate)
GOOGLE_PHASE1_QUERIES = [
    # Proven patterns from v1 Yandex results — test on Google
    "buy CS2 skins",
    "sell CS2 skins",
    "CSGO skin marketplace",
    "buy Dota 2 items",
    "sell FIFA coins online",
    "buy game accounts online",
    "gaming marketplace virtual goods",
    "CS2 case opening site",
    "buy Steam gift card crypto",
    "buy game keys Bitcoin",
    # Competitor searches (high signal — direct alternatives)
    "sites like skinport",
    "skinbaron alternatives",
    "DMarket alternatives",
    "Bitskins alternatives",
    "CSFloat alternatives",
    "Waxpeer alternatives",
    "sites like G2G",
    "PlayerAuctions alternatives",
    "Eneba alternatives",
    "sites like Eldorado.gg",
    "sites like Hellcase",
    "sites like KeyDrop",
    # Crypto specific (highest value for Inxy)
    "buy CS2 skins with crypto",
    "gaming marketplace accepts cryptocurrency",
    "buy game items with Bitcoin",
    "crypto skin trading platform",
]


async def phase1_yandex_remaining():
    """Complete missing Yandex segment/geo combos."""
    from app.db import async_session_maker
    from app.services.company_search_service import company_search_service
    from app.models.domain import SearchEngine

    remaining = []
    for seg, geos in SEGMENT_GEOS.items():
        for geo in geos:
            if (seg, geo) not in DONE_COMBOS:
                remaining.append((seg, geo))

    logger.info(f"Phase 1: {len(remaining)} remaining Yandex segment/geo combos")

    for seg, geo in remaining:
        logger.info(f"\n--- Yandex: {seg}/{geo} ---")
        try:
            async with async_session_maker() as session:
                stats = await company_search_service.run_segment_search(
                    session=session,
                    project_id=PROJECT_ID,
                    company_id=COMPANY_ID,
                    segment_key=seg,
                    geo_key=geo,
                    search_engine=SearchEngine.YANDEX_API,
                    ai_expand_rounds=1,
                    ai_expand_count=20,
                )
                logger.info(
                    f"  {stats.get('targets_found', 0)} targets, "
                    f"{stats.get('domains_found', 0)} domains, "
                    f"{stats.get('total_queries', 0)} queries (job {stats.get('job_id')})"
                )
        except Exception as e:
            logger.error(f"  FAILED: {e}")


async def phase2_google_validate():
    """Run top queries on Google SERP — validate before scaling."""
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

    async with async_session_maker() as session:
        result = await session.execute(select(Project).where(Project.id == PROJECT_ID))
        project = result.scalar_one()
        target_segments = project.target_segments

        # Dedup
        existing_q = await session.execute(
            select(SearchQuery.query_text).join(SearchJob).where(
                SearchJob.project_id == PROJECT_ID
            )
        )
        existing = {r[0].strip().lower() for r in existing_q.fetchall()}

        new_queries = [q for q in GOOGLE_PHASE1_QUERIES if q.strip().lower() not in existing]
        logger.info(f"Phase 2: {len(new_queries)} new Google queries (of {len(GOOGLE_PHASE1_QUERIES)} planned)")

        if not new_queries:
            logger.info("All Google phase 1 queries already done.")
            return 0

        tc = await session.execute(
            select(func.count()).select_from(SearchResult).where(
                SearchResult.project_id == PROJECT_ID, SearchResult.is_target == True
            )
        )
        before = tc.scalar() or 0

        job = SearchJob(
            company_id=COMPANY_ID,
            status=SearchJobStatus.PENDING,
            search_engine=SearchEngine.GOOGLE_SERP,
            queries_total=len(new_queries),
            project_id=PROJECT_ID,
            config={
                "segment": "v3_google",
                "geo": "global",
                "max_pages": 3,
                "workers": 5,
                "target_segments": target_segments,
                "query_source": "google_serp_top_queries",
            },
        )
        session.add(job)
        await session.flush()
        logger.info(f"Created Google job {job.id}")

        for q_text in new_queries:
            sq = SearchQuery(
                search_job_id=job.id,
                query_text=q_text,
                segment="v3_google",
                geo="global",
                language="en",
            )
            session.add(sq)
        await session.commit()

        logger.info("Running Google SERP search...")
        try:
            await search_service.run_search_job(session, job.id)
        except Exception as e:
            logger.error(f"Google search error: {e}")

        await session.refresh(job)
        logger.info(f"Google done: {job.domains_found} domains, {job.domains_new} new")

        skip_set = await company_search_service._build_skip_set(session, PROJECT_ID)
        new_domains = await company_search_service._get_new_domains_from_job(session, job, skip_set)
        logger.info(f"New domains to analyze: {len(new_domains)}")

        if new_domains:
            logger.info("Scraping + analyzing...")
            await company_search_service._scrape_and_analyze_domains(
                session=session,
                job=job,
                domains=new_domains,
                target_segments=target_segments,
            )
            await session.commit()

        job.status = SearchJobStatus.COMPLETED
        job.completed_at = datetime.utcnow()
        await session.commit()

        tc = await session.execute(
            select(func.count()).select_from(SearchResult).where(
                SearchResult.project_id == PROJECT_ID, SearchResult.is_target == True
            )
        )
        after = tc.scalar() or 0
        new_targets = after - before
        logger.info(f"Google phase 1: {new_targets} new targets (before={before}, after={after})")
        return new_targets


async def main():
    logger.info("=" * 60)
    logger.info("INXY SEARCH V3 — COMPLETE COVERAGE + GOOGLE VALIDATION")
    logger.info("=" * 60)

    # Phase 1: Finish all Yandex geos
    logger.info("\n" + "=" * 60)
    logger.info("PHASE 1: YANDEX — Remaining geos")
    logger.info("=" * 60)
    await phase1_yandex_remaining()

    # Phase 2: Google top queries
    logger.info("\n" + "=" * 60)
    logger.info("PHASE 2: GOOGLE SERP — Top queries validation")
    logger.info("=" * 60)
    google_targets = await phase2_google_validate()

    # Final summary
    from app.db import async_session_maker
    from app.models.domain import SearchResult
    from sqlalchemy import select, func
    async with async_session_maker() as session:
        tc = await session.execute(
            select(func.count()).select_from(SearchResult).where(
                SearchResult.project_id == PROJECT_ID, SearchResult.is_target == True
            )
        )
        total = tc.scalar() or 0
        ta = await session.execute(
            select(func.count()).select_from(SearchResult).where(
                SearchResult.project_id == PROJECT_ID
            )
        )
        analyzed = ta.scalar() or 0

    logger.info("\n" + "=" * 60)
    logger.info("V3 COMPLETE — FINAL STATS")
    logger.info(f"Total analyzed: {analyzed}")
    logger.info(f"Total targets:  {total}")
    logger.info(f"Google new targets: {google_targets}")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
