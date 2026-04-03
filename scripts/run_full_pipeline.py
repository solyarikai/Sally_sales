#!/usr/bin/env python3
"""
Full Data Gathering Pipeline — reusable for any project.
=========================================================

Phases:
  1. Parallel Yandex + Google SERP search (iterative, with query feedback)
  2. Website contact extraction (GPT + regex on scraped HTML)
  3. Apollo people enrichment (1 credit/person, never re-enriches)

Search engines: Yandex + Google always. Apollo search opt-in via --apollo-search.
Apollo enrichment for target companies always runs (dedup guards prevent waste).

Usage:
  python run_full_pipeline.py --project-id 18 --max-queries 1500 --target-goal 2000 --apollo-credits 500

Docker:
  docker run -d --name pipeline-PROJECT --network repo_default \\
    --restart unless-stopped \\
    -v ~/magnum-opus-project/repo/backend:/app \\
    -v ~/magnum-opus-project/repo/scripts:/scripts \\
    -v ~/magnum-opus-project/repo/google-credentials.json:/app/google-credentials.json:ro \\
    -e DATABASE_URL=postgresql+asyncpg://leadgen:leadgen_secret@postgres:5432/leadgen \\
    -e OPENAI_API_KEY=... \\
    -e YANDEX_SEARCH_API_KEY=... -e YANDEX_SEARCH_FOLDER_ID=... \\
    -e CRONA_EMAIL=... -e CRONA_PASSWORD=... \\
    -e APOLLO_API_KEY=... \\
    -e APIFY_PROXY_PASSWORD=... \\
    -e GOOGLE_APPLICATION_CREDENTIALS=/app/google-credentials.json \\
    python:3.11 bash -c 'pip install -q -r /app/requirements.txt && python /scripts/run_full_pipeline.py --project-id 18'
"""
import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime

sys.path.insert(0, "/app")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
os.environ.setdefault("DATABASE_URL", os.environ.get("DATABASE_URL", ""))

if not os.environ.get("APIFY_PROXY_PASSWORD"):
    os.environ["APIFY_PROXY_PASSWORD"] = "apify_proxy_zZ12PNY7illL44MXT8Cf3vKetkI5I62Oupn2"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("full_pipeline")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

COMPANY_ID = 1  # Single-tenant for now


def parse_args():
    p = argparse.ArgumentParser(description="Full data gathering pipeline")
    p.add_argument("--project-id", type=int, required=True, help="Project ID to run pipeline for")
    p.add_argument("--max-queries", type=int, default=1500, help="Max search queries per engine (default: 1500)")
    p.add_argument("--target-goal", type=int, default=2000, help="Target companies goal (search stops on stall anyway)")
    p.add_argument("--apollo-search", action="store_true", default=False,
                   help="Also use Apollo as a search engine (costs credits, off by default)")
    p.add_argument("--apollo-credits", type=int, default=500, help="Max Apollo credits for enrichment (default: 500)")
    p.add_argument("--apollo-max-people", type=int, default=5, help="Max people per domain in Apollo enrichment (default: 5)")
    p.add_argument("--apollo-titles", nargs="*", default=["CEO", "Founder", "Managing Director", "Partner", "Head of Business Development"],
                   help="Job title filter for Apollo enrichment")
    p.add_argument("--skip-search", action="store_true", default=False, help="Skip search phase, only run extraction + enrichment")
    p.add_argument("--skip-extraction", action="store_true", default=False, help="Skip website contact extraction")
    p.add_argument("--skip-enrichment", action="store_true", default=False, help="Skip Apollo enrichment")
    p.add_argument("--export-sheet", action="store_true", default=False, help="Export results to Google Sheet after pipeline")
    return p.parse_args()


async def phase_search(project_id: int, max_queries: int, target_goal: int, apollo_search: bool):
    """Phase 1: Parallel search via Yandex + Google SERP (+ optional Apollo)."""
    from app.db import async_session_maker
    from app.models.domain import SearchEngine
    from app.services.company_search_service import company_search_service

    async with async_session_maker() as session:
        targets_before = await company_search_service._count_project_targets(session, project_id)
    logger.info(f"Targets before search: {targets_before}")

    # Build engine list
    engines = [
        ("Yandex", SearchEngine.YANDEX_API),
        ("Google SERP", SearchEngine.GOOGLE_SERP),
    ]
    if apollo_search:
        engines.append(("Apollo", SearchEngine.APOLLO))

    async def run_engine(name: str, engine: SearchEngine):
        logger.info(f"[{name}] Starting search (max_queries={max_queries}, target_goal={target_goal})")
        try:
            async with async_session_maker() as session:
                job = await company_search_service.run_project_search(
                    session=session,
                    project_id=project_id,
                    company_id=COMPANY_ID,
                    max_queries=max_queries,
                    target_goal=target_goal,
                    search_engine=engine,
                )
                targets_after = await company_search_service._count_project_targets(session, project_id)
            config = job.config or {}
            logger.info(f"[{name}] DONE — job #{job.id}, status={job.status}, "
                        f"queries={config.get('queries_generated', '?')}, "
                        f"iterations={config.get('iterations_run', '?')}, "
                        f"targets now={targets_after}")
            return name, job, targets_after
        except Exception as e:
            logger.error(f"[{name}] FAILED: {e}", exc_info=True)
            return name, None, targets_before

    # Run all engines in parallel
    logger.info("=" * 70)
    logger.info(f"PARALLEL SEARCH: {', '.join(n for n, _ in engines)}")
    logger.info(f"max_queries={max_queries} each, target_goal={target_goal}")
    logger.info("=" * 70)

    results = await asyncio.gather(*[run_engine(name, eng) for name, eng in engines])

    # Find final target count (max across engines, since they share the same project)
    targets_after = max(r[2] for r in results) if results else targets_before
    new_targets = targets_after - targets_before

    logger.info("")
    logger.info("=" * 70)
    logger.info("SEARCH COMPLETE")
    logger.info(f"  Targets before: {targets_before}")
    logger.info(f"  Targets after:  {targets_after} (+{new_targets} new)")
    for name, job, count in results:
        if job:
            cfg = job.config or {}
            logger.info(f"  [{name}] job #{job.id}: {cfg.get('queries_generated', '?')} queries, "
                        f"{cfg.get('iterations_run', '?')} iterations")
        else:
            logger.info(f"  [{name}] FAILED")
    logger.info("=" * 70)

    return targets_before, targets_after


async def phase_extract_contacts(project_id: int):
    """Phase 2: Extract contacts from target company websites."""
    from sqlalchemy import select, or_
    from app.db import async_session_maker
    from app.models.pipeline import DiscoveredCompany
    from app.services.pipeline_service import pipeline_service

    async with async_session_maker() as session:
        result = await session.execute(
            select(DiscoveredCompany.id).where(
                DiscoveredCompany.project_id == project_id,
                DiscoveredCompany.company_id == COMPANY_ID,
                DiscoveredCompany.is_target == True,
                or_(
                    DiscoveredCompany.contacts_count == 0,
                    DiscoveredCompany.contacts_count.is_(None),
                ),
            )
        )
        ids = [r[0] for r in result.fetchall()]

    if not ids:
        logger.info("No targets need website contact extraction — all already extracted")
        return {"processed": 0, "contacts_found": 0, "errors": 0, "skipped": 0}

    logger.info("=" * 70)
    logger.info(f"WEBSITE CONTACT EXTRACTION: {len(ids)} targets")
    logger.info("=" * 70)

    BATCH = 20
    total_stats = {"processed": 0, "contacts_found": 0, "errors": 0, "skipped": 0}

    for i in range(0, len(ids), BATCH):
        batch_ids = ids[i:i + BATCH]
        batch_num = i // BATCH + 1
        total_batches = (len(ids) + BATCH - 1) // BATCH

        try:
            async with async_session_maker() as session:
                stats = await pipeline_service.extract_contacts_batch(
                    session, batch_ids, company_id=COMPANY_ID
                )
            total_stats["processed"] += stats.get("processed", 0)
            total_stats["contacts_found"] += stats.get("contacts_found", 0)
            total_stats["errors"] += stats.get("errors", 0)
            total_stats["skipped"] += stats.get("skipped", 0)
            logger.info(f"  Batch {batch_num}/{total_batches}: +{stats.get('contacts_found', 0)} contacts "
                        f"(total so far: {total_stats['contacts_found']})")
        except Exception as e:
            logger.error(f"  Batch {batch_num}/{total_batches} FAILED: {e}", exc_info=True)
            total_stats["errors"] += len(batch_ids)

    logger.info(f"EXTRACTION COMPLETE: {total_stats}")
    return total_stats


async def phase_apollo_enrichment(project_id: int, max_credits: int, max_people: int, titles: list):
    """Phase 3: Apollo people enrichment for target companies."""
    from sqlalchemy import select
    from app.db import async_session_maker
    from app.models.pipeline import DiscoveredCompany
    from app.services.pipeline_service import pipeline_service
    from app.services.apollo_service import apollo_service

    async with async_session_maker() as session:
        result = await session.execute(
            select(DiscoveredCompany.id).where(
                DiscoveredCompany.project_id == project_id,
                DiscoveredCompany.company_id == COMPANY_ID,
                DiscoveredCompany.is_target == True,
                DiscoveredCompany.apollo_enriched_at.is_(None),
            ).order_by(DiscoveredCompany.confidence.desc())
        )
        ids = [r[0] for r in result.fetchall()]

    if not ids:
        logger.info("No targets need Apollo enrichment — all already enriched")
        return {"processed": 0, "people_found": 0, "credits_used": 0, "errors": 0, "skipped": 0}

    if not apollo_service.is_configured():
        logger.warning("Apollo API key not configured — skipping enrichment")
        return {"processed": 0, "people_found": 0, "credits_used": 0, "errors": 0, "skipped": len(ids)}

    logger.info("=" * 70)
    logger.info(f"APOLLO ENRICHMENT: {len(ids)} unenriched targets")
    logger.info(f"  max_people={max_people}, max_credits={max_credits}")
    logger.info(f"  titles={titles}")
    logger.info("=" * 70)

    BATCH = 10
    total_stats = {"processed": 0, "people_found": 0, "credits_used": 0, "errors": 0, "skipped": 0}

    for i in range(0, len(ids), BATCH):
        batch_ids = ids[i:i + BATCH]
        batch_num = i // BATCH + 1
        total_batches = (len(ids) + BATCH - 1) // BATCH

        # Enforce overall credit budget
        remaining_credits = max_credits - total_stats["credits_used"]
        if remaining_credits <= 0:
            logger.info(f"  Credit budget exhausted ({max_credits}), stopping at batch {batch_num}")
            break

        try:
            async with async_session_maker() as session:
                stats = await pipeline_service.enrich_apollo_batch(
                    session, batch_ids, company_id=COMPANY_ID,
                    max_people=max_people,
                    max_credits=remaining_credits,
                    titles=titles if titles else None,
                )
            total_stats["processed"] += stats.get("processed", 0)
            total_stats["people_found"] += stats.get("people_found", 0)
            total_stats["credits_used"] += stats.get("credits_used", 0)
            total_stats["errors"] += stats.get("errors", 0)
            total_stats["skipped"] += stats.get("skipped", 0)
            logger.info(f"  Batch {batch_num}/{total_batches}: +{stats.get('people_found', 0)} people, "
                        f"+{stats.get('credits_used', 0)} credits "
                        f"(total: {total_stats['people_found']} people, {total_stats['credits_used']} credits)")
        except Exception as e:
            logger.error(f"  Batch {batch_num}/{total_batches} FAILED: {e}", exc_info=True)
            total_stats["errors"] += len(batch_ids)

    logger.info(f"APOLLO ENRICHMENT COMPLETE: {total_stats}")
    return total_stats


async def phase_export(project_id: int):
    """Export results to Google Sheet."""
    from app.db import async_session_maker
    from app.services.google_sheets_service import google_sheets_service
    from sqlalchemy import text

    if not google_sheets_service.is_configured():
        logger.warning("Google Sheets not configured — skipping export")
        return None

    async with async_session_maker() as session:
        # Use the contacts export query from pipeline API
        rows = (await session.execute(text("""
            SELECT dc.domain, dc.confidence, dc.company_info,
                   dc.apollo_people_count, dc.apollo_enriched_at,
                   dc.contacts_count, dc.scraped_at,
                   CAST(dc.status AS text) as status
            FROM discovered_companies dc
            WHERE dc.project_id = :project_id AND dc.is_target = true
            ORDER BY dc.confidence DESC NULLS LAST
        """), {"project_id": project_id})).fetchall()

    if not rows:
        logger.info("No targets to export")
        return None

    import json
    headers = ["Domain", "Website", "Company Name", "Industry", "Location",
               "Confidence", "Contacts", "Apollo People", "Status"]
    sheet_rows = [headers]
    for r in rows:
        ci = r.company_info or {}
        if isinstance(ci, str):
            try:
                ci = json.loads(ci)
            except Exception:
                ci = {}
        sheet_rows.append([
            r.domain,
            f"https://{r.domain}",
            ci.get("name", ""),
            ci.get("industry", ""),
            ci.get("location", ""),
            f"{(r.confidence or 0) * 100:.0f}%",
            r.contacts_count or 0,
            r.apollo_people_count or 0,
            r.status or "",
        ])

    sheet_url = google_sheets_service.create_and_populate(
        title=f"Pipeline Export — Project {project_id} — {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
        data=sheet_rows,
        share_with=["pn@getsally.io"],
    )
    if sheet_url:
        logger.info(f"Exported to Google Sheet: {sheet_url}")
    return sheet_url


async def print_summary(project_id: int):
    """Print final summary stats."""
    from sqlalchemy import text
    from app.db import async_session_maker

    async with async_session_maker() as session:
        r = (await session.execute(text("""
            SELECT
                COUNT(*) as total_targets,
                COUNT(*) FILTER (WHERE contacts_count > 0) as with_contacts,
                COUNT(*) FILTER (WHERE apollo_enriched_at IS NOT NULL) as apollo_done,
                SUM(COALESCE(apollo_credits_used, 0)) as total_credits,
                SUM(COALESCE(apollo_people_count, 0)) as total_people,
                SUM(COALESCE(contacts_count, 0)) as total_contacts
            FROM discovered_companies
            WHERE project_id = :pid AND is_target = true
        """), {"pid": project_id})).fetchone()

    logger.info("")
    logger.info("=" * 70)
    logger.info(f"PIPELINE SUMMARY — Project {project_id}")
    logger.info("=" * 70)
    logger.info(f"  Target companies:       {r[0]}")
    logger.info(f"  With website contacts:  {r[1]}")
    logger.info(f"  Apollo enriched:        {r[2]}")
    logger.info(f"  Total contacts:         {r[5]}")
    logger.info(f"  Apollo people:          {r[4]}")
    logger.info(f"  Apollo credits used:    {r[3]}")
    logger.info("=" * 70)


async def main():
    args = parse_args()
    start = datetime.utcnow()

    logger.info("=" * 70)
    logger.info(f"FULL PIPELINE — Project {args.project_id}")
    logger.info(f"  Search: Yandex + Google SERP" + (" + Apollo" if args.apollo_search else ""))
    logger.info(f"  max_queries={args.max_queries}, target_goal={args.target_goal}")
    logger.info(f"  Apollo enrichment: max_credits={args.apollo_credits}, max_people={args.apollo_max_people}")
    logger.info(f"  Titles: {args.apollo_titles}")
    logger.info(f"  Flags: skip_search={args.skip_search}, skip_extraction={args.skip_extraction}, "
                f"skip_enrichment={args.skip_enrichment}")
    logger.info("=" * 70)

    # Phase 1: Search
    if not args.skip_search:
        await phase_search(args.project_id, args.max_queries, args.target_goal, args.apollo_search)
    else:
        logger.info("Skipping search phase (--skip-search)")

    # Phase 2: Website contact extraction
    if not args.skip_extraction:
        await phase_extract_contacts(args.project_id)
    else:
        logger.info("Skipping website extraction (--skip-extraction)")

    # Phase 3: Apollo enrichment
    if not args.skip_enrichment:
        await phase_apollo_enrichment(
            args.project_id,
            max_credits=args.apollo_credits,
            max_people=args.apollo_max_people,
            titles=args.apollo_titles,
        )
    else:
        logger.info("Skipping Apollo enrichment (--skip-enrichment)")

    # Export
    if args.export_sheet:
        await phase_export(args.project_id)

    # Summary
    await print_summary(args.project_id)

    elapsed = (datetime.utcnow() - start).total_seconds()
    logger.info(f"Total pipeline time: {elapsed:.0f}s ({elapsed / 60:.1f} min)")

    # Cleanup
    from app.db import engine
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
