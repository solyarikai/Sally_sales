"""
Add OnSocial paid clients as blacklist and generate lookalike queries.

1. Blacklists 191 client domains in discovered_companies
2. Builds lookalike queries: company names from clients as search seeds
"""
import asyncio
import json
import logging
import sys
import os

sys.path.insert(0, "/app")
os.chdir("/app")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ID = 42
COMPANY_ID = 1

# OnSocial paid clients — BLACKLIST (do not target)
CLIENT_DOMAINS = [
    "sevenpeaks.no", "ultraviolet.club", "suits.ai", "trytano.com",
    "houseofmarketers.com", "influencers.club", "anymindgroup.com", "trafmasters.com",
    "bardar.app", "influur.com", "mymeadow.ai", "refluenced.com",
    "styledoubler.com", "hashgifted.com", "simple.app", "oddity.com",
    "unboxsocial.com", "out2win.io", "bloggers.tools", "culturex.in",
    "emw-global.com", "devotion.club", "pearpop.com", "bulk.com",
    "bossmgmtgrp.com", "ecomx.io", "linkster.co", "blindcreator.com",
    "imagen-ai.com", "codefree.io", "airstrip.com.br", "oml.in",
    "ai-fluence.com", "assaabloy.com", "socialpubli.com", "reflexgroup.com",
    "sheer.dk", "mieladigital.com", "changenow.io", "brandinfluency.com",
    "enfluenso.com", "pepperagency.com", "vamp.me", "impactify.ae",
    "southnext.com", "eleve.co.in", "icubeswire.com", "ikala.ai",
    "zeroto1.co", "nordicinfluencermarketing.com", "tcf.team",
    "advy.ai", "halomediaagency.com", "umusic.com", "agency-eight.com",
    "connectmgt.com", "narrativegroup.co", "yoloco.io", "upfluence.com",
    "joinmavely.com", "dreamwell.ai", "holzkern.com", "grin.co",
    "n1.partners", "buzzbassador.com", "double.global", "squad.app",
    "skorr.social", "lunyone.de", "blanklabel.team", "insense.me",
    "influence-me.de", "1xbet-team.com", "viralpitch.co", "tiege.com",
    "uniting.it", "aspire.io", "enskai.com", "heylinkme.co",
    "getfluence.co", "influencer.in", "billo.app", "mms.group",
    "eqolot.com", "keepface.com", "amiyah.in", "metaone.gg",
    "accrueperformance.co.uk", "sideqik.com", "captiv8.io", "hbagency.co",
    "7senders.com", "wowzi.co", "lottiefiles.com", "thehypeagency.co",
    "ampjar.com", "zoomph.com", "the5thcolumn.agency", "storipress.com",
    "starfuel.io", "trybe.one", "wob.ag", "smartocto.com",
    "socialpeeks.com", "buzzstream.com", "kolsquare.com", "gigapay.co",
    "thecircularlab.com", "hashtagpaid.com", "taplio.com", "joinshares.com",
    "vidiq.com", "socialcat.com", "brandbassador.com", "advocu.com",
    "sparkle.io", "tagger.com", "socialladder.com", "phlanx.com",
    "boostiny.com", "fohr.co", "clevertap.com", "lefty.io",
    "heepsy.com", "juliusworks.com", "linqia.com", "modash.io",
    "creatoriq.com", "traackr.com", "neoreach.com", "popular-pays.com",
    "socialnative.com", "activate.social", "mavrck.co", "later.com",
    "klear.com", "kitly.com", "affable.ai", "dovetale.com",
    "influencity.com", "ifluenz.com", "hypr.co", "inbeat.co",
    "impulze.ai", "influencer.com", "marketingforce.com", "webfluential.com",
    "reachbird.io", "scrunch.com", "tinysponsor.com", "whalar.com",
    "theinfluenceroom.com", "wearesocial.com", "obviously.com",
    "viral-nation.com", "goat-agency.com", "theshelfrz.com",
    "openinfluence.com", "mediakix.com", "izea.com", "takumi.com",
    "collectively.inc", "fanbytes.co.uk", "billion-dollar-boy.com",
    "thesoul-publishing.com", "kairos-media.com", "buttermilk.agency",
    "digitalvoices.com", "socially-powerful.com", "disruptiveadvertising.com",
    "moburst.com", "neoreach.com", "meltwater.com", "mention.com",
    "sproutsocial.com", "brandwatch.com", "hootsuite.com", "agorapulse.com",
    "buffer.com", "socialbakers.com", "emplifi.io", "dash-hudson.com",
    "sprinklr.com",
]

# Lookalike query seeds: names of actual OnSocial clients → find similar companies
LOOKALIKE_QUERIES_EN = [
    # Based on client domain patterns — what they ARE
    "influencer marketing agency",
    "influencer marketing platform",
    "creator economy startup",
    "UGC agency",
    "influencer management platform",
    "social media influencer tool",
    "brand ambassador platform",
    "influencer CRM",
    "creator marketplace",
    "influencer analytics SaaS",
    # Competitor-style queries
    "companies like Grin influencer",
    "alternatives to Upfluence",
    "alternatives to AspireIQ",
    "alternatives to CreatorIQ",
    "alternatives to Traackr",
    "alternatives to Modash",
    "alternatives to Heepsy",
    "alternatives to Kolsquare",
    "influencer platform comparison",
    "top influencer marketing tools 2024",
    "best influencer marketing agencies 2024",
    "influencer marketing agency directory",
    "list of influencer agencies",
    "influencer marketing companies list",
    # Geo-specific
    "influencer agency Spain",
    "influencer agency Poland",
    "influencer agency Nordic",
    "influencer agency Sweden",
    "influencer agency Latin America",
    "influencer agency Mexico",
    "influencer agency Brazil",
    "influencer agency India",
    "influencer agency Germany",
    "influencer agency UK",
    "influencer agency France",
    "influencer agency Italy",
    "UGC agency USA",
    "UGC agency Europe",
    "creator agency New York",
    "creator agency Los Angeles",
    # Industry directories / lists
    "influencer marketing hub agencies list",
    "clutch influencer marketing agencies",
    "G2 influencer marketing platforms",
    "capterra influencer marketing",
    "influencer marketing agency awards",
    "social media marketing agencies ranking",
]


async def blacklist_clients():
    """Add client domains to ProjectBlacklist and un-target in discovered_companies."""
    from app.db import async_session_maker
    from sqlalchemy import text

    async with async_session_maker() as session:
        # 1. Add to ProjectBlacklist (per-project, prevents re-scoring)
        added = 0
        for domain in CLIENT_DOMAINS:
            result = await session.execute(text("""
                INSERT INTO project_blacklist (project_id, domain, reason, source)
                VALUES (:pid, :domain, 'OnSocial paid client', 'manual')
                ON CONFLICT (project_id, domain) DO NOTHING
            """), {"pid": PROJECT_ID, "domain": domain})
            if result.rowcount > 0:
                added += 1
        logger.info(f"Added {added} new domains to project_blacklist (of {len(CLIENT_DOMAINS)} total)")

        # 2. Un-target any that were discovered as targets
        result = await session.execute(text("""
            UPDATE discovered_companies
            SET is_target = false, confidence = 0
            WHERE project_id = :pid AND domain = ANY(:domains) AND is_target = true
        """), {"pid": PROJECT_ID, "domains": CLIENT_DOMAINS})
        logger.info(f"Un-targeted {result.rowcount} client domains in discovered_companies")

        await session.commit()


async def launch_lookalike_search():
    """Launch lookalike search with Google SERP, then score and promote."""
    from app.db import async_session_maker
    from app.models.domain import SearchJob, SearchJobStatus, SearchEngine, SearchQuery
    from app.models.contact import Project
    from app.services.search_service import search_service
    from app.services.company_search_service import company_search_service
    from sqlalchemy import select

    async with async_session_maker() as session:
        # Load project
        proj_result = await session.execute(select(Project).where(Project.id == PROJECT_ID))
        project = proj_result.scalar_one()

        job = SearchJob(
            company_id=COMPANY_ID,
            project_id=PROJECT_ID,
            status=SearchJobStatus.PENDING,
            search_engine=SearchEngine.GOOGLE_SERP,
            queries_total=len(LOOKALIKE_QUERIES_EN),
            config={
                "type": "lookalike",
                "source": "onsocial_paid_clients",
                "max_pages": 3,
                "workers": 8,
                "target_segments": project.target_segments,
            },
        )
        session.add(job)
        await session.flush()

        for q_text in LOOKALIKE_QUERIES_EN:
            sq = SearchQuery(
                search_job_id=job.id,
                query_text=q_text,
            )
            session.add(sq)

        await session.commit()
        logger.info(f"Created lookalike search job {job.id} with {len(LOOKALIKE_QUERIES_EN)} queries")

        # Run the search
        await search_service.run_search_job(session, job.id)
        await session.refresh(job)
        logger.info(f"Search done: {job.domains_found} domains found")

        # Score new domains
        skip_set = await company_search_service._build_skip_set(session, PROJECT_ID)
        new_domains = await company_search_service._get_new_domains_from_job(session, job, skip_set)
        logger.info(f"New domains to score: {len(new_domains)}")

        if new_domains:
            await company_search_service._scrape_and_analyze_domains(
                session=session,
                job=job,
                domains=new_domains,
                target_segments=project.target_segments,
            )
            await session.commit()

        # Count targets
        from app.models.domain import SearchResult
        from sqlalchemy import func
        target_count = await session.execute(
            select(func.count()).select_from(SearchResult).where(
                SearchResult.search_job_id == job.id,
                SearchResult.is_target == True,
            )
        )
        targets = target_count.scalar() or 0
        logger.info(f"Lookalike search: {len(LOOKALIKE_QUERIES_EN)} queries → {job.domains_found} domains → {targets} targets")


async def main():
    logger.info("=== OnSocial: Blacklist clients + Lookalike search ===")
    await blacklist_clients()
    await launch_lookalike_search()
    logger.info("Done!")


if __name__ == "__main__":
    asyncio.run(main())
