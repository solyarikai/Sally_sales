"""
Inxy domain analysis backlog — Analyze thousands of domains found but never scraped.

V1 found 40,000+ domains across all jobs but only analyzed ~4,700.
This script recovers the rest by scraping and analyzing unprocessed domains.
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
logger = logging.getLogger("inxy_backlog")

PROJECT_ID = 48
COMPANY_ID = 1
BATCH_SIZE = 100  # Domains per analysis batch


async def main():
    from app.db import async_session_maker
    from app.services.company_search_service import company_search_service
    from app.services.domain_service import domain_service
    from app.models.domain import (
        SearchJob, SearchJobStatus, SearchEngine,
        SearchQuery, SearchResult, Domain,
    )
    from app.models.contact import Project
    from sqlalchemy import select, func, text
    from datetime import datetime

    async with async_session_maker() as session:
        # Load project
        result = await session.execute(select(Project).where(Project.id == PROJECT_ID))
        project = result.scalar_one()
        target_segments = project.target_segments

        # Current targets
        tc = await session.execute(
            select(func.count()).select_from(SearchResult).where(
                SearchResult.project_id == PROJECT_ID, SearchResult.is_target == True
            )
        )
        before = tc.scalar() or 0
        logger.info(f"Targets before: {before}")

        # Find all domains discovered by Inxy jobs but NOT yet in search_results
        # The domains table is global; we need domains from queries in Inxy jobs
        all_domains_q = await session.execute(text("""
            SELECT DISTINCT d.domain
            FROM domains d
            WHERE d.status != 'trash'
            AND d.domain NOT IN (
                SELECT sr.domain FROM search_results sr WHERE sr.project_id = :pid
            )
            AND d.domain IN (
                -- Domains found by Inxy search queries
                SELECT DISTINCT unnest(string_to_array(
                    replace(replace(sq.query_text, '"', ''), '''', ''),
                    ' '
                )) FROM search_queries sq
                JOIN search_jobs sj ON sq.search_job_id = sj.id
                WHERE sj.project_id = :pid
            )
            LIMIT 5000
        """), {"pid": PROJECT_ID})

        # Actually, this approach won't work well. Let me use the domain_to_query mapping
        # from job configs, or just get ALL unanalyzed domains from this project's jobs
        pass

    # Better approach: get domains from each job's search results that were found but not analyzed
    async with async_session_maker() as session:
        # Get all job IDs for this project
        jobs_q = await session.execute(
            select(SearchJob.id, SearchJob.domains_found, SearchJob.config).where(
                SearchJob.project_id == PROJECT_ID,
                SearchJob.domains_found > 0,
            )
        )
        jobs = jobs_q.fetchall()

        # Build skip set (already analyzed domains)
        skip_set = await company_search_service._build_skip_set(session, PROJECT_ID)
        logger.info(f"Skip set size: {len(skip_set)}")

        # For each job, get domains that were found but not analyzed
        all_unanalyzed = []
        for job_id, domains_found, config in jobs:
            if not config:
                continue
            domain_to_query = config.get("domain_to_query", {})
            for domain in domain_to_query:
                if domain not in skip_set:
                    all_unanalyzed.append(domain)
                    skip_set.add(domain)  # Prevent duplicates across jobs

        logger.info(f"Unanalyzed domains from job configs: {len(all_unanalyzed)}")

        if not all_unanalyzed:
            # Fallback: query domains table for any domains seen by Inxy that aren't analyzed
            logger.info("Trying alternative: domains from search_queries results...")
            # Get unique domains from ALL search query results for this project
            result = await session.execute(text("""
                WITH job_domains AS (
                    SELECT DISTINCT d.domain
                    FROM domains d
                    WHERE d.status = 'active'
                    AND NOT EXISTS (
                        SELECT 1 FROM search_results sr
                        WHERE sr.project_id = :pid AND sr.domain = d.domain
                    )
                    ORDER BY d.last_seen DESC
                    LIMIT 5000
                )
                SELECT domain FROM job_domains
            """), {"pid": PROJECT_ID})
            all_unanalyzed = [r[0] for r in result.fetchall()]
            logger.info(f"Unanalyzed active domains (global): {len(all_unanalyzed)}")

        if not all_unanalyzed:
            logger.info("No unanalyzed domains found. Done.")
            return

        # Create a recovery job
        job = SearchJob(
            company_id=COMPANY_ID,
            status=SearchJobStatus.PENDING,
            search_engine=SearchEngine.YANDEX_API,
            queries_total=0,
            project_id=PROJECT_ID,
            config={
                "segment": "backlog_recovery",
                "geo": "all",
                "query_source": "domain_backlog",
                "domains_to_analyze": len(all_unanalyzed),
            },
        )
        session.add(job)
        await session.flush()
        logger.info(f"Created recovery job {job.id} for {len(all_unanalyzed)} domains")
        await session.commit()

        # Process in batches
        total_analyzed = 0
        for i in range(0, len(all_unanalyzed), BATCH_SIZE):
            batch = all_unanalyzed[i:i + BATCH_SIZE]
            batch_num = i // BATCH_SIZE + 1
            total_batches = (len(all_unanalyzed) + BATCH_SIZE - 1) // BATCH_SIZE
            logger.info(f"Batch {batch_num}/{total_batches}: analyzing {len(batch)} domains...")

            try:
                await company_search_service._scrape_and_analyze_domains(
                    session=session,
                    job=job,
                    domains=batch,
                    target_segments=target_segments,
                )
                await session.commit()
                total_analyzed += len(batch)

                # Check targets after each batch
                tc = await session.execute(
                    select(func.count()).select_from(SearchResult).where(
                        SearchResult.project_id == PROJECT_ID,
                        SearchResult.is_target == True,
                    )
                )
                current = tc.scalar() or 0
                logger.info(f"  Batch {batch_num} done. Total targets now: {current} (+{current - before})")
            except Exception as e:
                logger.error(f"  Batch {batch_num} error: {e}")
                # Continue with next batch
                continue

        # Finalize
        job.status = SearchJobStatus.COMPLETED
        job.completed_at = datetime.utcnow()
        config = dict(job.config or {})
        config["domains_analyzed"] = total_analyzed
        job.config = config
        await session.commit()

        tc = await session.execute(
            select(func.count()).select_from(SearchResult).where(
                SearchResult.project_id == PROJECT_ID, SearchResult.is_target == True
            )
        )
        after = tc.scalar() or 0

        logger.info(f"\n{'='*60}")
        logger.info(f"BACKLOG RECOVERY COMPLETE")
        logger.info(f"Domains analyzed: {total_analyzed}")
        logger.info(f"Targets before:   {before}")
        logger.info(f"Targets after:    {after}")
        logger.info(f"New targets:      {after - before}")
        logger.info(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
