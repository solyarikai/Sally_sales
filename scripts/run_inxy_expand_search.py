"""
Inxy — MASSIVE expansion search for gaming ICP targets.
1. Yandex: all remaining allowed geos (19 countries)
2. Apollo org: gaming-specific keyword_tags
3. Google SERP: "alternatives to [known target]" pattern
"""
import asyncio
import logging
import os
import sys
from datetime import datetime

sys.path.insert(0, "/app")
os.chdir("/app")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", stream=sys.stdout)
logger = logging.getLogger("inxy_expand")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

PROJECT_ID = 48
COMPANY_ID = 1

# All allowed geos (low risk only, no UK, no US)
ALLOWED_GEOS = [
    "australia", "austria", "belgium", "canada", "denmark", "estonia",
    "finland", "france", "germany", "iceland", "ireland", "japan",
    "liechtenstein", "new zealand", "norway", "sweden", "switzerland",
    "andorra", "san marino",
]

# Already searched geos
DONE_GEOS = {"france", "germany"}

# Gaming-specific search queries
GAMING_QUERIES = [
    # Skin marketplaces
    "buy CS2 skins", "sell CS2 skins", "CS2 skin marketplace",
    "buy CSGO skins", "CSGO skin trading", "CSGO marketplace",
    "buy Rust skins", "Rust skin marketplace",
    "buy Dota 2 items", "Dota 2 marketplace",
    "buy TF2 items", "TF2 trading site",
    # Case opening
    "CS2 case opening site", "CSGO case opening",
    "open cases CS2", "skin case opening",
    # Game items / currency
    "buy game items online", "sell game items",
    "buy FIFA coins", "FIFA coin seller",
    "buy WoW gold", "World of Warcraft gold seller",
    "buy Fortnite accounts", "Fortnite items shop",
    "buy Roblox items", "Roblox trading site",
    "buy game currency online", "game item marketplace",
    "virtual goods marketplace gaming",
    # Boosting
    "game boosting service", "buy game boost",
    # Game keys / top-up
    "game key marketplace", "buy game keys cheap",
    "gaming top up platform", "game gift cards online",
    "Steam gift card buy", "gaming voucher platform",
    # Alternatives to known targets
    "skinport alternative", "skinbaron alternative",
    "DMarket alternative", "CSFloat alternative",
    "Bitskins alternative", "Waxpeer alternative",
    "G2G alternative", "PlayerAuctions alternative",
    "Eldorado.gg alternative", "iGVault alternative",
    "best skin trading sites 2025", "top CSGO marketplaces",
    "best game item marketplaces", "where to buy game skins",
]

# Apollo gaming-specific keyword_tags
APOLLO_GAMING_KEYWORDS = [
    "online gaming", "esports", "video games", "gaming",
    "virtual goods", "e-commerce", "marketplace",
    "digital goods", "in-game items",
]

APOLLO_GAMING_INDUSTRIES = [
    "computer games", "gambling & casinos", "online media",
    "entertainment", "leisure, travel & tourism",
]


async def step1_yandex_new_geos():
    """Run Yandex search for all remaining allowed geos."""
    from app.db import async_session_maker
    from app.services.search_service import search_service
    from app.services.company_search_service import company_search_service
    from app.models.domain import SearchJob, SearchJobStatus, SearchEngine, SearchQuery, SearchResult
    from app.models.contact import Project
    from sqlalchemy import select, func

    new_geos = [g for g in ALLOWED_GEOS if g not in DONE_GEOS]
    logger.info(f"STEP 1: Yandex search for {len(new_geos)} new geos")

    # Select top queries (proven performers)
    TOP_YANDEX_QUERIES = [
        "buy CS2 skins", "sell CS2 skins", "CSGO skins marketplace",
        "buy Rust skins", "buy Dota 2 items", "buy TF2 items",
        "CS2 case opening site", "CSGO case opening",
        "buy game items online", "game item marketplace",
        "buy FIFA coins", "buy WoW gold",
        "buy Roblox items", "buy Fortnite items",
        "virtual goods marketplace gaming",
        "sell game skins online", "skin trading platform",
        "game boosting service", "game key marketplace",
        "buy game accounts online",
    ]

    async with async_session_maker() as session:
        project = (await session.execute(select(Project).where(Project.id == PROJECT_ID))).scalar_one()
        target_segments = project.target_segments

        # Check existing query/geo combos
        existing_q = await session.execute(
            select(SearchQuery.query_text, SearchQuery.geo).join(SearchJob).where(
                SearchJob.project_id == PROJECT_ID,
                SearchJob.search_engine == SearchEngine.YANDEX_API,
            )
        )
        existing_combos = {(r[0].strip().lower(), r[1]) for r in existing_q.fetchall()}
        logger.info(f"Existing Yandex combos: {len(existing_combos)}")

    total_new_targets = 0

    for geo in new_geos:
        queries_for_geo = [
            q for q in TOP_YANDEX_QUERIES
            if (q.strip().lower(), geo) not in existing_combos
        ]
        if not queries_for_geo:
            logger.info(f"  {geo}: all queries done, skip")
            continue

        logger.info(f"\n--- Yandex {geo}: {len(queries_for_geo)} queries ---")

        try:
            async with async_session_maker() as session:
                job = SearchJob(
                    company_id=COMPANY_ID,
                    status=SearchJobStatus.PENDING,
                    search_engine=SearchEngine.YANDEX_API,
                    queries_total=len(queries_for_geo),
                    project_id=PROJECT_ID,
                    config={
                        "segment": "gaming_expansion",
                        "geo": geo,
                        "query_source": "gaming_top_queries",
                    },
                )
                session.add(job)
                await session.flush()

                for q_text in queries_for_geo:
                    sq = SearchQuery(
                        search_job_id=job.id,
                        query_text=q_text,
                        segment="gaming_expansion",
                        geo=geo,
                    )
                    session.add(sq)
                await session.commit()

                job_id = job.id
                logger.info(f"  Job {job_id}, running...")

                try:
                    await search_service.run_search_job(session, job_id)
                except Exception as e:
                    logger.error(f"  Search error: {e}")
                    await session.rollback()

            # Analysis in fresh session
            async with async_session_maker() as session:
                job = (await session.execute(select(SearchJob).where(SearchJob.id == job_id))).scalar_one()
                logger.info(f"  Domains found: {job.domains_found}, new: {job.domains_new}")

                skip_set = await company_search_service._build_skip_set(session, PROJECT_ID)
                new_domains = await company_search_service._get_new_domains_from_job(session, job, skip_set)

                if new_domains:
                    logger.info(f"  Analyzing {len(new_domains)} new domains...")
                    try:
                        await company_search_service._scrape_and_analyze_domains(
                            session=session, job=job, domains=new_domains,
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
                current_targets = tc.scalar() or 0
                logger.info(f"  Total targets now: {current_targets}")

                for q_text in queries_for_geo:
                    existing_combos.add((q_text.strip().lower(), geo))

        except Exception as e:
            logger.error(f"  {geo} FAILED: {e}")
            continue

    return total_new_targets


async def step2_google_alternatives():
    """Google SERP: 'alternatives to [known target]' pattern — highest conversion."""
    from app.db import async_session_maker
    from app.services.search_service import search_service
    from app.services.company_search_service import company_search_service
    from app.models.domain import SearchJob, SearchJobStatus, SearchEngine, SearchQuery, SearchResult
    from app.models.contact import Project
    from sqlalchemy import select, func

    # Known gaming targets to find alternatives for
    KNOWN_TARGETS = [
        "Skinport", "SkinBaron", "DMarket", "CSFloat", "Bitskins",
        "Waxpeer", "CS.Money", "BUFF163", "Hellcase", "KeyDrop",
        "CSGORoll", "CSGOEmpire", "Gamdom", "Clash.gg",
        "G2G", "PlayerAuctions", "Eldorado.gg", "iGVault",
        "SEAGM", "Codashop", "Eneba", "Kinguin",
        "SkinSwap", "TradeIt.gg", "SkinBid",
    ]

    ALT_QUERIES = []
    for target in KNOWN_TARGETS:
        ALT_QUERIES.append(f"{target} alternatives")
        ALT_QUERIES.append(f"sites like {target}")

    # Add general gaming marketplace queries
    ALT_QUERIES.extend([
        "best CS2 skin marketplaces 2025",
        "top game item trading sites",
        "best places to buy game skins",
        "cheapest CS2 skin sites",
        "trusted skin trading platforms",
        "game currency sellers list",
        "where to buy WoW gold safely",
        "best FIFA coin sellers",
        "Roblox item trading platforms",
        "game boosting websites list",
    ])

    SEARCH_CONFIGS = [
        {"gl": "us", "hl": "en"},  # Global English results
        {"gl": "de", "hl": "en"},
        {"gl": "se", "hl": "en"},
    ]

    logger.info(f"STEP 2: Google SERP — {len(ALT_QUERIES)} queries × {len(SEARCH_CONFIGS)} geos")

    async with async_session_maker() as session:
        project = (await session.execute(select(Project).where(Project.id == PROJECT_ID))).scalar_one()
        target_segments = project.target_segments

        existing_q = await session.execute(
            select(SearchQuery.query_text, SearchQuery.geo).join(SearchJob).where(
                SearchJob.project_id == PROJECT_ID,
                SearchJob.search_engine == SearchEngine.GOOGLE_SERP,
            )
        )
        existing_combos = {(r[0].strip().lower(), r[1]) for r in existing_q.fetchall()}

    for config in SEARCH_CONFIGS:
        geo = config["gl"]
        geo_queries = [q for q in ALT_QUERIES if (q.strip().lower(), geo) not in existing_combos]

        if not geo_queries:
            logger.info(f"  Google {geo}: all done, skip")
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
                        "segment": "gaming_alternatives",
                        "geo": geo,
                        "hl": config["hl"],
                    },
                )
                session.add(job)
                await session.flush()

                for q_text in geo_queries:
                    sq = SearchQuery(
                        search_job_id=job.id,
                        query_text=q_text,
                        segment="gaming_alternatives",
                        geo=geo,
                        language=config["hl"],
                    )
                    session.add(sq)
                await session.commit()

                job_id = job.id
                logger.info(f"  Job {job_id}, running...")

                try:
                    await search_service.run_search_job(session, job_id)
                except Exception as e:
                    logger.error(f"  Search error: {e}")
                    await session.rollback()

            async with async_session_maker() as session:
                job = (await session.execute(select(SearchJob).where(SearchJob.id == job_id))).scalar_one()
                logger.info(f"  Domains: {job.domains_found}, new: {job.domains_new}")

                skip_set = await company_search_service._build_skip_set(session, PROJECT_ID)
                new_domains = await company_search_service._get_new_domains_from_job(session, job, skip_set)

                if new_domains:
                    logger.info(f"  Analyzing {len(new_domains)} new domains...")
                    try:
                        await company_search_service._scrape_and_analyze_domains(
                            session=session, job=job, domains=new_domains,
                            target_segments=target_segments,
                        )
                        await session.commit()
                    except Exception as e:
                        logger.error(f"  Analysis error: {e}")
                        await session.rollback()

                job.status = SearchJobStatus.COMPLETED
                job.completed_at = datetime.utcnow()
                await session.commit()

                for q_text in geo_queries:
                    existing_combos.add((q_text.strip().lower(), geo))

        except Exception as e:
            logger.error(f"  Google {geo} FAILED: {e}")
            continue


async def step3_apollo_gaming():
    """Apollo org search with gaming-specific keywords."""
    from app.db import async_session_maker
    from app.services.apollo_service import apollo_service
    from app.services.company_search_service import company_search_service
    from app.models.domain import SearchJob, SearchJobStatus, SearchEngine, SearchResult
    from app.models.pipeline import DiscoveredCompany
    from app.models.contact import Project
    from sqlalchemy import select, func
    import httpx

    logger.info("STEP 3: Apollo org search with gaming keywords")

    # Gaming-specific keyword combos for Apollo
    KEYWORD_COMBOS = [
        ["gaming", "marketplace"],
        ["skins", "trading"],
        ["csgo", "marketplace"],
        ["game items", "marketplace"],
        ["virtual goods"],
        ["case opening"],
        ["game currency"],
        ["game boosting"],
        ["esports", "betting"],
        ["game keys", "marketplace"],
    ]

    APOLLO_INDUSTRIES = [
        "computer games",
        "gambling & casinos",
        "online media",
        "entertainment",
        "internet",
    ]

    async with async_session_maker() as session:
        project = (await session.execute(select(Project).where(Project.id == PROJECT_ID))).scalar_one()
        target_segments = project.target_segments

        # Get existing domains to skip
        existing = await session.execute(
            select(DiscoveredCompany.domain).where(DiscoveredCompany.project_id == PROJECT_ID)
        )
        existing_domains = {r[0] for r in existing.fetchall()}
        logger.info(f"Existing domains in project: {len(existing_domains)}")

    apollo_service.reset_credits()
    all_new_domains = []

    for keywords in KEYWORD_COMBOS:
        for industry in APOLLO_INDUSTRIES[:3]:  # Top 3 industries
            try:
                logger.info(f"  Apollo: keywords={keywords}, industry={industry}")
                results = await apollo_service.search_organizations(
                    keyword_tags=keywords,
                    industry=[industry],
                    page=1,
                    per_page=100,
                )
                if not results:
                    continue

                new_count = 0
                for org in results:
                    domain = org.get("primary_domain") or org.get("website_url", "").replace("https://", "").replace("http://", "").split("/")[0]
                    if not domain or domain in existing_domains:
                        continue
                    existing_domains.add(domain)
                    all_new_domains.append(domain)
                    new_count += 1

                logger.info(f"    Found {len(results)} orgs, {new_count} new domains")

            except Exception as e:
                logger.error(f"    Apollo error: {e}")

    logger.info(f"Apollo total new domains: {len(all_new_domains)}, credits: {apollo_service.credits_used}")

    if all_new_domains:
        # Create a search job and analyze
        async with async_session_maker() as session:
            job = SearchJob(
                company_id=COMPANY_ID,
                status=SearchJobStatus.PENDING,
                search_engine=SearchEngine.GOOGLE_SERP,  # placeholder
                queries_total=0,
                project_id=PROJECT_ID,
                config={
                    "segment": "apollo_gaming_targeted",
                    "apollo_credits": apollo_service.credits_used,
                    "domains_found": len(all_new_domains),
                },
            )
            session.add(job)
            await session.flush()

            logger.info(f"  Analyzing {len(all_new_domains)} Apollo domains...")
            try:
                await company_search_service._scrape_and_analyze_domains(
                    session=session, job=job, domains=all_new_domains,
                    target_segments=target_segments,
                )
                await session.commit()
            except Exception as e:
                logger.error(f"  Analysis error: {e}")
                await session.rollback()

            job.status = SearchJobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            await session.commit()


async def main():
    start = datetime.utcnow()
    logger.info("=" * 60)
    logger.info("INXY — MASSIVE GAMING ICP EXPANSION")
    logger.info("=" * 60)

    from app.db import async_session_maker
    from app.models.domain import SearchResult
    from sqlalchemy import select, func

    async with async_session_maker() as session:
        tc = await session.execute(
            select(func.count()).select_from(SearchResult).where(
                SearchResult.project_id == PROJECT_ID, SearchResult.is_target == True,
            )
        )
        before = tc.scalar() or 0
        logger.info(f"Targets before: {before}")

    await step1_yandex_new_geos()
    await step2_google_alternatives()
    await step3_apollo_gaming()

    async with async_session_maker() as session:
        tc = await session.execute(
            select(func.count()).select_from(SearchResult).where(
                SearchResult.project_id == PROJECT_ID, SearchResult.is_target == True,
            )
        )
        after = tc.scalar() or 0

    elapsed = (datetime.utcnow() - start).total_seconds()
    logger.info("=" * 60)
    logger.info("EXPANSION COMPLETE")
    logger.info(f"Targets before: {before}")
    logger.info(f"Targets after:  {after}")
    logger.info(f"NEW targets:    {after - before}")
    logger.info(f"Time: {elapsed:.0f}s ({elapsed/60:.1f} min)")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
