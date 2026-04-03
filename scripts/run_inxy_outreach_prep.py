"""
Inxy Outreach Preparation — Full pipeline from targets to Google Sheet.

Steps:
1. Promote all target SearchResults → DiscoveredCompany
2. Extract website contacts (emails, phones) via GPT + regex
3. Apollo C-level enrichment (CEO, CFO, COO, Founder, Head of Finance, etc.)
4. FindyMail: verify Apollo emails, find emails for contacts without them
5. Export to Google Sheet: each row = one contact, with full provenance
"""
import asyncio
import json
import logging
import os
import sys
from datetime import datetime

sys.path.insert(0, "/app")
os.chdir("/app")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("inxy_outreach")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

PROJECT_ID = 48
COMPANY_ID = 1
SHARE_WITH = ["pn@getsally.io"]

# C-level / finance / payments titles for Apollo enrichment
TARGET_TITLES = [
    "CEO", "Chief Executive Officer",
    "CFO", "Chief Financial Officer",
    "COO", "Chief Operating Officer",
    "Founder", "Co-Founder",
    "CTO", "Chief Technology Officer",
    "Head of Finance", "VP Finance", "Director of Finance",
    "Head of Payments", "VP Payments", "Director of Payments",
    "Head of Business Development", "VP Business Development",
    "Managing Director", "General Manager", "Owner",
]


async def step1_promote_targets():
    """Promote all target SearchResults to DiscoveredCompany records."""
    from app.db import async_session_maker
    from app.models.domain import SearchJob, SearchResult
    from app.models.pipeline import DiscoveredCompany, DiscoveredCompanyStatus
    from sqlalchemy import select, func

    logger.info("=" * 60)
    logger.info("STEP 1: Promote targets → DiscoveredCompany")
    logger.info("=" * 60)

    async with async_session_maker() as session:
        # Get all target search results
        targets = await session.execute(
            select(SearchResult).where(
                SearchResult.project_id == PROJECT_ID,
                SearchResult.is_target == True,
            )
        )
        all_targets = targets.scalars().all()
        logger.info(f"Target SearchResults: {len(all_targets)}")

        # Check existing DiscoveredCompanies
        existing = await session.execute(
            select(DiscoveredCompany.domain).where(
                DiscoveredCompany.project_id == PROJECT_ID,
            )
        )
        existing_domains = {r[0] for r in existing.fetchall()}

        created = 0
        updated = 0
        for sr in all_targets:
            if sr.domain in existing_domains:
                # Update existing to ensure is_target=true
                dc_q = await session.execute(
                    select(DiscoveredCompany).where(
                        DiscoveredCompany.project_id == PROJECT_ID,
                        DiscoveredCompany.domain == sr.domain,
                    )
                )
                dc = dc_q.scalar_one_or_none()
                if dc and not dc.is_target:
                    dc.is_target = True
                    dc.confidence = sr.confidence
                    dc.reasoning = sr.reasoning
                    dc.company_info = sr.company_info
                    updated += 1
                continue

            company_info = sr.company_info or {}
            dc = DiscoveredCompany(
                company_id=COMPANY_ID,
                project_id=PROJECT_ID,
                domain=sr.domain,
                name=company_info.get("name"),
                url=sr.url or f"https://{sr.domain}",
                search_result_id=sr.id,
                search_job_id=sr.search_job_id,
                is_target=True,
                confidence=sr.confidence,
                reasoning=sr.reasoning,
                company_info=sr.company_info,
                matched_segment=sr.matched_segment,
                status=DiscoveredCompanyStatus.ANALYZED,
                scraped_html=sr.html_snippet,
                scraped_at=sr.scraped_at,
            )
            session.add(dc)
            existing_domains.add(sr.domain)
            created += 1

        await session.commit()

        # Count total
        tc = await session.execute(
            select(func.count()).select_from(DiscoveredCompany).where(
                DiscoveredCompany.project_id == PROJECT_ID,
                DiscoveredCompany.is_target == True,
            )
        )
        total = tc.scalar() or 0
        logger.info(f"Created: {created}, Updated: {updated}, Total targets in pipeline: {total}")
        return total


async def step2_extract_website_contacts():
    """Extract contacts from target company websites."""
    from app.db import async_session_maker
    from app.services.pipeline_service import pipeline_service
    from app.models.pipeline import DiscoveredCompany
    from sqlalchemy import select

    logger.info("=" * 60)
    logger.info("STEP 2: Extract website contacts")
    logger.info("=" * 60)

    async with async_session_maker() as session:
        # Get targets without contacts extracted yet
        result = await session.execute(
            select(DiscoveredCompany).where(
                DiscoveredCompany.project_id == PROJECT_ID,
                DiscoveredCompany.is_target == True,
            )
        )
        all_targets = result.scalars().all()

        # Split into those needing extraction vs already done
        need_extraction = [dc for dc in all_targets if not dc.contacts_count or dc.contacts_count == 0]
        already_done = len(all_targets) - len(need_extraction)

        logger.info(f"Targets: {len(all_targets)}, need extraction: {len(need_extraction)}, already done: {already_done}")

        if not need_extraction:
            logger.info("All targets already have contacts extracted.")
            return

        BATCH = 20
        total_contacts = 0
        for i in range(0, len(need_extraction), BATCH):
            batch = need_extraction[i:i + BATCH]
            batch_ids = [dc.id for dc in batch]
            batch_num = i // BATCH + 1
            total_batches = (len(need_extraction) + BATCH - 1) // BATCH

            logger.info(f"Batch {batch_num}/{total_batches}: extracting from {len(batch)} domains...")
            try:
                stats = await pipeline_service.extract_contacts_batch(
                    session=session,
                    discovered_company_ids=batch_ids,
                    company_id=COMPANY_ID,
                )
                total_contacts += stats.get("contacts_found", 0)
                logger.info(f"  Batch {batch_num}: {stats}")
            except Exception as e:
                logger.error(f"  Batch {batch_num} error: {e}")

        logger.info(f"Website extraction complete. Total new contacts: {total_contacts}")


async def step3_apollo_enrichment():
    """Enrich targets with Apollo C-level contacts."""
    from app.db import async_session_maker
    from app.services.pipeline_service import pipeline_service
    from app.models.pipeline import DiscoveredCompany
    from sqlalchemy import select

    logger.info("=" * 60)
    logger.info("STEP 3: Apollo C-level enrichment")
    logger.info("=" * 60)

    async with async_session_maker() as session:
        result = await session.execute(
            select(DiscoveredCompany).where(
                DiscoveredCompany.project_id == PROJECT_ID,
                DiscoveredCompany.is_target == True,
            )
        )
        all_targets = result.scalars().all()

        # Skip those already enriched via Apollo
        need_enrichment = [dc for dc in all_targets if not dc.apollo_enriched_at]
        already_done = len(all_targets) - len(need_enrichment)

        logger.info(f"Targets: {len(all_targets)}, need Apollo: {len(need_enrichment)}, already enriched: {already_done}")

        if not need_enrichment:
            logger.info("All targets already Apollo-enriched.")
            return

        BATCH = 25
        total_people = 0
        for i in range(0, len(need_enrichment), BATCH):
            batch = need_enrichment[i:i + BATCH]
            batch_ids = [dc.id for dc in batch]
            batch_num = i // BATCH + 1
            total_batches = (len(need_enrichment) + BATCH - 1) // BATCH

            logger.info(f"Batch {batch_num}/{total_batches}: enriching {len(batch)} domains...")
            try:
                stats = await pipeline_service.enrich_apollo_batch(
                    session=session,
                    discovered_company_ids=batch_ids,
                    company_id=COMPANY_ID,
                    max_people=5,
                    titles=TARGET_TITLES,
                )
                total_people += stats.get("people_found", 0)
                logger.info(f"  Batch {batch_num}: {stats}")
            except Exception as e:
                logger.error(f"  Batch {batch_num} error: {e}")

        logger.info(f"Apollo enrichment complete. Total new people: {total_people}")


async def step4_findymail_verification():
    """Verify/find emails via FindyMail."""
    from app.db import async_session_maker
    from app.services.findymail_service import findymail_service
    from app.services.email_verification_service import email_verification_service
    from app.models.pipeline import DiscoveredCompany, ExtractedContact, ContactSource
    from app.core.config import settings
    from sqlalchemy import select

    logger.info("=" * 60)
    logger.info("STEP 4: FindyMail email verification & finding")
    logger.info("=" * 60)

    # Init FindyMail
    if hasattr(settings, "FINDYMAIL_API_KEY") and settings.FINDYMAIL_API_KEY:
        findymail_service.set_api_key(settings.FINDYMAIL_API_KEY)
    elif os.environ.get("FINDYMAIL_API_KEY"):
        findymail_service.set_api_key(os.environ["FINDYMAIL_API_KEY"])

    if not findymail_service.is_connected():
        logger.warning("FindyMail not configured — skipping verification step")
        return

    credits = await findymail_service.get_credits()
    logger.info(f"FindyMail credits: {credits}")

    async with async_session_maker() as session:
        # Get all extracted contacts for target companies
        dc_ids_q = await session.execute(
            select(DiscoveredCompany.id).where(
                DiscoveredCompany.project_id == PROJECT_ID,
                DiscoveredCompany.is_target == True,
            )
        )
        dc_ids = [r[0] for r in dc_ids_q.fetchall()]

        contacts_q = await session.execute(
            select(ExtractedContact).where(
                ExtractedContact.discovered_company_id.in_(dc_ids),
            )
        )
        all_contacts = contacts_q.scalars().all()

        # Split: Apollo contacts needing verification, contacts needing email finding
        to_verify = []
        to_find = []
        already_verified = 0

        for ec in all_contacts:
            if ec.is_verified:
                already_verified += 1
                continue
            if ec.email and ec.source == ContactSource.APOLLO:
                to_verify.append(ec)
            elif not ec.email and ec.first_name and ec.last_name:
                to_find.append(ec)

        logger.info(f"Contacts: {len(all_contacts)} total, {already_verified} verified, "
                     f"{len(to_verify)} to verify, {len(to_find)} to find email")

        # Verify Apollo emails
        verified_count = 0
        invalid_count = 0
        for ec in to_verify:
            try:
                result = await findymail_service.verify_email(ec.email)
                if result.get("success"):
                    ec.is_verified = result.get("verified", False)
                    ec.verification_method = "findymail"
                    if ec.is_verified:
                        verified_count += 1
                    else:
                        invalid_count += 1
                        # Try to find a better email
                        if ec.first_name and ec.last_name:
                            dc_q = await session.execute(
                                select(DiscoveredCompany.domain).where(
                                    DiscoveredCompany.id == ec.discovered_company_id
                                )
                            )
                            domain = dc_q.scalar()
                            if domain:
                                find_result = await findymail_service.find_email_by_name(
                                    f"{ec.first_name} {ec.last_name}", domain
                                )
                                if find_result.get("success") and find_result.get("email"):
                                    ec.email = find_result["email"]
                                    ec.is_verified = find_result.get("verified", False)
                                    ec.verification_method = "findymail_found"
                                    logger.info(f"  Replaced invalid email with FindyMail: {ec.email}")

                if verified_count + invalid_count > 0 and (verified_count + invalid_count) % 50 == 0:
                    await session.commit()
                    logger.info(f"  Verify progress: {verified_count} valid, {invalid_count} invalid")

            except Exception as e:
                logger.error(f"  Verify error for {ec.email}: {e}")

        # Find emails for contacts without them
        found_count = 0
        for ec in to_find:
            try:
                dc_q = await session.execute(
                    select(DiscoveredCompany.domain).where(
                        DiscoveredCompany.id == ec.discovered_company_id
                    )
                )
                domain = dc_q.scalar()
                if not domain:
                    continue

                result = await findymail_service.find_email_by_name(
                    f"{ec.first_name} {ec.last_name}", domain
                )
                if result.get("success") and result.get("email"):
                    ec.email = result["email"]
                    ec.is_verified = result.get("verified", False)
                    ec.verification_method = "findymail_found"
                    found_count += 1

            except Exception as e:
                logger.error(f"  Find error for {ec.first_name} {ec.last_name}: {e}")

        await session.commit()
        logger.info(f"FindyMail complete: {verified_count} verified, {invalid_count} invalid, {found_count} found")


async def step5_export_google_sheet():
    """Export all contacts to Google Sheet — each row = one contact."""
    from app.db import async_session_maker
    from app.services.google_sheets_service import google_sheets_service
    from sqlalchemy import text

    logger.info("=" * 60)
    logger.info("STEP 5: Export to Google Sheet")
    logger.info("=" * 60)

    async with async_session_maker() as session:
        # Main query: join search_results + discovered_companies + extracted_contacts
        # Each row = one contact with full company + provenance data
        result = await session.execute(text("""
            SELECT
                dc.domain,
                'https://' || dc.domain as url,
                COALESCE(dc.name, sr.company_info->>'name', '') as company_name,
                COALESCE(sr.company_info->>'description', '') as description,
                COALESCE(sr.company_info->>'location', '') as location,
                COALESCE(sr.company_info->>'industry', '') as industry,
                COALESCE(sr.matched_segment, dc.matched_segment, '') as segment,
                COALESCE(sr.confidence, dc.confidence, 0) as confidence,
                COALESCE(sr.reasoning, dc.reasoning, '') as reasoning,
                -- Contact fields
                ec.first_name,
                ec.last_name,
                ec.email,
                ec.phone,
                ec.job_title,
                ec.linkedin_url,
                ec.source as contact_source,
                ec.is_verified,
                ec.verification_method,
                -- Source tracking
                CASE
                    WHEN dc.company_info->>'source' = 'team_xlsx' THEN 'Manual (XLSX)'
                    WHEN sj.config->>'segment' = 'team_manual' THEN 'Manual (XLSX)'
                    WHEN sj.search_engine = 'YANDEX_API' THEN 'Yandex'
                    WHEN sj.search_engine = 'GOOGLE_SERP' THEN 'Google'
                    WHEN sj.config->>'segment' LIKE 'apollo%' THEN 'Apollo'
                    ELSE COALESCE(sj.search_engine::text, 'Unknown')
                END as discovery_source,
                COALESCE(sq.query_text, '') as search_query,
                COALESCE(sq.geo, sj.config->>'geo', '') as search_geo,
                sj.id as search_job_id,
                -- Apollo org data
                dc.apollo_org_data->>'country' as apollo_country,
                dc.apollo_org_data->>'estimated_num_employees' as employees,
                dc.apollo_org_data->>'annual_revenue_printed' as revenue,
                dc.apollo_org_data->>'founded_year' as founded_year
            FROM discovered_companies dc
            LEFT JOIN search_results sr ON sr.id = dc.search_result_id
            LEFT JOIN search_jobs sj ON sj.id = COALESCE(sr.search_job_id, dc.search_job_id)
            LEFT JOIN search_queries sq ON sr.source_query_id = sq.id
            LEFT JOIN extracted_contacts ec ON ec.discovered_company_id = dc.id
            WHERE dc.project_id = :project_id
                AND dc.is_target = true
            ORDER BY dc.confidence DESC, dc.domain, ec.source, ec.is_verified DESC
        """), {"project_id": PROJECT_ID})
        rows = result.fetchall()

        logger.info(f"Total rows (contacts + companies): {len(rows)}")

        # Also add companies without contacts as standalone rows
        headers = [
            "Domain", "URL", "Company Name", "Description",
            "Location", "Industry", "Segment", "Confidence",
            "First Name", "Last Name", "Email", "Phone",
            "Job Title", "LinkedIn",
            "Contact Source", "Email Verified", "Verification Method",
            "Discovery Source", "Search Query", "Search Geo", "Search Job ID",
            "Country (Apollo)", "Employees", "Revenue", "Founded Year",
            "Reasoning",
        ]

        data = [headers]
        seen_domains = set()

        for row in rows:
            has_contact = bool(row.email or row.first_name or row.phone)

            data.append([
                row.domain or "",
                row.url or "",
                row.company_name or "",
                (row.description or "")[:200],
                row.location or "",
                row.industry or "",
                row.segment or "",
                str(row.confidence or ""),
                row.first_name or "",
                row.last_name or "",
                row.email or "",
                row.phone or "",
                row.job_title or "",
                row.linkedin_url or "",
                str(row.contact_source or ("" if not has_contact else "website")),
                "Yes" if row.is_verified else ("" if not row.email else "No"),
                row.verification_method or "",
                row.discovery_source or "",
                row.search_query or "",
                row.search_geo or "",
                str(row.search_job_id or ""),
                row.apollo_country or "",
                row.employees or "",
                row.revenue or "",
                row.founded_year or "",
                (row.reasoning or "")[:300],
            ])
            seen_domains.add(row.domain)

        # Stats
        contacts_with_email = sum(1 for r in data[1:] if r[10])  # Email column
        contacts_with_name = sum(1 for r in data[1:] if r[8] and r[9])  # First + Last name
        unique_domains = len(seen_domains)

        logger.info(f"Sheet data: {len(data)-1} rows, {unique_domains} domains, "
                     f"{contacts_with_email} with email, {contacts_with_name} with name")

        title = f"Inxy Outreach Targets — {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
        url = google_sheets_service.create_and_populate(
            title=title,
            data=data,
            share_with=SHARE_WITH,
        )

        if url:
            logger.info(f"Google Sheet created: {url}")
        else:
            logger.error("Google Sheets export FAILED — saving JSON fallback")
            fallback = "/scripts/inxy_outreach_targets.json"
            with open(fallback, "w", encoding="utf-8") as f:
                json.dump(
                    [dict(zip(headers, r)) for r in data[1:]],
                    f, indent=2, default=str, ensure_ascii=False,
                )
            logger.info(f"JSON fallback saved: {fallback}")
            url = fallback

        return url


async def main():
    start = datetime.utcnow()
    logger.info("=" * 60)
    logger.info("INXY OUTREACH PREPARATION PIPELINE")
    logger.info(f"Time: {start.isoformat()}")
    logger.info("=" * 60)

    results = {}

    # Step 1: Promote targets
    try:
        results["targets"] = await step1_promote_targets()
    except Exception as e:
        logger.error(f"Step 1 FAILED: {e}", exc_info=True)
        results["step1_error"] = str(e)

    # Step 2: Website contact extraction
    try:
        await step2_extract_website_contacts()
        results["step2"] = "done"
    except Exception as e:
        logger.error(f"Step 2 FAILED: {e}", exc_info=True)
        results["step2_error"] = str(e)

    # Step 3: Apollo enrichment
    try:
        await step3_apollo_enrichment()
        results["step3"] = "done"
    except Exception as e:
        logger.error(f"Step 3 FAILED: {e}", exc_info=True)
        results["step3_error"] = str(e)

    # Step 4: FindyMail verification
    try:
        await step4_findymail_verification()
        results["step4"] = "done"
    except Exception as e:
        logger.error(f"Step 4 FAILED: {e}", exc_info=True)
        results["step4_error"] = str(e)

    # Step 5: Google Sheet export
    try:
        results["sheet_url"] = await step5_export_google_sheet()
    except Exception as e:
        logger.error(f"Step 5 FAILED: {e}", exc_info=True)
        results["step5_error"] = str(e)

    elapsed = (datetime.utcnow() - start).total_seconds()
    logger.info("=" * 60)
    logger.info("PIPELINE COMPLETE")
    logger.info(f"Elapsed: {elapsed:.0f}s ({elapsed/60:.1f} min)")
    logger.info(f"Results: {json.dumps(results, indent=2, default=str)}")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
