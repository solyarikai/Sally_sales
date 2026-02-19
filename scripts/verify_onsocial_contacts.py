"""
Verify OnSocial (project 42) extracted contacts via FindyMail.
Uses existing email_verification_service with 90-day cache.
Then re-exports to Google Sheet with verification results.
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
logger = logging.getLogger("verify_onsocial")

PROJECT_ID = 42
FINDYMAIL_API_KEY = os.environ.get("FINDYMAIL_API_KEY", "")
SHEET_ID = "1lxO7hF9RZ7OIAAF2Xyw1S3H4Yv87LbPAnFTc9lIfwZA"
SHARE_WITH = ["pn@getsally.io"]
MAX_CREDITS = 500  # budget cap


async def main():
    from app.db import async_session_maker
    from app.services.findymail_service import findymail_service
    from app.services.email_verification_service import email_verification_service
    from app.services.google_sheets_service import google_sheets_service
    from sqlalchemy import text

    # 1. Connect FindyMail
    findymail_service.set_api_key(FINDYMAIL_API_KEY)
    if not findymail_service.is_connected():
        logger.error("FindyMail API key not set!")
        return

    credits = await findymail_service.get_credits()
    logger.info(f"FindyMail credits: {credits}")

    async with async_session_maker() as session:
        # 2. Get emails already in OnSocial campaigns (exclude from sheet but still verify all)
        campaign_emails_result = await session.execute(text("""
            SELECT DISTINCT lower(email) as email
            FROM contacts
            WHERE campaigns::text ILIKE '%onsocial%'
              AND email IS NOT NULL AND email != ''
        """))
        campaign_emails = {row.email for row in campaign_emails_result.fetchall()}
        logger.info(f"Found {len(campaign_emails)} emails in OnSocial campaigns")

        # 3. Get ALL extracted contacts for target companies
        contacts_result = await session.execute(text("""
            SELECT
                ec.id as ec_id,
                ec.email,
                ec.first_name,
                ec.last_name,
                ec.job_title,
                ec.linkedin_url,
                ec.phone,
                ec.source,
                ec.is_verified,
                ec.verification_method,
                dc.id as dc_id,
                dc.domain,
                dc.name as company_name
            FROM extracted_contacts ec
            JOIN discovered_companies dc ON ec.discovered_company_id = dc.id
            WHERE dc.project_id = :pid
              AND dc.is_target = true
              AND ec.email IS NOT NULL
              AND ec.email != ''
            ORDER BY dc.domain, ec.source DESC
        """), {"pid": PROJECT_ID})
        all_contacts = contacts_result.fetchall()
        logger.info(f"Total contacts to verify: {len(all_contacts)}")

        # 4. Build maps for linking verification records back
        email_to_extracted = {}
        emails_to_verify = []
        for c in all_contacts:
            email_lower = c.email.lower().strip()
            if email_lower not in email_to_extracted:
                email_to_extracted[email_lower] = c.ec_id
                emails_to_verify.append(email_lower)

        logger.info(f"Unique emails to verify: {len(emails_to_verify)}")

        # 5. Run batch verification (respects 90-day cache)
        logger.info(f"Starting FindyMail verification (budget: {MAX_CREDITS} credits)...")
        batch_result = await email_verification_service.verify_batch(
            session=session,
            emails=emails_to_verify,
            project_id=PROJECT_ID,
            max_credits=MAX_CREDITS,
            email_to_extracted=email_to_extracted,
        )
        await session.commit()

        stats = batch_result["stats"]
        results = batch_result["results"]
        logger.info(f"Verification complete: {stats}")
        logger.info(f"  Valid: {stats['valid']}, Invalid: {stats['invalid']}, "
                     f"Cached: {stats['cached']}, Errors: {stats['errors']}, "
                     f"Cost: ${stats['cost_usd']:.2f}")

        # 6. Now re-export to Google Sheet with verification results
        # Load target company info
        targets = await session.execute(text("""
            SELECT DISTINCT ON (dc.domain)
                dc.domain,
                dc.name as company_name,
                dc.confidence,
                sr.company_info->>'description' as description,
                sr.company_info->>'services' as services,
                sr.company_info->>'location' as location,
                sr.company_info->>'industry' as industry,
                sr.scores->>'language_match' as language_match,
                sr.scores->>'industry_match' as industry_match,
                sr.scores->>'service_match' as service_match,
                sr.scores->>'company_type' as company_type_score,
                sr.scores->>'geography_match' as geography_match,
                sr.review_status,
                sr.reasoning,
                sr.matched_segment,
                'https://' || dc.domain as url
            FROM discovered_companies dc
            LEFT JOIN search_results sr ON sr.domain = dc.domain AND sr.project_id = dc.project_id AND sr.is_target = true
            WHERE dc.project_id = :pid AND dc.is_target = true
            ORDER BY dc.domain, dc.confidence DESC NULLS LAST
        """), {"pid": PROJECT_ID})
        target_rows = {row.domain: row for row in targets.fetchall()}

        # Collect search metadata
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
            if row.query_text:
                domain_meta[d]["queries"].append(row.query_text)
            if row.search_engine:
                domain_meta[d]["engines"].add(str(row.search_engine))
            if row.matched_segment:
                domain_meta[d]["segments"].add(row.matched_segment)

        # Load ALL verification history for these emails
        verif_result = await session.execute(text("""
            SELECT email, result, is_valid, provider, verified_at, service
            FROM email_verifications
            WHERE project_id = :pid
            ORDER BY email, verified_at DESC
        """), {"pid": PROJECT_ID})
        verif_map = {}
        for v in verif_result.fetchall():
            if v.email not in verif_map:
                verif_map[v.email] = v  # latest only

        # 7. Build sheet
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
        new_contacts = 0
        campaign_contacts = 0

        # Group contacts by domain
        domain_contacts = {}
        for c in all_contacts:
            domain_contacts.setdefault(c.domain, []).append(c)

        for domain in sorted(target_rows.keys()):
            row = target_rows[domain]
            contacts = domain_contacts.get(domain, [])
            if not contacts:
                continue

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
                str(row.confidence or ""),
                str(row.language_match or ""), str(row.industry_match or ""),
                str(row.service_match or ""), str(row.company_type_score or ""),
                str(row.geography_match or ""),
            ]
            search_cols = [
                row.review_status or "", engines, segments, source_query,
            ]
            reasoning_col = [row.reasoning or ""]

            for c in contacts:
                if not c.email:
                    continue

                email_lower = c.email.lower().strip()
                in_campaign = "YES" if email_lower in campaign_emails else ""
                verif = verif_map.get(email_lower)

                contact_cols = [
                    c.first_name or "", c.last_name or "",
                    c.email, c.job_title or "",
                    c.linkedin_url or "", c.phone or "",
                    str(c.source or ""),
                    "Yes" if c.is_verified else "",
                    verif.result if verif else "",
                    "Yes" if verif and verif.is_valid else ("No" if verif and verif.is_valid is False else ""),
                    verif.provider if verif else "",
                    str(verif.verified_at)[:19] if verif else "",
                    in_campaign,
                ]
                data.append(contact_cols + company_cols + score_cols + search_cols + reasoning_col)

                if in_campaign:
                    campaign_contacts += 1
                else:
                    new_contacts += 1

        # Add companies with NO contacts
        no_contact_count = 0
        for domain in sorted(target_rows.keys()):
            if domain not in domain_contacts or not any(c.email for c in domain_contacts.get(domain, [])):
                row = target_rows[domain]
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
                    str(row.confidence or ""),
                    str(row.language_match or ""), str(row.industry_match or ""),
                    str(row.service_match or ""), str(row.company_type_score or ""),
                    str(row.geography_match or ""),
                ]
                search_cols = [row.review_status or "", engines, segments, source_query]
                reasoning_col = [row.reasoning or ""]
                contact_cols = ["", "", "NO CONTACTS", "", "", "", "", "", "", "", "", "", ""]
                data.append(contact_cols + company_cols + score_cols + search_cols + reasoning_col)
                no_contact_count += 1

        logger.info(f"Sheet: {len(data)-1} rows ({new_contacts} new + {campaign_contacts} in campaigns + {no_contact_count} no-contacts)")

        # 8. Write to Google Sheet
        google_sheets_service._initialize()
        sheets = google_sheets_service.sheets_service

        if sheets:
            try:
                sheets.spreadsheets().values().clear(
                    spreadsheetId=SHEET_ID, range="Sheet1",
                ).execute()
                sheets.spreadsheets().values().update(
                    spreadsheetId=SHEET_ID, range="Sheet1!A1",
                    valueInputOption="RAW",
                    body={"values": data},
                ).execute()
                logger.info(f"SUCCESS: wrote {len(data)-1} rows to https://docs.google.com/spreadsheets/d/{SHEET_ID}")
            except Exception as e:
                logger.error(f"Sheet update failed: {e}")
                url = google_sheets_service.create_and_populate(
                    title=f"OnSocial Verified — {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
                    data=data, share_with=SHARE_WITH,
                )
                logger.info(f"Created new sheet: {url}")
        else:
            logger.error("Google Sheets not initialized!")

        # 9. Print summary
        valid_count = sum(1 for r in results.values() if r.get("result") == "valid")
        invalid_count = sum(1 for r in results.values() if r.get("result") in ("invalid", "catch_all"))
        print("\n" + "=" * 60)
        print("ONSOCIAL FINDYMAIL VERIFICATION SUMMARY")
        print("=" * 60)
        print(f"Unique emails processed: {len(emails_to_verify)}")
        print(f"  Valid: {valid_count}")
        print(f"  Invalid: {invalid_count}")
        print(f"  Cached (skipped): {stats['cached']}")
        print(f"  Errors: {stats['errors']}")
        print(f"  API credits used: {stats['verified'] - stats['cached']}")
        print(f"  Cost: ${stats['cost_usd']:.2f}")
        print(f"\nSheet rows: {len(data)-1}")
        print(f"  New contacts (not in campaigns): {new_contacts}")
        print(f"  In campaigns: {campaign_contacts}")
        print(f"  Companies without contacts: {no_contact_count}")
        print(f"\nSheet: https://docs.google.com/spreadsheets/d/{SHEET_ID}")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
