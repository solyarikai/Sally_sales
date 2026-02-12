"""
Deliryo Top-50 Search Pipeline
===============================
Runs the full search pipeline for project Deliryo (id=18):
1. run_project_search() → queries → Yandex → Crona scrape → GPT scoring → auto-review
2. Act as operator: manually review flagged results
3. Run knowledge accumulation
4. Output ranked top-50

Uses the backend services directly via the venv.
"""
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

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(levelname)s: %(message)s')
logger = logging.getLogger('deliryo_search')

# Silence noisy loggers
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)


async def run_pipeline():
    """Execute the full Deliryo search pipeline."""
    from app.db import async_session_maker
    from app.models.domain import SearchJob, SearchQuery, SearchResult, ProjectSearchKnowledge
    from app.services.company_search_service import company_search_service
    from app.services.review_service import review_service
    from sqlalchemy import select, func

    PROJECT_ID = 18

    async with async_session_maker() as session:
        # --------------------------------------------------------
        # Step 0: Check current state
        # --------------------------------------------------------
        # Get company_id from project
        from sqlalchemy import text
        row = await session.execute(text("SELECT company_id FROM projects WHERE id = :pid"), {"pid": PROJECT_ID})
        company_id = row.scalar_one()

        # Count existing results
        cnt = await session.execute(
            select(func.count()).select_from(SearchResult).where(
                SearchResult.project_id == PROJECT_ID
            )
        )
        existing_count = cnt.scalar() or 0
        logger.info(f"Existing results for Deliryo: {existing_count}")

        # --------------------------------------------------------
        # Step 1: Run full search pipeline (queries → Yandex → scrape → score → review)
        # --------------------------------------------------------
        logger.info("=" * 60)
        logger.info("STARTING FULL SEARCH PIPELINE")
        logger.info("=" * 60)

        job = await company_search_service.run_project_search(
            session=session,
            project_id=PROJECT_ID,
            company_id=company_id,
            max_queries=60,
        )
        await session.commit()

        logger.info(f"\nSearch job {job.id} completed: status={job.status}")
        logger.info(f"  Domains found: {job.domains_found}, new: {job.domains_new}")
        logger.info(f"  Config: {json.dumps(job.config or {}, indent=2)}")

        # --------------------------------------------------------
        # Step 2: Operator review of flagged results
        # --------------------------------------------------------
        logger.info("\n" + "=" * 60)
        logger.info("OPERATOR REVIEW PHASE")
        logger.info("=" * 60)

        # Get all results for this job that need review
        flagged_result = await session.execute(
            select(SearchResult).where(
                SearchResult.search_job_id == job.id,
                SearchResult.review_status == "flagged",
            ).order_by(SearchResult.confidence.desc())
        )
        flagged = list(flagged_result.scalars().all())

        logger.info(f"Flagged results to review: {len(flagged)}")
        for sr in flagged:
            # Act as operator: apply heuristic-based manual review
            verdict = _operator_review(sr)
            await review_service.manual_review(
                session=session,
                result_id=sr.id,
                verdict=verdict["verdict"],
                note=verdict["note"],
            )
            logger.info(f"  {sr.domain}: {verdict['verdict']} — {verdict['note']}")

        # Also review results that were auto-confirmed but look suspicious
        confirmed_result = await session.execute(
            select(SearchResult).where(
                SearchResult.search_job_id == job.id,
                SearchResult.review_status == "confirmed",
            ).order_by(SearchResult.confidence.asc())
        )
        confirmed = list(confirmed_result.scalars().all())

        for sr in confirmed:
            # Double-check low-confidence confirmed results
            if (sr.confidence or 0) < 0.4:
                await review_service.manual_review(
                    session=session,
                    result_id=sr.id,
                    verdict="rejected",
                    note="Operator: low confidence confirmed result, rejecting",
                )
                logger.info(f"  {sr.domain}: rejected (low confidence {sr.confidence:.2f} confirmed)")

        await session.commit()

        # --------------------------------------------------------
        # Step 3: Update knowledge from reviews
        # --------------------------------------------------------
        logger.info("\nUpdating project knowledge...")
        knowledge = await review_service.update_project_knowledge(session, PROJECT_ID)
        await session.commit()
        logger.info(f"  Targets found: {knowledge.total_targets_found}")
        logger.info(f"  False positives: {knowledge.total_false_positives}")
        logger.info(f"  Good query patterns: {len(knowledge.good_query_patterns or [])}")
        logger.info(f"  Bad query patterns: {len(knowledge.bad_query_patterns or [])}")

        # --------------------------------------------------------
        # Step 4: Get review summary
        # --------------------------------------------------------
        summary = await review_service.get_review_summary(session, job.id)
        logger.info(f"\nReview summary: {summary}")

        # --------------------------------------------------------
        # Step 5: Output top 50
        # --------------------------------------------------------
        logger.info("\n" + "=" * 60)
        logger.info("TOP 50 TARGETS FOR DELIRYO")
        logger.info("=" * 60)

        # Get all targets across all jobs for this project
        all_targets_result = await session.execute(
            select(SearchResult).where(
                SearchResult.project_id == PROJECT_ID,
                SearchResult.is_target == True,
                SearchResult.review_status != "rejected",
            ).order_by(SearchResult.confidence.desc())
        )
        all_targets = list(all_targets_result.scalars().all())

        output = []
        for i, r in enumerate(all_targets[:50], 1):
            entry = {
                "rank": i,
                "domain": r.domain,
                "confidence": round(r.confidence or 0, 3),
                "review_status": r.review_status or "unreviewed",
                "company_name": (r.company_info or {}).get("name", ""),
                "industry": (r.company_info or {}).get("industry", ""),
                "services": (r.company_info or {}).get("services", []),
                "scores": r.scores or {},
                "reasoning": (r.reasoning or "")[:200],
            }
            output.append(entry)
            logger.info(
                f"  {i:2d}. {r.domain:<45s} conf={entry['confidence']:.2f} "
                f"review={entry['review_status']:<10s} "
                f"'{entry['company_name']}'"
            )

        # Save to file
        output_path = os.path.join(os.path.dirname(__file__), 'deliryo_top50.json')
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        logger.info(f"\nResults saved to {output_path}")

        # If we don't have 50 yet, note that a second run might help
        if len(all_targets) < 50:
            logger.info(f"\nNote: Only {len(all_targets)} targets found so far. "
                       f"Run again to find more (knowledge feedback will improve queries).")

        return output


def _operator_review(sr: "SearchResult") -> dict:
    """
    Heuristic operator review for flagged results.
    Simulates what a human operator would decide based on available data.
    """
    scores = sr.scores or {}
    company_info = sr.company_info or {}
    reasoning = (sr.reasoning or "").lower()
    domain = (sr.domain or "").lower()
    industry = (company_info.get("industry") or "").lower()
    services = company_info.get("services") or []
    name = (company_info.get("name") or "").lower()

    # --- REJECT rules ---

    # Non-Russian sites for Russian market
    lang_score = scores.get("language_match", 1.0)
    if lang_score < 0.3:
        return {"verdict": "rejected", "note": f"Operator: non-Russian site (language_match={lang_score})"}

    # Known non-target patterns
    reject_patterns = [
        "crm", "erp", "saas", "software", "job board", "vacancy", "recruiter",
        "news", "media", "magazine", "journal", "blog", "forum",
        "directory", "catalog", "aggregator", "marketplace",
        "education", "university", "school", "course",
        "freelance", "outsource",
    ]
    for pattern in reject_patterns:
        if pattern in industry or pattern in name or any(pattern in s.lower() for s in services):
            return {"verdict": "rejected", "note": f"Operator: non-target pattern '{pattern}' detected"}

    # Very low confidence
    if (sr.confidence or 0) < 0.2:
        return {"verdict": "rejected", "note": f"Operator: very low confidence ({sr.confidence})"}

    # --- CONFIRM rules ---

    # Multi-family office / wealth management keywords
    target_keywords = [
        "family office", "фэмили офис", "мфо", "wealth management",
        "управление капиталом", "управление активами", "asset management",
        "hnwi", "private wealth", "private banking",
        "инвестиционн", "investment", "состоятельн",
        "капитал", "capital", "trust", "траст",
    ]
    matched_keywords = []
    text_to_check = f"{name} {industry} {' '.join(services)} {reasoning}"
    for kw in target_keywords:
        if kw in text_to_check:
            matched_keywords.append(kw)

    if len(matched_keywords) >= 2 and (sr.confidence or 0) >= 0.4:
        return {"verdict": "confirmed", "note": f"Operator: matches target keywords: {', '.join(matched_keywords)}"}

    # Good scores across the board
    if all(scores.get(k, 0) >= 0.5 for k in ["industry_match", "service_match", "company_type", "geography_match"]):
        if (sr.confidence or 0) >= 0.4:
            return {"verdict": "confirmed", "note": "Operator: good scores across all criteria"}

    # Single strong keyword match with decent confidence
    if matched_keywords and (sr.confidence or 0) >= 0.5:
        return {"verdict": "confirmed", "note": f"Operator: matches target keyword: {matched_keywords[0]}"}

    # --- FLAG: leave uncertain ---
    return {"verdict": "flagged", "note": "Operator: uncertain, keeping flagged for human review"}


if __name__ == "__main__":
    result = asyncio.run(run_pipeline())
    if result:
        print(f"\nFound {len(result)} target companies for Deliryo")
    else:
        print("\nPipeline completed but no targets found")
