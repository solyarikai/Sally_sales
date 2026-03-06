"""
Inxy Apollo-powered search — Reverse-engineer Apollo labels from team's known targets,
then use those labels to find hundreds more companies via Apollo org search (free).

Strategy:
1. Enrich team's 87 known domains via Apollo (FREE) to learn keyword_tags + industries
2. Use top keyword_tags to search Apollo for similar companies in low-risk geos
3. Scrape + analyze found domains via existing pipeline
4. Also add team's 87 as confirmed targets in search_results
"""
import asyncio
import logging
import sys
import os
from collections import Counter

sys.path.insert(0, "/app")
os.chdir("/app")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("inxy_apollo")

PROJECT_ID = 48
COMPANY_ID = 1

# Team's confirmed domains from skin_sites_all.xlsx
TEAM_DOMAINS = [
    "avan.market", "bandit.camp", "bitskins.com", "bloodycase.com", "buff163.com",
    "chicken.gg", "clash.gg", "cobaltlab.tech", "cs.deals", "cs.money",
    "cs.trade", "csfloat.com", "csgo.net", "csgo500.com", "csgobig.com",
    "csgodatabase.com", "csgodiamonds.net", "csgoempire.com", "csgofast.com",
    "csgogem.com", "csgold.gg", "csgoluck.com", "csgopolygon.com", "csgoroll.gg",
    "csgoskins.gg", "csgostake.com", "datdrop.com", "dmarket.com", "dota2expert.com",
    "duelbits.com", "farmskins.com", "g4skins.com", "gamblefi.com", "gamdom.com",
    "ggdrop.com", "ggskins.com", "godota2.com", "hellcase.com", "howl.gg",
    "key-drop.com", "loot.farm", "market.csgo.com", "opcases.com", "pirateswap.gg",
    "plunder.gg", "pricempire.com", "rain.gg", "rainbet.com", "rapidskins.com",
    "roobet.com", "rustcasino.com", "rustchance.com", "rustclash.com", "rustly.gg",
    "rustmagic.com", "rustreaper.com", "ruststake.com", "rustypot.com", "rustyloot.gg",
    "sellyourskins.com", "sih.app", "skin.club", "skinbaron.de", "skinbid.com",
    "skincantor.com", "skincashier.com", "skinflow.gg", "skinomat.com", "skinport.com",
    "skinrave.gg", "skins.cash", "skins.com", "skinsmonkey.com", "skinswap.com",
    "snipeskins.com", "stake.com", "steamanalyst.com", "swap.gg", "tf2easy.com",
    "tf2hunt.com", "thunderpick.io", "tradeit.gg", "uuskins.com", "waxpeer.com",
    "white.market", "youpin898.com",
]

# Low-risk geos for Apollo search (country names as Apollo expects)
LOW_RISK_LOCATIONS = [
    "Germany", "France", "Sweden", "Finland", "Denmark", "Norway",
    "Canada", "Australia", "Japan", "New Zealand", "Austria",
    "Belgium", "Ireland", "Switzerland", "Estonia", "Iceland",
    "Andorra", "San Marino", "Liechtenstein",
]


async def phase1_enrich_known_targets():
    """Enrich team's domains via Apollo (FREE) to learn labels."""
    from app.services.apollo_service import apollo_service

    keyword_counter = Counter()
    industry_counter = Counter()
    enriched = 0
    enrichment_data = []

    logger.info(f"Phase 1: Enriching {len(TEAM_DOMAINS)} team domains via Apollo (FREE)...")

    for domain in TEAM_DOMAINS:
        try:
            org = await apollo_service.enrich_organization(domain)
            if org:
                enriched += 1
                name = org.get("name", "")
                keywords = org.get("keywords", []) or []
                industry = org.get("industry", "")
                country = org.get("country", "")

                for kw in keywords:
                    keyword_counter[kw.lower()] += 1
                if industry:
                    industry_counter[industry.lower()] += 1

                enrichment_data.append({
                    "domain": domain,
                    "name": name,
                    "keywords": keywords,
                    "industry": industry,
                    "country": country,
                })

                if enriched % 10 == 0:
                    logger.info(f"  Enriched {enriched}/{len(TEAM_DOMAINS)}...")
            else:
                logger.info(f"  {domain}: not found in Apollo")
        except Exception as e:
            logger.error(f"  {domain}: error: {e}")

    logger.info(f"\nEnriched {enriched}/{len(TEAM_DOMAINS)} domains")
    logger.info(f"\nTop 30 Apollo keyword_tags:")
    for kw, count in keyword_counter.most_common(30):
        logger.info(f"  [{count}x] {kw}")

    logger.info(f"\nTop 15 industries:")
    for ind, count in industry_counter.most_common(15):
        logger.info(f"  [{count}x] {ind}")

    return keyword_counter, industry_counter, enrichment_data


async def phase2_add_team_targets():
    """Add team's 87 domains as confirmed targets in search_results."""
    from app.db import async_session_maker
    from app.models.domain import SearchJob, SearchJobStatus, SearchEngine, SearchResult
    from sqlalchemy import select
    from datetime import datetime

    async with async_session_maker() as session:
        # Check which team domains are already in results
        existing = await session.execute(
            select(SearchResult.domain).where(
                SearchResult.project_id == PROJECT_ID,
                SearchResult.domain.in_(TEAM_DOMAINS),
            )
        )
        existing_domains = {r[0] for r in existing.fetchall()}
        new_domains = [d for d in TEAM_DOMAINS if d not in existing_domains]

        logger.info(f"Phase 2: {len(existing_domains)} already in results, {len(new_domains)} to add")

        if not new_domains:
            return

        # Create a job for the team imports
        job = SearchJob(
            company_id=COMPANY_ID,
            status=SearchJobStatus.COMPLETED,
            search_engine=SearchEngine.YANDEX_API,
            queries_total=0,
            project_id=PROJECT_ID,
            config={
                "segment": "team_manual",
                "geo": "global",
                "query_source": "team_xlsx_import",
                "domains_imported": len(new_domains),
            },
            completed_at=datetime.utcnow(),
        )
        session.add(job)
        await session.flush()

        for domain in new_domains:
            sr = SearchResult(
                search_job_id=job.id,
                project_id=PROJECT_ID,
                domain=domain,
                url=f"https://{domain}",
                is_target=True,
                confidence=1.0,
                reasoning="Confirmed target from team research (skin_sites_all.xlsx)",
                matched_segment="team_confirmed",
                company_info={"source": "team_xlsx"},
                scraped_at=datetime.utcnow(),
                analyzed_at=datetime.utcnow(),
            )
            session.add(sr)

        await session.commit()
        logger.info(f"Added {len(new_domains)} team targets (job {job.id})")


async def phase3_apollo_org_search(top_keywords: Counter):
    """Use top Apollo keywords to find similar companies in low-risk geos."""
    from app.db import async_session_maker
    from app.services.apollo_service import apollo_service
    from app.services.company_search_service import company_search_service
    from app.models.domain import (
        SearchJob, SearchJobStatus, SearchEngine, SearchResult,
    )
    from app.models.contact import Project
    from sqlalchemy import select, func
    from datetime import datetime

    # Build keyword groups from enrichment data
    # Use the most common keywords found across team's targets
    keyword_groups = []
    top_kws = [kw for kw, count in top_keywords.most_common(20) if count >= 2]

    if not top_kws:
        # Fallback to manual keywords
        top_kws = [
            "gaming", "esports", "video games", "online gaming",
            "skin", "marketplace", "trading", "virtual goods",
            "case opening", "gambling", "crypto", "game items",
        ]

    # Search Apollo with keyword combinations × geos
    logger.info(f"Phase 3: Apollo org search with {len(top_kws)} keywords across {len(LOW_RISK_LOCATIONS)} geos")

    all_found_domains = set()

    # Group keywords into batches of 3-4 for more targeted search
    kw_batches = []
    for i in range(0, len(top_kws), 3):
        batch = top_kws[i:i+3]
        if batch:
            kw_batches.append(batch)

    for kw_batch in kw_batches:
        for location in LOW_RISK_LOCATIONS:
            logger.info(f"  Apollo search: keywords={kw_batch}, location={location}")
            try:
                orgs = await apollo_service.search_organizations_all_pages(
                    keyword_tags=kw_batch,
                    locations=[location],
                    max_pages=5,
                    per_page=100,
                )
                for org in orgs:
                    domain = org.get("primary_domain") or ""
                    if domain and "." in domain:
                        all_found_domains.add(domain.lower())

                if orgs:
                    logger.info(f"    Found {len(orgs)} orgs")
            except Exception as e:
                logger.error(f"    Error: {e}")

    logger.info(f"\nApollo found {len(all_found_domains)} unique domains total")

    if not all_found_domains:
        return

    # Filter out already-analyzed and analyze new ones
    async with async_session_maker() as session:
        result = await session.execute(select(Project).where(Project.id == PROJECT_ID))
        project = result.scalar_one()

        skip_set = await company_search_service._build_skip_set(session, PROJECT_ID)
        new_domains = [d for d in all_found_domains if d not in skip_set]
        logger.info(f"New domains to analyze: {len(new_domains)} (of {len(all_found_domains)} found)")

        if not new_domains:
            logger.info("All Apollo domains already analyzed.")
            return

        tc = await session.execute(
            select(func.count()).select_from(SearchResult).where(
                SearchResult.project_id == PROJECT_ID, SearchResult.is_target == True
            )
        )
        before = tc.scalar() or 0

        # Create Apollo search job
        job = SearchJob(
            company_id=COMPANY_ID,
            status=SearchJobStatus.PENDING,
            search_engine=SearchEngine.YANDEX_API,  # Using YANDEX as placeholder
            queries_total=0,
            domains_found=len(new_domains),
            domains_new=len(new_domains),
            project_id=PROJECT_ID,
            config={
                "segment": "apollo_org_search",
                "geo": "low_risk",
                "query_source": "apollo_keywords",
                "keywords_used": top_kws[:10],
                "total_apollo_domains": len(all_found_domains),
            },
        )
        session.add(job)
        await session.flush()
        logger.info(f"Created Apollo job {job.id}")
        await session.commit()

        # Scrape and analyze in batches
        BATCH = 100
        for i in range(0, len(new_domains), BATCH):
            batch = new_domains[i:i + BATCH]
            batch_num = i // BATCH + 1
            logger.info(f"Analyzing batch {batch_num}: {len(batch)} domains...")
            try:
                await company_search_service._scrape_and_analyze_domains(
                    session=session,
                    job=job,
                    domains=batch,
                    target_segments=project.target_segments,
                )
                await session.commit()
            except Exception as e:
                logger.error(f"Batch {batch_num} error: {e}")

        job.status = SearchJobStatus.COMPLETED
        job.completed_at = datetime.utcnow()
        await session.commit()

        tc = await session.execute(
            select(func.count()).select_from(SearchResult).where(
                SearchResult.project_id == PROJECT_ID, SearchResult.is_target == True
            )
        )
        after = tc.scalar() or 0
        logger.info(f"Apollo search: {after - before} new targets (before={before}, after={after})")


async def main():
    from app.db import async_session_maker
    from app.models.domain import SearchResult
    from sqlalchemy import select, func

    logger.info("=" * 60)
    logger.info("INXY APOLLO-POWERED SEARCH")
    logger.info("=" * 60)

    # Phase 1: Enrich known targets
    top_keywords, top_industries, enrichment_data = await phase1_enrich_known_targets()

    # Phase 2: Add team targets to DB
    await phase2_add_team_targets()

    # Phase 3: Apollo org search for similar companies
    await phase3_apollo_org_search(top_keywords)

    # Final stats
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

    logger.info(f"\n{'='*60}")
    logger.info(f"FINAL STATS")
    logger.info(f"Total analyzed: {analyzed}")
    logger.info(f"Total targets:  {total}")
    logger.info(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
