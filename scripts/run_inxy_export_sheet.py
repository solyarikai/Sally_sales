"""
Inxy outreach-ready export:
1. Verify ALL unverified website/subpage emails via FindyMail
2. For Apollo contacts without email but with name — try FindyMail find
3. Export ONLY rows with verified emails OR website/subpage emails to Google Sheet
"""
import asyncio
import json
import logging
import os
import sys
from datetime import datetime

sys.path.insert(0, "/app")
os.chdir("/app")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", stream=sys.stdout)
logger = logging.getLogger("inxy_export")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

PROJECT_ID = 48
SHARE_WITH = ["pn@getsally.io"]


async def step1_findymail_apollo():
    """
    FindyMail processing for Apollo contacts:
    1. Verify ALL Apollo emails (even those Apollo marked verified)
    2. If invalid → try FindyMail to find correct email
    3. For Apollo contacts without email → try FindyMail find by name+domain
    Website emails are NOT touched — they go to sheet as-is.
    """
    from app.db import async_session_maker
    from app.services.findymail_service import findymail_service
    from app.models.pipeline import ExtractedContact, DiscoveredCompany, ContactSource
    from app.core.config import settings
    from sqlalchemy import select

    if hasattr(settings, "FINDYMAIL_API_KEY") and settings.FINDYMAIL_API_KEY:
        findymail_service.set_api_key(settings.FINDYMAIL_API_KEY)
    elif os.environ.get("FINDYMAIL_API_KEY"):
        findymail_service.set_api_key(os.environ["FINDYMAIL_API_KEY"])

    if not findymail_service.is_connected():
        logger.warning("FindyMail not configured — skipping")
        return

    credits = await findymail_service.get_credits()
    logger.info(f"FindyMail credits: {credits}")

    async with async_session_maker() as session:
        dc_ids_q = await session.execute(
            select(DiscoveredCompany.id).where(
                DiscoveredCompany.project_id == PROJECT_ID,
                DiscoveredCompany.is_target == True,
            )
        )
        dc_ids = [r[0] for r in dc_ids_q.fetchall()]

        # 1. ALL Apollo contacts with email that haven't been FindyMail-verified yet
        apollo_with_email_q = await session.execute(
            select(ExtractedContact).where(
                ExtractedContact.discovered_company_id.in_(dc_ids),
                ExtractedContact.email.isnot(None),
                ExtractedContact.source == ContactSource.APOLLO,
                # Skip those already processed by findymail
                ExtractedContact.verification_method.notin_(["findymail", "findymail_found"]),
            )
        )
        to_verify = apollo_with_email_q.scalars().all()
        logger.info(f"Apollo emails to verify via FindyMail: {len(to_verify)}")

        verified = 0
        invalid = 0
        replaced = 0
        for ec in to_verify:
            try:
                result = await findymail_service.verify_email(ec.email)
                if result.get("success"):
                    is_valid = result.get("verified", False)
                    if is_valid:
                        ec.is_verified = True
                        ec.verification_method = "findymail"
                        verified += 1
                    else:
                        # Invalid — try to find correct email via FindyMail
                        ec.is_verified = False
                        ec.verification_method = "findymail"
                        invalid += 1

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
                                    replaced += 1
                                    logger.info(f"  Replaced: {ec.first_name} {ec.last_name}@{domain} → {ec.email}")
                else:
                    ec.verification_method = "findymail_error"
            except Exception as e:
                logger.error(f"Verify error {ec.email}: {e}")

            total_done = verified + invalid
            if total_done % 20 == 0 and total_done > 0:
                await session.commit()
                logger.info(f"  Verify progress: {verified} valid, {invalid} invalid, {replaced} replaced")

        # 2. Apollo contacts WITHOUT email — try FindyMail find via LinkedIn or name+domain
        no_email_q = await session.execute(
            select(ExtractedContact).where(
                ExtractedContact.discovered_company_id.in_(dc_ids),
                ExtractedContact.email.is_(None),
                ExtractedContact.source == ContactSource.APOLLO,
                ExtractedContact.verification_method.is_(None),
            )
        )
        no_email = no_email_q.scalars().all()
        logger.info(f"Apollo contacts without email to find: {len(no_email)}")

        found_linkedin = 0
        found_name = 0
        for ec in no_email:
            try:
                # Try LinkedIn first (higher quality)
                if ec.linkedin_url:
                    result = await findymail_service.find_email_by_linkedin(ec.linkedin_url)
                    if result.get("success") and result.get("email"):
                        ec.email = result["email"]
                        ec.is_verified = result.get("verified", False)
                        ec.verification_method = "findymail_linkedin"
                        found_linkedin += 1
                        continue

                # Fallback to name+domain
                if ec.first_name and ec.last_name:
                    dc_q = await session.execute(
                        select(DiscoveredCompany.domain).where(DiscoveredCompany.id == ec.discovered_company_id)
                    )
                    domain = dc_q.scalar()
                    if domain:
                        result = await findymail_service.find_email_by_name(
                            f"{ec.first_name} {ec.last_name}", domain
                        )
                        if result.get("success") and result.get("email"):
                            ec.email = result["email"]
                            ec.is_verified = result.get("verified", False)
                            ec.verification_method = "findymail_found"
                            found_name += 1
            except Exception as e:
                logger.error(f"Find error {ec.first_name} {ec.last_name}: {e}")

        # 3. Also try LinkedIn for Apollo contacts that HAVE email but also have LinkedIn
        #    (to maximize verified emails from FindyMail)
        apollo_with_linkedin_q = await session.execute(
            select(ExtractedContact).where(
                ExtractedContact.discovered_company_id.in_(dc_ids),
                ExtractedContact.source == ContactSource.APOLLO,
                ExtractedContact.linkedin_url.isnot(None),
                ExtractedContact.verification_method.is_(None),  # not yet findymail-processed
                ExtractedContact.email.is_(None),  # no email yet after step above
            )
        )
        # Already covered above, this is just a safety net

        await session.commit()
        logger.info(f"FindyMail DONE: {verified} verified, {invalid} invalid, {replaced} replaced, "
                     f"found_linkedin={found_linkedin}, found_name={found_name}")


async def step2_export_clean_sheet():
    """Export only outreach-ready contacts: verified emails + website emails."""
    from app.db import async_session_maker
    from app.services.google_sheets_service import google_sheets_service
    from sqlalchemy import text

    async with async_session_maker() as session:
        # Final sheet logic:
        # 1. Website/subpage emails → include as-is (general company emails)
        # 2. Apollo/FindyMail emails → only if verified by FindyMail (verification_method LIKE 'findymail%')
        #    This excludes raw Apollo emails that weren't FindyMail-verified
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
                ec.first_name,
                ec.last_name,
                ec.email,
                ec.phone,
                ec.job_title,
                ec.linkedin_url,
                ec.source as contact_source,
                ec.is_verified,
                ec.verification_method,
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
                dc.apollo_org_data->>'country' as apollo_country,
                dc.apollo_org_data->>'estimated_num_employees' as employees,
                dc.apollo_org_data->>'annual_revenue_printed' as revenue,
                dc.apollo_org_data->>'founded_year' as founded_year
            FROM discovered_companies dc
            LEFT JOIN search_results sr ON sr.id = dc.search_result_id
            LEFT JOIN search_jobs sj ON sj.id = COALESCE(sr.search_job_id, dc.search_job_id)
            LEFT JOIN search_queries sq ON sr.source_query_id = sq.id
            JOIN extracted_contacts ec ON ec.discovered_company_id = dc.id
            WHERE dc.project_id = :project_id
                AND dc.is_target = true
                AND ec.email IS NOT NULL
                AND (
                    -- Website/subpage emails: include as-is
                    ec.source IN ('WEBSITE_SCRAPE', 'SUBPAGE_SCRAPE')
                    -- Apollo emails: only if FindyMail verified or found
                    OR (ec.source = 'APOLLO' AND ec.verification_method LIKE 'findymail%%' AND ec.is_verified = true)
                )
            ORDER BY dc.domain, ec.source, ec.is_verified DESC
        """), {"project_id": PROJECT_ID})
        rows = result.fetchall()

    logger.info(f"Outreach-ready contacts: {len(rows)}")

    unique_domains = set()
    for r in rows:
        unique_domains.add(r.domain)
    logger.info(f"Unique companies: {len(unique_domains)}")

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
    for row in rows:
        data.append([
            row.domain or "", row.url or "", row.company_name or "",
            (row.description or "")[:200], row.location or "", row.industry or "",
            row.segment or "", str(row.confidence or ""),
            row.first_name or "", row.last_name or "",
            row.email or "", row.phone or "",
            row.job_title or "", row.linkedin_url or "",
            str(row.contact_source or ""), "Yes" if row.is_verified else "No",
            row.verification_method or "",
            row.discovery_source or "", row.search_query or "",
            row.search_geo or "", str(row.search_job_id or ""),
            row.apollo_country or "", row.employees or "",
            row.revenue or "", row.founded_year or "",
            (row.reasoning or "")[:300],
        ])

    logger.info(f"Exporting {len(data)-1} rows to Google Sheets...")

    title = f"Inxy Outreach Ready — {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
    url = google_sheets_service.create_and_populate(title=title, data=data, share_with=SHARE_WITH)

    if url:
        logger.info(f"SUCCESS: {url}")
    else:
        logger.error("Google Sheets FAILED")
        with open("/scripts/inxy_outreach_ready.json", "w") as f:
            json.dump([dict(zip(headers, r)) for r in data[1:]], f, indent=2, default=str, ensure_ascii=False)
        logger.info("JSON fallback saved: /scripts/inxy_outreach_ready.json")


async def main():
    logger.info("=" * 60)
    logger.info("INXY OUTREACH EXPORT — FindyMail verify + clean sheet")
    logger.info("=" * 60)

    await step1_findymail_apollo()
    await step2_export_clean_sheet()


if __name__ == "__main__":
    asyncio.run(main())
