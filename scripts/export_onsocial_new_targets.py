"""
Export OnSocial (project 42) NEW target contacts to Google Sheets.
Excludes all contacts already in OnSocial SmartLead campaigns.
Format: ONE ROW PER CONTACT (Smartlead-compatible).
Marks Apollo vs Website contacts for FindyMail verification needs.
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
logger = logging.getLogger("export_onsocial_new")

PROJECT_ID = 42
COMPANY_ID = 1
SHARE_WITH = ["pn@getsally.io"]
SHEET_ID = "1lxO7hF9RZ7OIAAF2Xyw1S3H4Yv87LbPAnFTc9lIfwZA"


async def main():
    from app.db import async_session_maker
    from app.services.google_sheets_service import google_sheets_service
    from sqlalchemy import text

    async with async_session_maker() as session:
        # 1. Get all emails already in OnSocial SmartLead campaigns
        campaign_emails_result = await session.execute(text("""
            SELECT DISTINCT lower(email) as email
            FROM contacts
            WHERE campaigns::text ILIKE '%onsocial%'
              AND email IS NOT NULL AND email != ''
        """))
        campaign_emails = {row.email for row in campaign_emails_result.fetchall()}
        logger.info(f"Excluding {len(campaign_emails)} emails already in OnSocial campaigns")

        # 2. Load all targets with search result info (deduplicate by domain)
        targets = await session.execute(text("""
            SELECT DISTINCT ON (dc.domain)
                dc.id as dc_id,
                dc.domain,
                dc.name as company_name,
                dc.confidence,
                dc.contacts_count,
                dc.status as dc_status,
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
        target_rows = targets.fetchall()
        logger.info(f"Loaded {len(target_rows)} unique target companies")

        # Collect all queries/engines per domain
        meta_result = await session.execute(text("""
            SELECT
                sr.domain,
                sq.query_text,
                sj.search_engine,
                sr.matched_segment
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

        # 3. Load ALL contacts for target companies
        contacts_result = await session.execute(text("""
            SELECT
                dc.domain,
                ec.first_name,
                ec.last_name,
                ec.email,
                ec.phone,
                ec.job_title,
                ec.linkedin_url,
                ec.source,
                ec.is_verified
            FROM extracted_contacts ec
            JOIN discovered_companies dc ON ec.discovered_company_id = dc.id
            WHERE dc.project_id = :pid AND dc.is_target = true
            ORDER BY dc.domain, ec.is_verified DESC, ec.source DESC
        """), {"pid": PROJECT_ID})
        contact_rows = contacts_result.fetchall()

        domain_contacts = {}
        for c in contact_rows:
            domain_contacts.setdefault(c.domain, []).append(c)

        logger.info(f"Loaded contacts for {len(domain_contacts)} domains ({len(contact_rows)} total)")

        # 4. Build sheet — ONE ROW PER CONTACT, excluding campaign emails
        headers = [
            "First Name", "Last Name", "Email", "Job Title", "LinkedIn",
            "Phone", "Contact Source", "Verified", "Needs FindyMail",
            "Domain", "URL", "Company Name", "Description",
            "Industry", "Services", "Location",
            "Confidence", "Language", "Industry Match", "Service Match",
            "Company Type", "Geography",
            "Review Status", "Search Engine", "Segment", "Source Query",
            "Reasoning",
        ]

        data = [headers]
        included_contacts = 0
        excluded_contacts = 0
        companies_with_new_contacts = 0
        companies_no_new_contacts = 0

        for row in target_rows:
            services = row.services
            if services:
                try:
                    sl = json.loads(services) if isinstance(services, str) else services
                    services = ", ".join(sl) if isinstance(sl, list) else str(services)
                except Exception:
                    pass

            meta = domain_meta.get(row.domain, {})
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

            contacts = domain_contacts.get(row.domain, [])
            company_had_new = False
            for c in contacts:
                if not c.email:
                    continue
                # EXCLUDE if already in OnSocial campaigns
                if c.email.lower() in campaign_emails:
                    excluded_contacts += 1
                    continue

                # Mark if needs FindyMail verification
                # Apollo contacts may have is_verified from Apollo but should still verify in FindyMail
                # Website-scraped contacts definitely need verification
                needs_findymail = "Yes" if c.source == "WEBSITE_SCRAPE" or not c.is_verified else ""

                contact_cols = [
                    c.first_name or "", c.last_name or "",
                    c.email or "", c.job_title or "",
                    c.linkedin_url or "", c.phone or "",
                    str(c.source or ""),
                    "Yes" if c.is_verified else "",
                    needs_findymail,
                ]
                data.append(contact_cols + company_cols + score_cols + search_cols + reasoning_col)
                included_contacts += 1
                company_had_new = True

            if company_had_new:
                companies_with_new_contacts += 1
            elif contacts:
                companies_no_new_contacts += 1

        logger.info(f"Sheet: {len(data)-1} rows")
        logger.info(f"Included: {included_contacts} new contacts from {companies_with_new_contacts} companies")
        logger.info(f"Excluded: {excluded_contacts} contacts (already in campaigns)")
        logger.info(f"Companies with all contacts in campaigns: {companies_no_new_contacts}")

        # 5. Also add companies WITH NO CONTACTS at the bottom (for reference)
        no_contact_rows = 0
        for row in target_rows:
            contacts = domain_contacts.get(row.domain, [])
            new_contacts = [c for c in contacts if c.email and c.email.lower() not in campaign_emails]
            if len(new_contacts) == 0:
                services = row.services
                if services:
                    try:
                        sl = json.loads(services) if isinstance(services, str) else services
                        services = ", ".join(sl) if isinstance(sl, list) else str(services)
                    except Exception:
                        pass

                meta = domain_meta.get(row.domain, {})
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

                contact_cols = ["", "", "NO CONTACTS YET", "", "", "", "", "", ""]
                data.append(contact_cols + company_cols + score_cols + search_cols + reasoning_col)
                no_contact_rows += 1

        logger.info(f"Added {no_contact_rows} target companies without new contacts (for reference)")

        # 6. Write to Google Sheet
        google_sheets_service._initialize()
        sheets = google_sheets_service.sheets_service

        if sheets:
            try:
                sheets.spreadsheets().values().clear(
                    spreadsheetId=SHEET_ID,
                    range="Sheet1",
                ).execute()
                logger.info("Cleared existing sheet data")

                sheets.spreadsheets().values().update(
                    spreadsheetId=SHEET_ID,
                    range="Sheet1!A1",
                    valueInputOption="RAW",
                    body={"values": data},
                ).execute()
                logger.info(f"SUCCESS: wrote {len(data)-1} rows to https://docs.google.com/spreadsheets/d/{SHEET_ID}")
            except Exception as e:
                logger.error(f"Sheet update failed: {e}")
                url = google_sheets_service.create_and_populate(
                    title=f"OnSocial NEW Targets — {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
                    data=data,
                    share_with=SHARE_WITH,
                )
                logger.info(f"Created new sheet: {url}")
        else:
            logger.error("Google Sheets not initialized!")
            fallback = "/scripts/onsocial_new_targets.json"
            with open(fallback, "w", encoding="utf-8") as f:
                json.dump(
                    [dict(zip(headers, r)) for r in data[1:]],
                    f, indent=2, default=str, ensure_ascii=False,
                )
            logger.info(f"JSON fallback: {fallback}")

        # 7. Print summary
        print("\n" + "="*60)
        print("ONSOCIAL PROJECT 42 — EXPORT SUMMARY")
        print("="*60)
        print(f"Total target companies: {len(target_rows)}")
        print(f"Companies with new contacts: {companies_with_new_contacts}")
        print(f"New contacts exported: {included_contacts}")
        print(f"Contacts excluded (in campaigns): {excluded_contacts}")
        print(f"Target companies without contacts: {no_contact_rows}")
        print(f"Total rows in sheet: {len(data)-1}")
        print(f"\nSheet: https://docs.google.com/spreadsheets/d/{SHEET_ID}")
        print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
