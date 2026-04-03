"""
Run Apollo People enrichment for OnSocial (project 42) target companies
that have 0 contacts. Uses pipeline_service.enrich_apollo_batch().
Then re-verify and re-export to Google Sheet.
"""
import asyncio
import json
import logging
import os
import sys
from datetime import datetime

sys.path.insert(0, "/app")
os.chdir("/app")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("apollo_fill")

PROJECT_ID = 42
COMPANY_ID = 1
FINDYMAIL_API_KEY = os.environ.get("FINDYMAIL_API_KEY", "")
SHEET_ID = "1lxO7hF9RZ7OIAAF2Xyw1S3H4Yv87LbPAnFTc9lIfwZA"
SHARE_WITH = ["pn@getsally.io"]


async def main():
    from app.db import async_session_maker
    from app.services.pipeline_service import pipeline_service
    from app.services.findymail_service import findymail_service
    from app.services.email_verification_service import email_verification_service
    from app.services.google_sheets_service import google_sheets_service
    from sqlalchemy import text

    # Setup FindyMail
    findymail_service.set_api_key(FINDYMAIL_API_KEY)
    credits = await findymail_service.get_credits()
    logger.info(f"FindyMail credits: {credits}")

    async with async_session_maker() as session:
        # 1. Find target companies with 0 email contacts
        result = await session.execute(text("""
            SELECT dc.id, dc.domain, dc.status
            FROM discovered_companies dc
            WHERE dc.project_id = :pid AND dc.is_target = true
            AND NOT EXISTS (
                SELECT 1 FROM extracted_contacts ec
                WHERE ec.discovered_company_id = dc.id AND ec.email IS NOT NULL AND ec.email != ''
            )
            ORDER BY dc.domain
        """), {"pid": PROJECT_ID})
        no_contact_companies = result.fetchall()
        logger.info(f"Companies with 0 email contacts: {len(no_contact_companies)}")

        by_status = {}
        for c in no_contact_companies:
            by_status.setdefault(c.status, []).append(c)
        for status, companies in by_status.items():
            logger.info(f"  {status}: {len(companies)} companies")

        # 2. Run Apollo enrichment for all of them
        dc_ids = [c.id for c in no_contact_companies]
        if dc_ids:
            logger.info(f"Running Apollo enrichment for {len(dc_ids)} companies...")
            # Use force_retry=True to re-try even previously enriched ones
            stats = await pipeline_service.enrich_apollo_batch(
                session=session,
                discovered_company_ids=dc_ids,
                company_id=COMPANY_ID,
                max_people=5,
                max_credits=2000,
                titles=["CEO", "Founder", "Managing Director", "Head of", "Director",
                        "Owner", "Co-Founder", "Partner", "VP", "Chief"],
                force_retry=True,
            )
            logger.info(f"Apollo enrichment: {stats}")
        else:
            logger.info("No companies to enrich")
            stats = {"processed": 0, "people_found": 0}

        # 3. Now also run website contact extraction for those still with 0 contacts
        still_empty = await session.execute(text("""
            SELECT dc.id, dc.domain
            FROM discovered_companies dc
            WHERE dc.project_id = :pid AND dc.is_target = true
            AND NOT EXISTS (
                SELECT 1 FROM extracted_contacts ec
                WHERE ec.discovered_company_id = dc.id AND ec.email IS NOT NULL AND ec.email != ''
            )
            ORDER BY dc.domain
        """), {"pid": PROJECT_ID})
        still_empty_rows = still_empty.fetchall()
        logger.info(f"Still 0 contacts after Apollo: {len(still_empty_rows)}")

        if still_empty_rows:
            dc_ids_extract = [c.id for c in still_empty_rows]
            logger.info(f"Running website contact extraction for {len(dc_ids_extract)} companies...")
            extract_stats = await pipeline_service.extract_contacts_batch(
                session=session,
                discovered_company_ids=dc_ids_extract,
                company_id=COMPANY_ID,
            )
            logger.info(f"Website extraction: {extract_stats}")

        # 4. Verify all unverified emails via FindyMail
        logger.info("\nVerifying new emails via FindyMail...")
        new_emails_result = await session.execute(text("""
            SELECT ec.id, ec.email
            FROM extracted_contacts ec
            JOIN discovered_companies dc ON ec.discovered_company_id = dc.id
            WHERE dc.project_id = :pid AND dc.is_target = true
              AND ec.email IS NOT NULL AND ec.email != ''
              AND NOT EXISTS (
                  SELECT 1 FROM email_verifications ev
                  WHERE ev.email = ec.email AND ev.expires_at > now() AND ev.result != 'error'
              )
        """), {"pid": PROJECT_ID})
        new_emails = new_emails_result.fetchall()
        logger.info(f"Unverified emails: {len(new_emails)}")

        if new_emails and FINDYMAIL_API_KEY:
            email_list = [r.email.lower().strip() for r in new_emails]
            email_to_extracted = {r.email.lower().strip(): r.id for r in new_emails}
            batch_result = await email_verification_service.verify_batch(
                session=session,
                emails=email_list,
                project_id=PROJECT_ID,
                max_credits=len(email_list) + 10,
                email_to_extracted=email_to_extracted,
            )
            await session.commit()
            vstats = batch_result["stats"]
            logger.info(f"Verified: {vstats['valid']} valid, {vstats['invalid']} invalid, "
                        f"{vstats['cached']} cached, cost=${vstats['cost_usd']:.2f}")

        # 5. Re-export Google Sheet
        logger.info("\nExporting to Google Sheet...")
        campaign_emails_result = await session.execute(text("""
            SELECT DISTINCT lower(email) as email FROM contacts
            WHERE campaigns::text ILIKE '%onsocial%' AND email IS NOT NULL AND email != ''
        """))
        campaign_emails = {row.email for row in campaign_emails_result.fetchall()}

        targets = await session.execute(text("""
            SELECT DISTINCT ON (dc.domain)
                dc.domain, dc.name as company_name, dc.confidence,
                sr.company_info->>'description' as description,
                sr.company_info->>'services' as services,
                sr.company_info->>'location' as location,
                sr.company_info->>'industry' as industry,
                sr.scores->>'language_match' as language_match,
                sr.scores->>'industry_match' as industry_match,
                sr.scores->>'service_match' as service_match,
                sr.scores->>'company_type' as company_type_score,
                sr.scores->>'geography_match' as geography_match,
                sr.review_status, sr.reasoning, sr.matched_segment,
                'https://' || dc.domain as url
            FROM discovered_companies dc
            LEFT JOIN search_results sr ON sr.domain = dc.domain AND sr.project_id = dc.project_id AND sr.is_target = true
            WHERE dc.project_id = :pid AND dc.is_target = true
            ORDER BY dc.domain, dc.confidence DESC NULLS LAST
        """), {"pid": PROJECT_ID})
        target_map = {row.domain: row for row in targets.fetchall()}

        contacts_result = await session.execute(text("""
            SELECT dc.domain, ec.first_name, ec.last_name, ec.email, ec.phone,
                ec.job_title, ec.linkedin_url, ec.source, ec.is_verified
            FROM extracted_contacts ec
            JOIN discovered_companies dc ON ec.discovered_company_id = dc.id
            WHERE dc.project_id = :pid AND dc.is_target = true
                AND ec.email IS NOT NULL AND ec.email != ''
            ORDER BY dc.domain, ec.is_verified DESC, ec.source DESC
        """), {"pid": PROJECT_ID})
        domain_contacts = {}
        for c in contacts_result.fetchall():
            domain_contacts.setdefault(c.domain, []).append(c)

        verif_result = await session.execute(text("""
            SELECT email, result, is_valid, provider, verified_at
            FROM email_verifications WHERE project_id = :pid
            ORDER BY email, verified_at DESC
        """), {"pid": PROJECT_ID})
        verif_map = {}
        for v in verif_result.fetchall():
            if v.email not in verif_map:
                verif_map[v.email] = v

        meta_result = await session.execute(text("""
            SELECT sr.domain, sq.query_text, sj.search_engine, sr.matched_segment
            FROM search_results sr
            LEFT JOIN search_queries sq ON sr.source_query_id = sq.id
            LEFT JOIN search_jobs sj ON sq.search_job_id = sj.id
            WHERE sr.project_id = :pid AND sr.is_target = true
        """), {"pid": PROJECT_ID})
        domain_meta = {}
        for row in meta_result.fetchall():
            d = row.domain
            if d not in domain_meta:
                domain_meta[d] = {"queries": [], "engines": set(), "segments": set()}
            if row.query_text: domain_meta[d]["queries"].append(row.query_text)
            if row.search_engine: domain_meta[d]["engines"].add(str(row.search_engine))
            if row.matched_segment: domain_meta[d]["segments"].add(row.matched_segment)

        headers = [
            "First Name", "Last Name", "Email", "Job Title", "LinkedIn",
            "Phone", "Contact Source", "Apollo Verified",
            "FindyMail Result", "FindyMail Valid", "Email Provider", "Verified At",
            "In Campaign",
            "Domain", "URL", "Company Name", "Description",
            "Industry", "Services", "Location",
            "Confidence", "Language", "Industry Match", "Service Match",
            "Company Type", "Geography",
            "Review Status", "Search Engine", "Segment", "Source Query",
            "Reasoning",
        ]
        data = [headers]
        new_ct = 0
        camp_ct = 0
        no_ct = 0

        for domain in sorted(target_map.keys()):
            row = target_map[domain]
            contacts = domain_contacts.get(domain, [])

            services = row.services
            if services:
                try:
                    sl = json.loads(services) if isinstance(services, str) else services
                    services = ", ".join(sl) if isinstance(sl, list) else str(services)
                except Exception:
                    pass

            meta = domain_meta.get(domain, {})
            engines = ", ".join(meta.get("engines", set()))
            segments = ", ".join(meta.get("segments", set()))
            queries = meta.get("queries", [])
            source_query = queries[0] if queries else ""

            company_cols = [
                row.domain, row.url, row.company_name or "", row.description or "",
                row.industry or "", services or "", row.location or "",
            ]
            score_cols = [
                str(row.confidence or ""), str(row.language_match or ""),
                str(row.industry_match or ""), str(row.service_match or ""),
                str(row.company_type_score or ""), str(row.geography_match or ""),
            ]
            search_cols = [row.review_status or "", engines, segments, source_query]
            reasoning_col = [row.reasoning or ""]

            if not contacts:
                contact_cols = ["", "", "NO CONTACTS", "", "", "", "", "", "", "", "", "", ""]
                data.append(contact_cols + company_cols + score_cols + search_cols + reasoning_col)
                no_ct += 1
                continue

            for c in contacts:
                email_lower = c.email.lower().strip()
                in_campaign = "YES" if email_lower in campaign_emails else ""
                verif = verif_map.get(email_lower)
                contact_cols = [
                    c.first_name or "", c.last_name or "", c.email, c.job_title or "",
                    c.linkedin_url or "", c.phone or "", str(c.source or ""),
                    "Yes" if c.is_verified else "",
                    verif.result if verif else "",
                    "Yes" if verif and verif.is_valid else ("No" if verif and verif.is_valid is False else ""),
                    verif.provider if verif else "",
                    str(verif.verified_at)[:19] if verif else "",
                    in_campaign,
                ]
                data.append(contact_cols + company_cols + score_cols + search_cols + reasoning_col)
                if in_campaign:
                    camp_ct += 1
                else:
                    new_ct += 1

        logger.info(f"Sheet: {len(data)-1} rows ({new_ct} new, {camp_ct} in campaigns, {no_ct} no-contacts)")

        google_sheets_service._initialize()
        sheets = google_sheets_service.sheets_service
        if sheets:
            try:
                sheets.spreadsheets().values().clear(spreadsheetId=SHEET_ID, range="Sheet1").execute()
                sheets.spreadsheets().values().update(
                    spreadsheetId=SHEET_ID, range="Sheet1!A1",
                    valueInputOption="RAW", body={"values": data},
                ).execute()
                logger.info(f"SUCCESS: https://docs.google.com/spreadsheets/d/{SHEET_ID}")
            except Exception as e:
                logger.error(f"Sheet failed: {e}")
                url = google_sheets_service.create_and_populate(
                    title=f"OnSocial Contacts — {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
                    data=data, share_with=SHARE_WITH,
                )
                logger.info(f"New sheet: {url}")

        # Final count
        final_zero = await session.execute(text("""
            SELECT COUNT(*) FROM discovered_companies dc
            WHERE dc.project_id = :pid AND dc.is_target = true
            AND NOT EXISTS (
                SELECT 1 FROM extracted_contacts ec
                WHERE ec.discovered_company_id = dc.id AND ec.email IS NOT NULL AND ec.email != ''
            )
        """), {"pid": PROJECT_ID})
        remaining = final_zero.scalar()

        print("\n" + "=" * 60)
        print("ONSOCIAL APOLLO FILL SUMMARY")
        print("=" * 60)
        print(f"Apollo enrichment: {stats}")
        print(f"Remaining companies with 0 contacts: {remaining}")
        print(f"\nSheet: {new_ct} new + {camp_ct} in campaigns + {no_ct} no-contacts = {len(data)-1} rows")
        print(f"https://docs.google.com/spreadsheets/d/{SHEET_ID}")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
