"""
Deliryo 1000-Target Search Script
==================================
Runs the iterative search pipeline for project Deliryo (id=18) until
target_goal is reached. Uses the new run_project_search() iterative loop.

Phase 1: Test with target_goal=100 (first run)
Phase 2: Scale to target_goal=1000

Pipeline per iteration:
  GPT-4o-mini generates queries → Yandex API search → Domain dedup against skip set →
  Crona batch scrape (JS-rendered) → GPT-4o-mini multi-criteria scoring →
  Auto-review (GPT second pass) → Blacklist rejections → Knowledge update →
  Refresh skip set → Next iteration if target not reached

Usage:
  cd backend
  source venv/bin/activate
  python ../scripts/deliryo_1000.py --goal 100   # test first
  python ../scripts/deliryo_1000.py --goal 1000  # full run
"""
import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
os.chdir(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from dotenv import load_dotenv
load_dotenv('.env')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(name)s %(levelname)s: %(message)s',
)
logger = logging.getLogger('deliryo_1000')

# Silence noisy loggers
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.engine.Engine').setLevel(logging.WARNING)


PROJECT_ID = 18


async def run_search(target_goal: int, max_queries: int, dry_run: bool = False):
    """Execute the iterative Deliryo search pipeline."""
    from app.db import async_session_maker
    from app.models.domain import SearchJob, SearchResult, ProjectBlacklist
    from app.services.company_search_service import company_search_service
    from app.services.review_service import review_service
    from sqlalchemy import select, func, text

    async with async_session_maker() as session:
        # --------------------------------------------------------
        # Step 0: Check current state
        # --------------------------------------------------------
        row = await session.execute(
            text("SELECT company_id, target_segments FROM projects WHERE id = :pid"),
            {"pid": PROJECT_ID},
        )
        project_row = row.fetchone()
        if not project_row:
            logger.error(f"Project {PROJECT_ID} not found!")
            return
        company_id = project_row[0]
        target_segments = project_row[1]

        # Count existing results and targets
        cnt = await session.execute(
            select(func.count()).select_from(SearchResult).where(
                SearchResult.project_id == PROJECT_ID
            )
        )
        existing_results = cnt.scalar() or 0

        cnt = await session.execute(
            select(func.count()).select_from(SearchResult).where(
                SearchResult.project_id == PROJECT_ID,
                SearchResult.is_target == True,
                SearchResult.review_status != "rejected",
            )
        )
        existing_targets = cnt.scalar() or 0

        cnt = await session.execute(
            select(func.count()).select_from(ProjectBlacklist).where(
                ProjectBlacklist.project_id == PROJECT_ID
            )
        )
        blacklisted = cnt.scalar() or 0

        logger.info("=" * 70)
        logger.info("DELIRYO SEARCH PIPELINE")
        logger.info("=" * 70)
        logger.info(f"  Target segments: {target_segments[:120]}...")
        logger.info(f"  Existing results: {existing_results}")
        logger.info(f"  Existing targets: {existing_targets}")
        logger.info(f"  Blacklisted domains: {blacklisted}")
        logger.info(f"  Goal: {target_goal} targets")
        logger.info(f"  Max queries budget: {max_queries}")
        logger.info(f"  Dry run: {dry_run}")
        logger.info("=" * 70)

        if existing_targets >= target_goal:
            logger.info(f"Already have {existing_targets} targets >= goal {target_goal}. Done!")
            await _print_top_targets(session, target_goal)
            return

        if dry_run:
            logger.info("DRY RUN — would call run_project_search() here. Exiting.")
            return

        # --------------------------------------------------------
        # Step 1: Run iterative search pipeline
        # --------------------------------------------------------
        logger.info("\nStarting iterative search pipeline...")
        start_time = datetime.utcnow()

        job = await company_search_service.run_project_search(
            session=session,
            project_id=PROJECT_ID,
            company_id=company_id,
            max_queries=max_queries,
            target_goal=target_goal,
        )
        await session.commit()

        elapsed = (datetime.utcnow() - start_time).total_seconds()
        logger.info(f"\nSearch job {job.id} completed in {elapsed:.0f}s")
        logger.info(f"  Status: {job.status}")
        logger.info(f"  Domains found: {job.domains_found}, new: {job.domains_new}")
        config = job.config or {}
        logger.info(f"  Iterations: {config.get('iterations_run', '?')}")
        logger.info(f"  Queries generated: {config.get('queries_generated', '?')}")
        logger.info(f"  Final targets: {config.get('final_targets', '?')}")
        logger.info(f"  OpenAI tokens: {config.get('openai_tokens_used', 0):,}")
        logger.info(f"  Crona credits: {config.get('crona_credits_used', 0)}")

        # --------------------------------------------------------
        # Step 2: Operator heuristic review of flagged results
        # --------------------------------------------------------
        logger.info("\n" + "=" * 70)
        logger.info("OPERATOR REVIEW PHASE")
        logger.info("=" * 70)

        flagged_result = await session.execute(
            select(SearchResult).where(
                SearchResult.search_job_id == job.id,
                SearchResult.review_status == "flagged",
            ).order_by(SearchResult.confidence.desc())
        )
        flagged = list(flagged_result.scalars().all())
        logger.info(f"Flagged results to review: {len(flagged)}")

        reviewed_count = 0
        for sr in flagged:
            verdict = _operator_review(sr)
            await review_service.manual_review(
                session=session,
                result_id=sr.id,
                verdict=verdict["verdict"],
                note=verdict["note"],
            )
            reviewed_count += 1
            if reviewed_count % 20 == 0:
                logger.info(f"  Reviewed {reviewed_count}/{len(flagged)}...")

        # Also reject low-confidence confirmed results
        confirmed_result = await session.execute(
            select(SearchResult).where(
                SearchResult.search_job_id == job.id,
                SearchResult.review_status == "confirmed",
                SearchResult.confidence < 0.35,
            )
        )
        low_conf = list(confirmed_result.scalars().all())
        for sr in low_conf:
            await review_service.manual_review(
                session=session,
                result_id=sr.id,
                verdict="rejected",
                note=f"Operator: low confidence {sr.confidence:.2f} confirmed result",
            )

        await session.commit()
        logger.info(f"  Operator reviewed: {reviewed_count} flagged + {len(low_conf)} low-confidence")

        # --------------------------------------------------------
        # Step 3: Update knowledge
        # --------------------------------------------------------
        logger.info("\nUpdating project knowledge...")
        knowledge = await review_service.update_project_knowledge(session, PROJECT_ID)
        await session.commit()
        logger.info(f"  Targets found: {knowledge.total_targets_found}")
        logger.info(f"  False positives: {knowledge.total_false_positives}")
        logger.info(f"  Good queries: {len(knowledge.good_query_patterns or [])}")
        logger.info(f"  Bad queries: {len(knowledge.bad_query_patterns or [])}")

        # --------------------------------------------------------
        # Step 4: Print summary
        # --------------------------------------------------------
        await _print_top_targets(session, target_goal)


async def _print_top_targets(session, limit: int = 100):
    """Print top targets for Deliryo."""
    from app.models.domain import SearchResult
    from sqlalchemy import select

    all_targets_result = await session.execute(
        select(SearchResult).where(
            SearchResult.project_id == PROJECT_ID,
            SearchResult.is_target == True,
            SearchResult.review_status != "rejected",
        ).order_by(SearchResult.confidence.desc())
    )
    all_targets = list(all_targets_result.scalars().all())

    logger.info("\n" + "=" * 70)
    logger.info(f"TOP TARGETS FOR DELIRYO ({len(all_targets)} total)")
    logger.info("=" * 70)

    output = []
    for i, r in enumerate(all_targets[:limit], 1):
        entry = {
            "rank": i,
            "domain": r.domain,
            "confidence": round(r.confidence or 0, 3),
            "review_status": r.review_status or "unreviewed",
            "company_name": (r.company_info or {}).get("name", ""),
            "industry": (r.company_info or {}).get("industry", ""),
            "services": (r.company_info or {}).get("services", []),
            "scores": r.scores or {},
        }
        output.append(entry)
        logger.info(
            f"  {i:3d}. {r.domain:<45s} conf={entry['confidence']:.2f} "
            f"review={entry['review_status']:<10s} "
            f"'{entry['company_name']}'"
        )

    # Save to file
    output_path = os.path.join(os.path.dirname(__file__), f'deliryo_targets_{len(all_targets)}.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    logger.info(f"\nResults saved to {output_path}")

    if len(all_targets) < limit:
        logger.info(
            f"\nNote: Only {len(all_targets)} targets found. "
            f"Run again to find more (knowledge feedback improves queries)."
        )


def _operator_review(sr) -> dict:
    """Heuristic operator review for flagged results."""
    scores = sr.scores or {}
    company_info = sr.company_info or {}
    reasoning = (sr.reasoning or "").lower()
    domain = (sr.domain or "").lower()
    industry = (company_info.get("industry") or "").lower()
    services = company_info.get("services") or []
    name = (company_info.get("name") or "").lower()

    # --- REJECT rules ---
    lang_score = scores.get("language_match", 1.0)
    if lang_score < 0.3:
        return {"verdict": "rejected", "note": f"Operator: non-Russian site (language_match={lang_score})"}

    reject_patterns = [
        "crm", "erp", "saas", "software", "job board", "vacancy", "recruiter",
        "news", "media", "magazine", "journal", "blog", "forum",
        "directory", "catalog", "aggregator", "marketplace",
        "education", "university", "school", "course",
        "freelance", "outsource", "seo", "marketing agency",
        "web development", "web design", "hosting",
    ]
    for pattern in reject_patterns:
        if pattern in industry or pattern in name or any(pattern in s.lower() for s in services):
            return {"verdict": "rejected", "note": f"Operator: non-target pattern '{pattern}' detected"}

    if (sr.confidence or 0) < 0.2:
        return {"verdict": "rejected", "note": f"Operator: very low confidence ({sr.confidence})"}

    # --- CONFIRM rules ---
    target_keywords = [
        "family office", "фэмили офис", "мфо", "wealth management",
        "управление капиталом", "управление активами", "asset management",
        "hnwi", "private wealth", "private banking",
        "инвестиционн", "investment", "состоятельн",
        "капитал", "capital", "trust", "траст",
        "multi-family", "multi family", "мультисемейн",
        "private equity", "venture capital", "фонд",
    ]
    matched_keywords = []
    text_to_check = f"{name} {industry} {' '.join(services)} {reasoning}"
    for kw in target_keywords:
        if kw in text_to_check:
            matched_keywords.append(kw)

    if len(matched_keywords) >= 2 and (sr.confidence or 0) >= 0.4:
        return {"verdict": "confirmed", "note": f"Operator: matches target keywords: {', '.join(matched_keywords)}"}

    if all(scores.get(k, 0) >= 0.5 for k in ["industry_match", "service_match", "company_type", "geography_match"]):
        if (sr.confidence or 0) >= 0.4:
            return {"verdict": "confirmed", "note": "Operator: good scores across all criteria"}

    if matched_keywords and (sr.confidence or 0) >= 0.5:
        return {"verdict": "confirmed", "note": f"Operator: matches target keyword: {matched_keywords[0]}"}

    return {"verdict": "flagged", "note": "Operator: uncertain, keeping flagged for human review"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deliryo iterative search pipeline")
    parser.add_argument("--goal", type=int, default=100, help="Target number of companies (default: 100)")
    parser.add_argument("--max-queries", type=int, default=500, help="Max queries budget (default: 500)")
    parser.add_argument("--dry-run", action="store_true", help="Just show state, don't run search")
    args = parser.parse_args()

    logger.info(f"Starting with goal={args.goal}, max_queries={args.max_queries}")
    asyncio.run(run_search(
        target_goal=args.goal,
        max_queries=args.max_queries,
        dry_run=args.dry_run,
    ))
