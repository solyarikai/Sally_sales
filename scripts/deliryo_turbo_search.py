#!/usr/bin/env python3
"""
Deliryo Turbo Search — Optimized pipeline running locally with Hetzner DB.

Runs until 1000 targets found. Optimizations:
- Yandex workers: 20 (up from 8)
- Query batch size: 100 (up from 50)
- Crona batches: 5 parallel (up from 3)
- GPT analysis: 40 concurrent (up from 20)
- Query regeneration from found target companies
- Max iterations: 100 (up from 30)

Usage:
    cd backend && python ../scripts/deliryo_turbo_search.py
"""
import asyncio
import sys
import os
import logging
import signal
from datetime import datetime

# Add backend to path — works both locally and in Docker
_script_dir = os.path.dirname(os.path.abspath(__file__))
_backend_dir = os.path.join(_script_dir, '..', 'backend')
if os.path.isdir(_backend_dir):
    sys.path.insert(0, _backend_dir)
elif os.path.isdir('/app'):
    sys.path.insert(0, '/app')

os.environ.setdefault("SEARCH_WORKERS", "20")
os.environ.setdefault("SEARCH_BATCH_QUERIES", "100")
os.environ.setdefault("SEARCH_MAX_ITERATIONS", "100")
os.environ.setdefault("SEARCH_TARGET_GOAL", "1000")

from app.db import async_session_maker, engine
from app.core.config import settings
from app.models.contact import Project
from app.models.domain import (
    SearchJob, SearchJobStatus, SearchEngine,
    SearchQuery, SearchResult, ProjectSearchKnowledge,
)
from app.services.search_service import search_service
from app.services.company_search_service import company_search_service
from sqlalchemy import select, func

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger("turbo")

# ── Config ────────────────────────────────────────────────────────────

PROJECT_ID = 18
COMPANY_ID = 1
TARGET_GOAL = 1000
MAX_QUERIES_BUDGET = 5000
BATCH_QUERIES = 100
YANDEX_WORKERS = 20
CRONA_BATCH_SIZE = 60
CRONA_PARALLEL = 5
GPT_ANALYSIS_CONCURRENT = 40
GPT_ANALYSIS_BATCH = 40
MAX_ITERATIONS = 100

# Graceful shutdown
shutdown_requested = False

def handle_signal(signum, frame):
    global shutdown_requested
    logger.warning("Shutdown requested, finishing current iteration...")
    shutdown_requested = True

signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)


# ── Monkey-patch concurrency settings ─────────────────────────────────

def patch_concurrency():
    """Override hardcoded concurrency values in the services."""
    import app.services.company_search_service as css_mod

    original_scrape_analyze = css_mod.CompanySearchService._scrape_and_analyze_domains

    async def patched_scrape_and_analyze(self, session, job, domains, target_segments):
        """Patched version with higher concurrency."""
        import asyncio as aio
        from app.services.crona_service import crona_service

        total_tokens = (job.config or {}).get("openai_tokens_used", 0)
        crona_credits_used = 0

        # Filter already-analyzed
        existing_result = await session.execute(
            select(SearchResult.domain).where(
                SearchResult.project_id == job.project_id,
                SearchResult.domain.in_(domains),
            )
        )
        existing_domains = {row[0] for row in existing_result.fetchall()}
        to_analyze = [d for d in domains if d not in existing_domains]

        if not to_analyze:
            return

        logger.info(f"  Scraping {len(to_analyze)} domains (Crona batch={CRONA_BATCH_SIZE}, parallel={CRONA_PARALLEL})")

        # --- Scrape phase ---
        scraped_texts = {}
        used_crona = False

        if crona_service.is_configured:
            crona_semaphore = aio.Semaphore(CRONA_PARALLEL)

            async def scrape_crona_batch(batch):
                async with crona_semaphore:
                    return await crona_service.scrape_domains(batch)

            batches = [to_analyze[i:i + CRONA_BATCH_SIZE] for i in range(0, len(to_analyze), CRONA_BATCH_SIZE)]
            batch_results = await aio.gather(
                *[scrape_crona_batch(b) for b in batches],
                return_exceptions=True,
            )
            for result in batch_results:
                if isinstance(result, dict):
                    scraped_texts.update(result)
                elif isinstance(result, Exception):
                    logger.error(f"  Crona batch failed: {result}")

            crona_credits_used = crona_service.credits_used
            used_crona = True
            logger.info(f"  Crona done: {len(scraped_texts)}/{len(to_analyze)} scraped, credits={crona_credits_used}")
        else:
            # Fallback: direct httpx with more concurrency
            semaphore = aio.Semaphore(10)

            async def scrape_one(domain):
                async with semaphore:
                    html = await self.scrape_domain(domain)
                    scraped_texts[domain] = html

            await aio.gather(*[scrape_one(d) for d in to_analyze], return_exceptions=True)

        scraped_at = datetime.utcnow()
        domain_to_query = (job.config or {}).get("domain_to_query", {})

        # --- Analyze phase: higher concurrency ---
        logger.info(f"  Analyzing {len(to_analyze)} domains (GPT concurrent={GPT_ANALYSIS_CONCURRENT})")
        semaphore = aio.Semaphore(GPT_ANALYSIS_CONCURRENT)

        async def analyze_domain(domain):
            nonlocal total_tokens
            async with semaphore:
                content = scraped_texts.get(domain)
                source_qid = domain_to_query.get(domain)

                if not content or len(content) < 50:
                    sr = SearchResult(
                        search_job_id=job.id,
                        project_id=job.project_id,
                        domain=domain,
                        url=f"https://{domain}",
                        is_target=False,
                        confidence=0,
                        reasoning="Failed to scrape website",
                        scraped_at=scraped_at,
                        source_query_id=source_qid,
                    )
                    session.add(sr)
                    return

                analysis = await self.analyze_company(
                    content, target_segments, domain,
                    is_html=not used_crona,
                )
                analyzed_at = datetime.utcnow()
                total_tokens += analysis.get("tokens_used", 0)

                sr = SearchResult(
                    search_job_id=job.id,
                    project_id=job.project_id,
                    domain=domain,
                    url=f"https://{domain}",
                    is_target=analysis.get("is_target", False),
                    confidence=analysis.get("confidence", 0),
                    reasoning=analysis.get("reasoning", ""),
                    company_info=analysis.get("company_info", {}),
                    scores=analysis.get("scores", {}),
                    html_snippet=content[:2000],
                    scraped_at=scraped_at,
                    analyzed_at=analyzed_at,
                    source_query_id=source_qid,
                )
                session.add(sr)

        # Process in larger batches
        for i in range(0, len(to_analyze), GPT_ANALYSIS_BATCH):
            batch = to_analyze[i:i + GPT_ANALYSIS_BATCH]
            tasks = [analyze_domain(d) for d in batch]
            await aio.gather(*tasks, return_exceptions=True)
            await session.flush()

        # Update job config
        config = dict(job.config or {})
        config["openai_tokens_used"] = total_tokens
        config["crona_credits_used"] = config.get("crona_credits_used", 0) + crona_credits_used
        config["scrape_method"] = "crona" if used_crona else "httpx"
        job.config = config

        # Auto-promote to pipeline
        try:
            from app.services.pipeline_service import pipeline_service
            await pipeline_service.auto_promote_from_search(session, job)
        except Exception as e:
            logger.warning(f"  Auto-promote failed: {e}")

    css_mod.CompanySearchService._scrape_and_analyze_domains = patched_scrape_and_analyze

    # Also patch SEARCH_WORKERS for Yandex
    settings.SEARCH_WORKERS = YANDEX_WORKERS
    settings.SEARCH_BATCH_QUERIES = BATCH_QUERIES
    settings.SEARCH_MAX_ITERATIONS = MAX_ITERATIONS
    settings.SEARCH_TARGET_GOAL = TARGET_GOAL

    logger.info(f"Patched: Yandex workers={YANDEX_WORKERS}, queries/batch={BATCH_QUERIES}, "
                f"Crona batch={CRONA_BATCH_SIZE}/parallel={CRONA_PARALLEL}, "
                f"GPT concurrent={GPT_ANALYSIS_CONCURRENT}")


# ── Main loop ─────────────────────────────────────────────────────────

async def run_turbo_search():
    patch_concurrency()

    async with async_session_maker() as session:
        # Load project
        result = await session.execute(
            select(Project).where(Project.id == PROJECT_ID)
        )
        project = result.scalar_one_or_none()
        if not project:
            logger.error(f"Project {PROJECT_ID} not found!")
            return

        logger.info(f"Project: {project.name} (id={PROJECT_ID})")
        logger.info(f"Target segments: {project.target_segments[:200]}...")

        # Count existing targets
        existing = await company_search_service._count_project_targets(session, PROJECT_ID)
        logger.info(f"Existing targets: {existing}/{TARGET_GOAL}")

        if existing >= TARGET_GOAL:
            logger.info("Target goal already reached!")
            return

        # Create a new search job for this turbo run
        job = SearchJob(
            company_id=COMPANY_ID,
            status=SearchJobStatus.RUNNING,
            search_engine=SearchEngine.YANDEX_API,
            queries_total=0,
            project_id=PROJECT_ID,
            started_at=datetime.utcnow(),
            config={
                "turbo_mode": True,
                "max_queries": MAX_QUERIES_BUDGET,
                "target_goal": TARGET_GOAL,
                "yandex_workers": YANDEX_WORKERS,
                "crona_batch_size": CRONA_BATCH_SIZE,
                "crona_parallel": CRONA_PARALLEL,
                "gpt_concurrent": GPT_ANALYSIS_CONCURRENT,
                "target_segments": project.target_segments,
                "max_pages": settings.SEARCH_MAX_PAGES,
                "openai_tokens_used": 0,
                "queries_generated": 0,
            },
        )
        session.add(job)
        await session.commit()
        logger.info(f"Created turbo search job #{job.id}")

        # Load knowledge
        knowledge_data = await company_search_service._load_project_knowledge(session, PROJECT_ID)
        good_queries = (knowledge_data or {}).get("good_query_patterns", [])
        bad_queries = (knowledge_data or {}).get("bad_query_patterns", [])

        all_used_queries = []
        total_queries_used = 0
        iteration = 0

        # Get confirmed target domains+info for query regeneration
        confirmed_result = await session.execute(
            select(SearchResult.domain, SearchResult.company_info).where(
                SearchResult.project_id == PROJECT_ID,
                SearchResult.is_target == True,
                SearchResult.review_status != "rejected",
            ).limit(100)
        )
        confirmed_target_examples = [row[0] for row in confirmed_result.fetchall()]

        while existing < TARGET_GOAL and iteration < MAX_ITERATIONS and not shutdown_requested:
            iteration += 1
            remaining_budget = MAX_QUERIES_BUDGET - total_queries_used
            batch_size = min(BATCH_QUERIES, remaining_budget)

            if batch_size <= 0:
                logger.info(f"Query budget exhausted ({total_queries_used}/{MAX_QUERIES_BUDGET})")
                break

            logger.info(f"\n{'='*60}")
            logger.info(f"ITERATION {iteration}: {existing}/{TARGET_GOAL} targets, "
                        f"{total_queries_used}/{MAX_QUERIES_BUDGET} queries used")
            logger.info(f"{'='*60}")

            # Generate queries with feedback from confirmed targets
            t0 = datetime.utcnow()
            queries = await search_service.generate_queries(
                session=session,
                count=batch_size,
                model="gpt-4o-mini",
                target_segments=project.target_segments,
                project_id=PROJECT_ID,
                existing_queries=all_used_queries[-500:],  # Keep last 500 to avoid huge prompts
                good_queries=good_queries,
                bad_queries=bad_queries,
                confirmed_targets=confirmed_target_examples[:50],
            )

            if not queries:
                logger.warning("No queries generated, stopping")
                break

            dt_gen = (datetime.utcnow() - t0).total_seconds()
            logger.info(f"  Generated {len(queries)} queries in {dt_gen:.1f}s")

            # Track tokens
            qg_tokens = search_service.last_query_gen_tokens
            config = dict(job.config or {})
            config["query_gen_tokens"] = config.get("query_gen_tokens", 0) + qg_tokens.get("total", 0)

            all_used_queries.extend(queries)
            total_queries_used += len(queries)

            # Update job
            job.queries_total = (job.queries_total or 0) + len(queries)
            config["queries_generated"] = total_queries_used
            config["iteration"] = iteration
            job.config = config

            for q_text in queries:
                sq = SearchQuery(search_job_id=job.id, query_text=q_text)
                session.add(sq)
            await session.commit()

            # Run Yandex search
            t0 = datetime.utcnow()
            logger.info(f"  Running Yandex search ({len(queries)} queries, {YANDEX_WORKERS} workers)...")
            await search_service.run_search_job(session, job.id)
            await session.refresh(job)
            dt_yandex = (datetime.utcnow() - t0).total_seconds()
            logger.info(f"  Yandex done in {dt_yandex:.1f}s — {job.domains_found} domains found, {job.domains_new} new")

            # Get new domains to scrape/analyze
            skip_set = await company_search_service._build_skip_set(session, PROJECT_ID)
            new_domains = await company_search_service._get_new_domains_from_job(session, job, skip_set)
            logger.info(f"  {len(new_domains)} new domains to analyze ({len(skip_set)} in skip set)")

            if new_domains:
                t0 = datetime.utcnow()
                await company_search_service._scrape_and_analyze_domains(
                    session=session,
                    job=job,
                    domains=new_domains,
                    target_segments=project.target_segments,
                )
                dt_analyze = (datetime.utcnow() - t0).total_seconds()
                logger.info(f"  Scrape+analyze done in {dt_analyze:.1f}s")

            await session.commit()

            # Auto-review
            try:
                from app.services.review_service import review_service
                review_stats = await review_service.review_batch(
                    session, job.id, project.target_segments
                )
                await session.commit()
                logger.info(f"  Auto-review: {review_stats}")
            except Exception as e:
                logger.warning(f"  Auto-review failed: {e}")

            # Refresh target count
            existing = await company_search_service._count_project_targets(session, PROJECT_ID)

            # Refresh knowledge + confirmed targets for next iteration
            knowledge_data = await company_search_service._load_project_knowledge(session, PROJECT_ID)
            good_queries = (knowledge_data or {}).get("good_query_patterns", [])
            bad_queries = (knowledge_data or {}).get("bad_query_patterns", [])

            confirmed_result = await session.execute(
                select(SearchResult.domain).where(
                    SearchResult.project_id == PROJECT_ID,
                    SearchResult.is_target == True,
                    SearchResult.review_status != "rejected",
                ).limit(100)
            )
            confirmed_target_examples = [row[0] for row in confirmed_result.fetchall()]

            logger.info(f"  PROGRESS: {existing}/{TARGET_GOAL} targets "
                        f"({len(confirmed_target_examples)} confirmed examples for next query gen)")

        # Mark job complete
        job.status = SearchJobStatus.COMPLETED
        job.completed_at = datetime.utcnow()
        config = dict(job.config or {})
        config["iterations_run"] = iteration
        config["final_targets"] = existing
        config["shutdown_reason"] = (
            "target_reached" if existing >= TARGET_GOAL else
            "shutdown_requested" if shutdown_requested else
            "budget_exhausted" if total_queries_used >= MAX_QUERIES_BUDGET else
            "max_iterations"
        )
        job.config = config
        await session.commit()

        logger.info(f"\n{'='*60}")
        logger.info(f"TURBO SEARCH COMPLETE")
        logger.info(f"  Job: #{job.id}")
        logger.info(f"  Iterations: {iteration}")
        logger.info(f"  Targets: {existing}/{TARGET_GOAL}")
        logger.info(f"  Queries used: {total_queries_used}")
        logger.info(f"  Reason: {config['shutdown_reason']}")
        logger.info(f"{'='*60}")


async def main():
    try:
        await run_turbo_search()
    except Exception as e:
        logger.error(f"Turbo search crashed: {e}", exc_info=True)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
