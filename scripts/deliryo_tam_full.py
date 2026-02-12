"""
Deliryo Full TAM Discovery — Apollo Organization Search + Scoring Pipeline
===========================================================================
Yandex search is fully exhausted (317 targets from 10K+ analyzed, 9,852 in skip set).
This script uses Apollo organization search to find the complete TAM.

Flow:
  Part A: Reverse-engineer Apollo filters from existing confirmed targets
  Part B: Apollo organization search (keyword × location matrix)
  Part C: Score new domains via Crona scrape + GPT analysis
  Part D: Contact extraction + Apollo people enrichment
  Part E: Export to Google Sheets
  Part F: Print summary

Deliryo ICP: family offices, wealth management, private banking, trust services,
HNWI advisory. Russia + international hubs.

Usage (Docker):
  docker run -d --name deliryo-tam --network repo_default \
    -v ~/magnum-opus-project/repo/backend:/app \
    -v ~/magnum-opus-project/repo/scripts:/scripts \
    -e DATABASE_URL=... -e OPENAI_API_KEY=... -e APOLLO_API_KEY=... \
    -e CRONA_EMAIL=... -e CRONA_PASSWORD=... \
    python:3.11 bash -c 'pip install -q -r /app/requirements.txt && python /scripts/deliryo_tam_full.py'
"""
import asyncio
import json
import logging
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

# Add backend to path (works both locally and in Docker)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
sys.path.insert(0, "/app")
os.environ.setdefault("DATABASE_URL", os.environ.get("DATABASE_URL", ""))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("deliryo_tam")

# Silence noisy loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# ── Constants ──────────────────────────────────────────────────────────────
PROJECT_ID = 18

# Apollo org search matrix
KEYWORDS_TIER1 = [
    ["family office"],
    ["wealth management"],
    ["private banking"],
    ["asset management"],
    ["trust services"],
    ["private wealth"],
    ["multi family office"],
    ["investment advisory"],
]

KEYWORDS_TIER2 = [
    ["private equity"],
    ["hedge fund"],
    ["investment management"],
]

LOCATIONS = [
    "Russia",
    "Cyprus",
    "Monaco",
    "United Kingdom",
    "Switzerland",
    "United Arab Emirates",
    "Israel",
    "Singapore",
    "Luxembourg",
    "Liechtenstein",
    "Latvia",
    "Estonia",
]

SIZE_RANGES = ["1,10", "11,50", "51,200", "201,1000"]

ENRICHMENT_TITLES = [
    "CEO", "Founder", "Managing Partner", "Director", "Head",
    "CIO", "CFO", "COO", "Owner", "Portfolio Manager",
    "Managing Director", "Partner", "President",
]


def extract_domain_from_url(url: str) -> Optional[str]:
    """Extract clean domain from a URL string."""
    if not url:
        return None
    url = url.strip().lower()
    for prefix in ("https://", "http://", "www."):
        if url.startswith(prefix):
            url = url[len(prefix):]
    url = url.split("/")[0].split("?")[0].split("#")[0]
    return url if url and "." in url else None


# ══════════════════════════════════════════════════════════════════════════
# Part A: Reverse-Engineer Apollo Filters from Existing Targets
# ══════════════════════════════════════════════════════════════════════════
async def part_a_analyze_existing_targets(session) -> Dict[str, Any]:
    """Analyze Apollo raw_data from confirmed targets to find common patterns."""
    from sqlalchemy import select, text

    logger.info("=" * 60)
    logger.info("PART A: Analyzing existing targets' Apollo data")
    logger.info("=" * 60)

    # Get all ExtractedContacts with raw_data for Deliryo targets
    # (avoid raw enum comparison — DB enum values may differ from Python)
    rows = await session.execute(text("""
        SELECT ec.raw_data, dc.domain, dc.company_info
        FROM extracted_contacts ec
        JOIN discovered_companies dc ON ec.discovered_company_id = dc.id
        WHERE dc.project_id = :pid
          AND dc.is_target = true
          AND ec.raw_data IS NOT NULL
    """), {"pid": PROJECT_ID})
    results = rows.fetchall()

    industries = Counter()
    keywords_counter = Counter()
    countries = Counter()
    seniorities = Counter()

    for raw_data, domain, company_info in results:
        if not isinstance(raw_data, dict):
            continue
        org = raw_data.get("organization") if isinstance(raw_data.get("organization"), dict) else {}
        # raw_data from apollo_service stores org as a string (org name), not dict
        # Check the actual shape
        if isinstance(raw_data.get("organization"), str):
            # Flat structure — seniority is at top level
            seniority = raw_data.get("seniority")
            if seniority:
                seniorities[seniority] += 1
            country = raw_data.get("country")
            if country:
                countries[country] += 1
        else:
            # Nested structure
            if org.get("industry"):
                industries[org["industry"]] += 1
            for kw in (org.get("keywords") or []):
                keywords_counter[kw] += 1
            if org.get("country"):
                countries[org["country"]] += 1
            seniority = raw_data.get("seniority")
            if seniority:
                seniorities[seniority] += 1

    patterns = {
        "total_contacts_analyzed": len(results),
        "top_industries": industries.most_common(20),
        "top_keywords": keywords_counter.most_common(30),
        "top_countries": countries.most_common(20),
        "top_seniorities": seniorities.most_common(10),
    }

    logger.info(f"Analyzed {len(results)} Apollo contacts from confirmed targets")
    logger.info(f"Top industries: {patterns['top_industries'][:10]}")
    logger.info(f"Top keywords: {patterns['top_keywords'][:10]}")
    logger.info(f"Top countries: {patterns['top_countries'][:10]}")
    logger.info(f"Top seniorities: {patterns['top_seniorities']}")

    return patterns


# ══════════════════════════════════════════════════════════════════════════
# Part B: Apollo Organization Search
# ══════════════════════════════════════════════════════════════════════════
async def part_b_apollo_org_search(session, skip_set: Set[str]) -> Dict[str, Any]:
    """Search Apollo for organizations matching Deliryo ICP."""
    from app.services.apollo_service import apollo_service

    logger.info("=" * 60)
    logger.info("PART B: Apollo Organization Search")
    logger.info(f"Skip set size: {len(skip_set)} domains")
    logger.info("=" * 60)

    if not apollo_service.is_configured():
        logger.error("Apollo API key not configured, skipping org search")
        return {"new_domains": [], "stats": {}}

    apollo_service.reset_credits()
    all_new_domains: Set[str] = set()
    combo_stats: Dict[str, Dict[str, int]] = {}

    all_keywords = KEYWORDS_TIER1 + KEYWORDS_TIER2

    for keyword_tags in all_keywords:
        for location in LOCATIONS:
            combo_key = f"{keyword_tags[0]}|{location}"
            logger.info(f"\n--- Searching: {combo_key} ---")

            orgs = await apollo_service.search_organizations_all_pages(
                keyword_tags=keyword_tags,
                locations=[location],
                num_employees_ranges=SIZE_RANGES,
                max_pages=50,
            )

            domains_found = set()
            for org in orgs:
                domain = org.get("primary_domain")
                if not domain:
                    # Try website_url
                    domain = extract_domain_from_url(org.get("website_url", ""))
                if domain:
                    domain = domain.lower().strip()
                    domains_found.add(domain)

            new_in_combo = domains_found - skip_set - all_new_domains
            all_new_domains.update(new_in_combo)

            combo_stats[combo_key] = {
                "orgs_returned": len(orgs),
                "domains_extracted": len(domains_found),
                "new_domains": len(new_in_combo),
            }

            logger.info(
                f"  {combo_key}: {len(orgs)} orgs, "
                f"{len(domains_found)} domains, "
                f"{len(new_in_combo)} NEW"
            )

    logger.info(f"\nApollo org search complete:")
    logger.info(f"  Total new domains found: {len(all_new_domains)}")
    logger.info(f"  Apollo credits used: {apollo_service.credits_used}")

    # Log top combos by new domains
    sorted_combos = sorted(combo_stats.items(), key=lambda x: x[1]["new_domains"], reverse=True)
    logger.info("\nTop 10 combos by new domains:")
    for combo_key, stats in sorted_combos[:10]:
        logger.info(f"  {combo_key}: {stats['new_domains']} new ({stats['orgs_returned']} orgs total)")

    return {
        "new_domains": sorted(all_new_domains),
        "stats": combo_stats,
        "credits_used": apollo_service.credits_used,
    }


# ══════════════════════════════════════════════════════════════════════════
# Part C: Score New Domains (Crona scrape + GPT analysis)
# ══════════════════════════════════════════════════════════════════════════
async def part_c_score_domains(session, new_domains: List[str], company_id: int) -> Dict[str, Any]:
    """Score new domains using the existing Crona + GPT pipeline."""
    from app.models.domain import SearchJob, SearchJobStatus, SearchEngine, SearchResult
    from app.models.contact import Project
    from app.services.company_search_service import company_search_service
    from sqlalchemy import select, func

    logger.info("=" * 60)
    logger.info(f"PART C: Scoring {len(new_domains)} new domains")
    logger.info("=" * 60)

    if not new_domains:
        logger.info("No new domains to score")
        return {"targets_found": 0, "analyzed": 0}

    # Load project for target_segments
    proj_result = await session.execute(
        select(Project).where(Project.id == PROJECT_ID)
    )
    project = proj_result.scalar_one_or_none()
    if not project:
        logger.error(f"Project {PROJECT_ID} not found!")
        return {"targets_found": 0, "analyzed": 0}

    target_segments = project.target_segments or ""

    # Create a search job for tracking
    job = SearchJob(
        company_id=company_id,
        status=SearchJobStatus.RUNNING,
        search_engine=SearchEngine.APOLLO_ORG,
        project_id=PROJECT_ID,
        queries_total=len(new_domains),
        started_at=datetime.utcnow(),
        config={
            "source": "apollo_org_search",
            "domains_to_analyze": len(new_domains),
        },
    )
    session.add(job)
    await session.flush()
    logger.info(f"Created search job {job.id} for Apollo org search scoring")

    # Process in batches of 100
    batch_size = 100
    total_targets = 0

    for i in range(0, len(new_domains), batch_size):
        batch = new_domains[i:i + batch_size]
        logger.info(f"\nScoring batch {i // batch_size + 1}/{(len(new_domains) + batch_size - 1) // batch_size}: {len(batch)} domains")

        await company_search_service._scrape_and_analyze_domains(
            session=session,
            job=job,
            domains=batch,
            target_segments=target_segments,
        )
        await session.commit()

        # Count targets so far
        cnt = await session.execute(
            select(func.count()).select_from(SearchResult).where(
                SearchResult.search_job_id == job.id,
                SearchResult.is_target == True,
                SearchResult.review_status != "rejected",
            )
        )
        batch_targets = cnt.scalar() or 0
        total_targets = batch_targets
        logger.info(f"  Targets so far: {total_targets}")

    # Finalize job
    job.status = SearchJobStatus.COMPLETED
    job.completed_at = datetime.utcnow()
    job.domains_found = len(new_domains)
    job.domains_new = len(new_domains)

    # Count final analyzed
    analyzed_cnt = await session.execute(
        select(func.count()).select_from(SearchResult).where(
            SearchResult.search_job_id == job.id,
        )
    )
    total_analyzed = analyzed_cnt.scalar() or 0

    await session.commit()

    logger.info(f"\nScoring complete:")
    logger.info(f"  Analyzed: {total_analyzed}")
    logger.info(f"  Targets found: {total_targets}")
    logger.info(f"  Job config: {json.dumps(job.config or {}, indent=2)}")

    return {
        "job_id": job.id,
        "targets_found": total_targets,
        "analyzed": total_analyzed,
        "config": job.config,
    }


# ══════════════════════════════════════════════════════════════════════════
# Part D: Contact Extraction + Apollo People Enrichment
# ══════════════════════════════════════════════════════════════════════════
async def part_d_enrich_contacts(session, company_id: int) -> Dict[str, Any]:
    """Extract contacts and enrich via Apollo for all Deliryo targets without contacts."""
    from app.models.pipeline import DiscoveredCompany, DiscoveredCompanyStatus
    from app.services.pipeline_service import pipeline_service
    from sqlalchemy import select

    logger.info("=" * 60)
    logger.info("PART D: Contact Extraction + Apollo Enrichment")
    logger.info("=" * 60)

    # Find all Deliryo target companies without Apollo enrichment
    result = await session.execute(
        select(DiscoveredCompany).where(
            DiscoveredCompany.project_id == PROJECT_ID,
            DiscoveredCompany.company_id == company_id,
            DiscoveredCompany.is_target == True,
            DiscoveredCompany.apollo_enriched_at.is_(None),
        )
    )
    companies = list(result.scalars().all())
    logger.info(f"Found {len(companies)} target companies without Apollo enrichment")

    if not companies:
        logger.info("All targets already enriched")
        return {"extracted": 0, "enriched": 0}

    dc_ids = [dc.id for dc in companies]

    # Step 1: Contact extraction from websites
    logger.info(f"\nExtracting contacts for {len(dc_ids)} companies...")
    extract_stats = await pipeline_service.extract_contacts_batch(
        session=session,
        discovered_company_ids=dc_ids,
        company_id=company_id,
    )
    logger.info(f"Contact extraction: {extract_stats}")

    # Step 2: Apollo people enrichment
    logger.info(f"\nApollo people enrichment for {len(dc_ids)} companies...")
    enrich_stats = await pipeline_service.enrich_apollo_batch(
        session=session,
        discovered_company_ids=dc_ids,
        company_id=company_id,
        titles=ENRICHMENT_TITLES,
    )
    logger.info(f"Apollo enrichment: {enrich_stats}")

    await session.commit()

    return {
        "extraction": extract_stats,
        "enrichment": enrich_stats,
    }


# ══════════════════════════════════════════════════════════════════════════
# Part E: Export to Google Sheets
# ══════════════════════════════════════════════════════════════════════════
async def part_e_export_sheets(session, company_id: int) -> Optional[str]:
    """Export all Deliryo targets + contacts to Google Sheets."""
    from app.models.pipeline import DiscoveredCompany, ExtractedContact
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    logger.info("=" * 60)
    logger.info("PART E: Google Sheets Export")
    logger.info("=" * 60)

    try:
        from app.services.sheets_service import sheets_service
        if not sheets_service.is_configured:
            logger.warning("Google Sheets not configured, skipping export")
            return None
    except ImportError:
        logger.warning("sheets_service not available, skipping export")
        return None

    # Load all targets with contacts
    result = await session.execute(
        select(DiscoveredCompany)
        .options(selectinload(DiscoveredCompany.extracted_contacts))
        .where(
            DiscoveredCompany.project_id == PROJECT_ID,
            DiscoveredCompany.company_id == company_id,
            DiscoveredCompany.is_target == True,
        )
        .order_by(DiscoveredCompany.confidence.desc())
    )
    companies = list(result.scalars().all())

    if not companies:
        logger.info("No targets to export")
        return None

    # Build rows for export
    rows = []
    for dc in companies:
        contacts = dc.extracted_contacts or []
        if contacts:
            for contact in contacts:
                rows.append({
                    "Domain": dc.domain,
                    "Company Name": dc.name or "",
                    "URL": dc.url or f"https://{dc.domain}",
                    "Confidence": dc.confidence or 0,
                    "Reasoning": (dc.reasoning or "")[:200],
                    "Status": dc.status.value if dc.status else "",
                    "Contact Email": contact.email or "",
                    "Contact Name": f"{contact.first_name or ''} {contact.last_name or ''}".strip(),
                    "Job Title": contact.job_title or "",
                    "LinkedIn": contact.linkedin_url or "",
                    "Phone": contact.phone or "",
                    "Source": contact.source.value if contact.source else "",
                    "Verified": "Yes" if contact.is_verified else "No",
                })
        else:
            rows.append({
                "Domain": dc.domain,
                "Company Name": dc.name or "",
                "URL": dc.url or f"https://{dc.domain}",
                "Confidence": dc.confidence or 0,
                "Reasoning": (dc.reasoning or "")[:200],
                "Status": dc.status.value if dc.status else "",
                "Contact Email": "",
                "Contact Name": "",
                "Job Title": "",
                "LinkedIn": "",
                "Phone": "",
                "Source": "",
                "Verified": "",
            })

    title = f"Deliryo TAM Full - {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
    try:
        sheet_url = await sheets_service.export_to_sheet(title, rows)
        logger.info(f"Exported {len(rows)} rows to Google Sheets: {sheet_url}")
        return sheet_url
    except Exception as e:
        logger.error(f"Google Sheets export failed: {e}")
        return None


# ══════════════════════════════════════════════════════════════════════════
# Part F: Summary
# ══════════════════════════════════════════════════════════════════════════
async def part_f_summary(session, apollo_result: Dict, scoring_result: Dict, enrich_result: Dict, sheet_url: Optional[str]):
    """Print final summary."""
    from app.models.domain import SearchResult
    from app.models.pipeline import DiscoveredCompany, ExtractedContact
    from sqlalchemy import select, func

    logger.info("\n" + "=" * 60)
    logger.info("DELIRYO TAM FULL — FINAL SUMMARY")
    logger.info("=" * 60)

    # Total targets
    cnt = await session.execute(
        select(func.count()).select_from(SearchResult).where(
            SearchResult.project_id == PROJECT_ID,
            SearchResult.is_target == True,
            SearchResult.review_status != "rejected",
        )
    )
    total_targets = cnt.scalar() or 0

    # Total analyzed
    cnt = await session.execute(
        select(func.count()).select_from(SearchResult).where(
            SearchResult.project_id == PROJECT_ID,
        )
    )
    total_analyzed = cnt.scalar() or 0

    # Total contacts
    cnt = await session.execute(
        select(func.count()).select_from(ExtractedContact).where(
            ExtractedContact.discovered_company_id.in_(
                select(DiscoveredCompany.id).where(
                    DiscoveredCompany.project_id == PROJECT_ID,
                    DiscoveredCompany.is_target == True,
                )
            )
        )
    )
    total_contacts = cnt.scalar() or 0

    logger.info(f"\n📊 RESULTS:")
    logger.info(f"  New domains from Apollo org search: {len(apollo_result.get('new_domains', []))}")
    logger.info(f"  New targets after scoring: {scoring_result.get('targets_found', 0)}")
    logger.info(f"  Contacts enriched: {enrich_result}")
    logger.info(f"\n📈 DELIRYO TOTAL TAM:")
    logger.info(f"  Total targets: {total_targets}")
    logger.info(f"  Total domains analyzed: {total_analyzed}")
    logger.info(f"  Total contacts: {total_contacts}")
    logger.info(f"\n💰 COSTS:")
    logger.info(f"  Apollo org search credits: {apollo_result.get('credits_used', 0)}")
    scoring_config = scoring_result.get("config") or {}
    logger.info(f"  Crona credits: {scoring_config.get('crona_credits_used', 'N/A')}")
    logger.info(f"  OpenAI tokens: {scoring_config.get('openai_tokens_used', 'N/A')}")
    if sheet_url:
        logger.info(f"\n📄 Google Sheet: {sheet_url}")
    logger.info("=" * 60)


# ══════════════════════════════════════════════════════════════════════════
# Main Orchestrator
# ══════════════════════════════════════════════════════════════════════════
async def main():
    from app.db import async_session_maker
    from app.services.company_search_service import company_search_service
    from sqlalchemy import text

    logger.info("=" * 60)
    logger.info("DELIRYO FULL TAM DISCOVERY")
    logger.info(f"Started at: {datetime.utcnow().isoformat()}")
    logger.info("=" * 60)

    async with async_session_maker() as session:
        # Get company_id
        row = await session.execute(text("SELECT company_id FROM projects WHERE id = :pid"), {"pid": PROJECT_ID})
        company_id = row.scalar_one()
        logger.info(f"Project {PROJECT_ID}, Company {company_id}")

        # Build skip set (all domains already processed)
        skip_set = await company_search_service._build_skip_set(session, PROJECT_ID)
        logger.info(f"Skip set: {len(skip_set)} domains already processed")

        # ── Part A ──
        patterns = await part_a_analyze_existing_targets(session)

        # ── Part B ──
        apollo_result = await part_b_apollo_org_search(session, skip_set)
        new_domains = apollo_result["new_domains"]

        if not new_domains:
            logger.info("No new domains found from Apollo org search")
        else:
            # ── Part C ──
            scoring_result = await part_c_score_domains(session, new_domains, company_id)

        if not new_domains:
            scoring_result = {"targets_found": 0, "analyzed": 0, "config": {}}

        # ── Part D ──
        enrich_result = await part_d_enrich_contacts(session, company_id)

        # ── Part E ──
        sheet_url = await part_e_export_sheets(session, company_id)

        # ── Part F ──
        await part_f_summary(session, apollo_result, scoring_result, enrich_result, sheet_url)


if __name__ == "__main__":
    asyncio.run(main())
