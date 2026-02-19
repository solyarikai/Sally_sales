"""
Export OnSocial (project 42) NEW + VERIFIED contacts to Google Sheet.
SmartLead-ready + analytics-rich: segment, source query, search engine,
scores, costs, verification status — everything needed for analysis.
Only valid FindyMail emails, excludes campaign duplicates.
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
logger = logging.getLogger("smartlead_export")

PROJECT_ID = 42
SHEET_ID = "1lxO7hF9RZ7OIAAF2Xyw1S3H4Yv87LbPAnFTc9lIfwZA"
SHARE_WITH = ["pn@getsally.io"]


async def main():
    from app.db import async_session_maker
    from app.services.google_sheets_service import google_sheets_service
    from sqlalchemy import text

    async with async_session_maker() as session:
        # 1. Emails already in OnSocial campaigns
        campaign_result = await session.execute(text("""
            SELECT DISTINCT lower(email) as email FROM contacts
            WHERE campaigns::text ILIKE '%onsocial%'
              AND email IS NOT NULL AND email != ''
              AND campaigns::text LIKE '[%'
        """))
        campaign_emails = {row.email for row in campaign_result.fetchall()}
        logger.info(f"Excluding {len(campaign_emails)} emails already in OnSocial campaigns")

        # 2. Load ALL search result data per domain (multiple queries can find same domain)
        meta_result = await session.execute(text("""
            SELECT
                sr.domain,
                sr.matched_segment,
                sr.scores,
                sr.review_status,
                sr.review_note,
                sr.confidence as sr_confidence,
                sr.reasoning,
                sr.company_info,
                sq.query_text,
                sj.search_engine::text as search_engine,
                sj.id as job_id
            FROM search_results sr
            LEFT JOIN search_queries sq ON sr.source_query_id = sq.id
            LEFT JOIN search_jobs sj ON sq.search_job_id = sj.id
            WHERE sr.project_id = :pid AND sr.is_target = true
            ORDER BY sr.domain, sr.confidence DESC NULLS LAST
        """), {"pid": PROJECT_ID})
        domain_meta = {}
        for row in meta_result.fetchall():
            d = row.domain
            if d not in domain_meta:
                domain_meta[d] = {
                    "queries": [],
                    "engines": set(),
                    "segments": set(),
                    "scores": row.scores,
                    "review_status": row.review_status,
                    "review_note": row.review_note,
                    "sr_confidence": row.sr_confidence,
                    "reasoning": row.reasoning,
                    "company_info": row.company_info,
                }
            if row.query_text and row.query_text not in domain_meta[d]["queries"]:
                domain_meta[d]["queries"].append(row.query_text)
            if row.search_engine:
                domain_meta[d]["engines"].add(row.search_engine)
            if row.matched_segment:
                domain_meta[d]["segments"].add(row.matched_segment)

        # 3. Load discovered company data (costs, status)
        dc_result = await session.execute(text("""
            SELECT
                dc.id, dc.domain, dc.name, dc.confidence,
                dc.status, dc.matched_segment as dc_segment,
                dc.apollo_credits_used, dc.apollo_people_count,
                dc.contacts_count
            FROM discovered_companies dc
            WHERE dc.project_id = :pid AND dc.is_target = true
        """), {"pid": PROJECT_ID})
        dc_map = {row.domain: row for row in dc_result.fetchall()}

        # 4. Load enrichment attempts per company (costs, methods used)
        ea_result = await session.execute(text("""
            SELECT
                ea.discovered_company_id,
                ea.source_type,
                ea.method,
                ea.status,
                ea.credits_used,
                ea.contacts_found,
                ea.emails_found
            FROM enrichment_attempts ea
            JOIN discovered_companies dc ON ea.discovered_company_id = dc.id
            WHERE dc.project_id = :pid AND dc.is_target = true
        """), {"pid": PROJECT_ID})
        dc_attempts = {}
        for row in ea_result.fetchall():
            dc_attempts.setdefault(row.discovered_company_id, []).append(row)

        # 5. Get verified contacts with FindyMail results
        contacts_result = await session.execute(text("""
            SELECT DISTINCT ON (lower(ec.email))
                ec.id as ec_id,
                ec.first_name,
                ec.last_name,
                ec.email,
                ec.job_title,
                ec.linkedin_url,
                ec.phone,
                ec.source,
                ec.is_verified as apollo_verified,
                ec.discovered_company_id,
                dc.domain,
                dc.name as company_name,
                'https://' || dc.domain as url,
                ev.result as fm_result,
                ev.is_valid as fm_valid,
                ev.provider as email_provider,
                ev.cost_usd as fm_cost,
                ev.verified_at as fm_verified_at
            FROM extracted_contacts ec
            JOIN discovered_companies dc ON ec.discovered_company_id = dc.id
            JOIN email_verifications ev ON ev.email = lower(ec.email)
                AND ev.project_id = :pid AND ev.is_valid = true
            WHERE dc.project_id = :pid AND dc.is_target = true
              AND ec.email IS NOT NULL AND ec.email != ''
            ORDER BY lower(ec.email), ec.is_verified DESC, ec.source DESC
        """), {"pid": PROJECT_ID})
        contacts = contacts_result.fetchall()
        logger.info(f"Total verified contacts: {len(contacts)}")

        # 6. Build analytics-rich sheet
        headers = [
            # ── SmartLead core fields ──
            "email", "first_name", "last_name", "company_name", "company_url",
            # ── Contact details ──
            "job_title", "linkedin_url", "phone",
            # ── Contact source & verification ──
            "contact_source", "apollo_verified", "findymail_result",
            "email_provider", "findymail_verified_at",
            # ── Company classification (our scoring) ──
            "segment", "confidence",
            "score_language", "score_industry", "score_service",
            "score_company_type", "score_geography",
            # ── Company info ──
            "description", "services", "location", "company_type", "employees",
            # ── Search discovery ──
            "search_engine", "source_query", "all_queries", "queries_count",
            # ── Pipeline tracking ──
            "review_status", "review_note",
            "apollo_credits", "enrichment_methods",
            "reasoning",
        ]

        data = [headers]
        skipped = 0

        for c in contacts:
            if c.email.lower().strip() in campaign_emails:
                skipped += 1
                continue

            domain = c.domain
            meta = domain_meta.get(domain, {})
            dc = dc_map.get(domain)
            attempts = dc_attempts.get(c.discovered_company_id, [])

            # Scores
            scores = meta.get("scores") or {}
            if isinstance(scores, str):
                try:
                    scores = json.loads(scores)
                except Exception:
                    scores = {}

            # Company info
            ci = meta.get("company_info") or {}
            if isinstance(ci, str):
                try:
                    ci = json.loads(ci)
                except Exception:
                    ci = {}

            services = ci.get("services", "")
            if isinstance(services, list):
                services = ", ".join(services)

            # Segment: prefer our matched_segment from search result, fallback to dc
            segments = meta.get("segments", set())
            segment = ", ".join(segments) if segments else (dc.dc_segment if dc else "")

            # Queries
            queries = meta.get("queries", [])
            engines = ", ".join(meta.get("engines", set()))

            # Enrichment methods used
            methods = set()
            for a in attempts:
                if a.status == "SUCCESS" and a.contacts_found and a.contacts_found > 0:
                    methods.add(a.source_type)
            # Also mark based on contact source
            methods.add(str(c.source or ""))
            enrichment_methods = ", ".join(sorted(methods))

            data.append([
                # SmartLead core
                c.email,
                c.first_name or "",
                c.last_name or "",
                c.company_name or "",
                c.url or "",
                # Contact details
                c.job_title or "",
                c.linkedin_url or "",
                c.phone or "",
                # Source & verification
                str(c.source or ""),
                "Yes" if c.apollo_verified else "",
                c.fm_result or "",
                c.email_provider or "",
                str(c.fm_verified_at)[:19] if c.fm_verified_at else "",
                # Classification
                segment,
                str(dc.confidence if dc else (meta.get("sr_confidence") or "")),
                str(scores.get("language_match", "")),
                str(scores.get("industry_match", "")),
                str(scores.get("service_match", "")),
                str(scores.get("company_type", "")),
                str(scores.get("geography_match", "")),
                # Company info
                ci.get("description", "") or "",
                services or "",
                ci.get("location", "") or "",
                ci.get("company_type", "") or "",
                ci.get("employee_count", "") or "",
                # Search discovery
                engines,
                queries[0] if queries else "",
                " | ".join(queries[:5]) if len(queries) > 1 else "",
                str(len(queries)),
                # Pipeline tracking
                meta.get("review_status") or "",
                meta.get("review_note") or "",
                str(dc.apollo_credits_used or 0) if dc else "0",
                enrichment_methods,
                meta.get("reasoning") or "",
            ])

        logger.info(f"SmartLead-ready rows: {len(data)-1} (skipped {skipped} in campaigns)")

        # 7. Write to Google Sheet
        google_sheets_service._initialize()
        sheets = google_sheets_service.sheets_service
        if sheets:
            try:
                sheets.spreadsheets().values().clear(
                    spreadsheetId=SHEET_ID, range="Sheet1",
                ).execute()
                sheets.spreadsheets().values().update(
                    spreadsheetId=SHEET_ID, range="Sheet1!A1",
                    valueInputOption="RAW", body={"values": data},
                ).execute()
                logger.info(f"SUCCESS: {len(data)-1} rows -> https://docs.google.com/spreadsheets/d/{SHEET_ID}")
            except Exception as e:
                logger.error(f"Sheet failed: {e}")
                url = google_sheets_service.create_and_populate(
                    title=f"OnSocial SmartLead+Analytics — {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
                    data=data, share_with=SHARE_WITH,
                )
                logger.info(f"New sheet: {url}")

        # 8. Project-level cost summary
        cost_result = await session.execute(text("""
            SELECT
                (SELECT SUM(COALESCE(dc.apollo_credits_used, 0)) FROM discovered_companies dc WHERE dc.project_id = :pid AND dc.is_target = true) as apollo_credits,
                (SELECT SUM(COALESCE(ev.credits_used, 0)) FROM email_verifications ev WHERE ev.project_id = :pid) as fm_credits,
                (SELECT SUM(COALESCE(ev.cost_usd, 0))::numeric(10,2) FROM email_verifications ev WHERE ev.project_id = :pid) as fm_cost,
                (SELECT COUNT(DISTINCT sj.id) FROM search_jobs sj WHERE sj.project_id = :pid) as jobs,
                (SELECT SUM(sj.queries_total) FROM search_jobs sj WHERE sj.project_id = :pid) as queries,
                (SELECT SUM(sj.domains_found) FROM search_jobs sj WHERE sj.project_id = :pid) as domains_found
        """), {"pid": PROJECT_ID})
        costs = cost_result.fetchone()

        print("\n" + "=" * 62)
        print("ONSOCIAL — SMARTLEAD-READY + ANALYTICS EXPORT")
        print("=" * 62)
        print(f"Verified valid contacts: {len(contacts)}")
        print(f"Excluded (in campaigns): {skipped}")
        print(f"Ready for SmartLead:     {len(data)-1}")
        print(f"\nProject costs:")
        print(f"  Search jobs: {costs.jobs}, queries: {costs.queries}, domains found: {costs.domains_found}")
        print(f"  Apollo credits: {costs.apollo_credits}")
        print(f"  FindyMail credits: {costs.fm_credits} (${costs.fm_cost})")
        print(f"\nhttps://docs.google.com/spreadsheets/d/{SHEET_ID}")
        print("=" * 62)


if __name__ == "__main__":
    asyncio.run(main())
