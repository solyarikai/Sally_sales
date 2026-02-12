#!/usr/bin/env python3
"""
Mark pre-enriched companies — backfill apollo_enriched_at and apollo_credits_used.

Two steps:
1. Auto-heal: any DiscoveredCompany with Apollo extracted_contacts but missing apollo_enriched_at
2. Cross-check: verify all 41 Apollo domains from user's Google Sheet are marked

Usage (on Hetzner):
  docker run --rm --network repo_default \
    -v ~/magnum-opus-project/repo/backend:/app \
    -v ~/magnum-opus-project/repo/scripts:/scripts \
    -v ~/magnum-opus-project/repo/google-credentials.json:/app/google-credentials.json:ro \
    -e DATABASE_URL=postgresql+asyncpg://leadgen:leadgen_secret@postgres:5432/leadgen \
    -e GOOGLE_APPLICATION_CREDENTIALS=/app/google-credentials.json \
    python:3.11 bash -c 'pip install -q -r /app/requirements.txt && python /scripts/mark_preenriched.py'
"""
import asyncio
import logging
import os
import sys

sys.path.insert(0, "/app")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("mark_preenriched")

# Google Sheet with pre-enriched Deliryo data
SHEET_ID = "1g9RLQpNwYqHqmkjSIaPaapUttVO3cUlWkzhPdK1FCf0"
SHEET_TAB = "Sheet2"  # Tab with 130 Apollo + 16 website_scrape contacts


async def main():
    from sqlalchemy import text
    from app.db import async_session_maker, engine

    try:
        async with async_session_maker() as session:
            # ============================================================
            # STEP 1: Auto-heal — mark any DC with Apollo contacts but no timestamp
            # ============================================================
            logger.info("=" * 60)
            logger.info("STEP 1: Auto-heal companies with Apollo contacts but missing apollo_enriched_at")
            logger.info("=" * 60)

            # First check how many need fixing
            check = await session.execute(text("""
                SELECT COUNT(DISTINCT dc.id), COUNT(ec.id)
                FROM discovered_companies dc
                JOIN extracted_contacts ec ON ec.discovered_company_id = dc.id
                WHERE ec.source = 'APOLLO'
                  AND dc.apollo_enriched_at IS NULL
            """))
            row = check.fetchone()
            logger.info(f"Companies needing fix: {row[0]} (with {row[1]} Apollo contacts)")

            if row[0] > 0:
                # Backfill apollo_enriched_at and apollo_credits_used
                result = await session.execute(text("""
                    UPDATE discovered_companies dc
                    SET apollo_enriched_at = ec_agg.earliest,
                        apollo_credits_used = ec_agg.cnt,
                        apollo_people_count = CASE
                            WHEN dc.apollo_people_count < ec_agg.cnt THEN ec_agg.cnt
                            ELSE dc.apollo_people_count
                        END
                    FROM (
                        SELECT discovered_company_id,
                               MIN(created_at) as earliest,
                               COUNT(*) as cnt
                        FROM extracted_contacts
                        WHERE source = 'APOLLO'
                        GROUP BY discovered_company_id
                    ) ec_agg
                    WHERE dc.id = ec_agg.discovered_company_id
                      AND dc.apollo_enriched_at IS NULL
                """))
                await session.commit()
                logger.info(f"Fixed {result.rowcount} companies")
            else:
                logger.info("No companies need fixing — all Apollo contacts already have timestamps")

            # Verify
            verify = await session.execute(text("""
                SELECT COUNT(DISTINCT dc.id)
                FROM discovered_companies dc
                JOIN extracted_contacts ec ON ec.discovered_company_id = dc.id
                WHERE ec.source = 'APOLLO'
                  AND dc.apollo_enriched_at IS NULL
            """))
            remaining = verify.scalar()
            logger.info(f"Remaining unfixed: {remaining}")

            # ============================================================
            # STEP 2: Cross-check against Google Sheet
            # ============================================================
            logger.info("")
            logger.info("=" * 60)
            logger.info("STEP 2: Cross-check against Google Sheet")
            logger.info("=" * 60)

            try:
                from app.services.google_sheets_service import google_sheets_service

                if not google_sheets_service.is_configured():
                    logger.warning("Google Sheets not configured — skipping cross-check")
                else:
                    data = google_sheets_service.read_sheet_data(SHEET_ID, SHEET_TAB)
                    logger.info(f"Read {len(data)} rows from Sheet2")

                    # Extract Apollo domains from sheet
                    sheet_apollo_domains = set()
                    for row in data:
                        source = row.get("source", "")
                        domain = row.get("domain", "")
                        if source == "APOLLO" and domain:
                            sheet_apollo_domains.add(domain.lower())

                    logger.info(f"Apollo domains in sheet: {len(sheet_apollo_domains)}")

                    if sheet_apollo_domains:
                        # Check which are marked in DB
                        domain_list = list(sheet_apollo_domains)
                        check = await session.execute(text("""
                            SELECT domain, apollo_enriched_at, apollo_credits_used, apollo_people_count
                            FROM discovered_companies
                            WHERE lower(domain) = ANY(:domains)
                              AND is_target = true
                            ORDER BY domain
                        """), {"domains": domain_list})
                        db_rows = check.fetchall()

                        db_domains = {}
                        for r in db_rows:
                            db_domains[r[0].lower()] = {
                                "apollo_enriched_at": r[1],
                                "apollo_credits_used": r[2],
                                "apollo_people_count": r[3],
                            }

                        marked = 0
                        unmarked = 0
                        not_in_db = 0
                        for d in sorted(sheet_apollo_domains):
                            if d in db_domains:
                                info = db_domains[d]
                                if info["apollo_enriched_at"]:
                                    marked += 1
                                else:
                                    unmarked += 1
                                    logger.warning(f"  UNMARKED: {d} (in DB but apollo_enriched_at=NULL)")
                            else:
                                not_in_db += 1
                                logger.warning(f"  NOT IN DB: {d} (in sheet but not in discovered_companies)")

                        logger.info(f"Results: {marked} marked, {unmarked} unmarked, {not_in_db} not in DB")

                        if unmarked > 0:
                            logger.warning(f"⚠ {unmarked} domains still unmarked — they will be re-enriched!")
                        if not_in_db > 0:
                            logger.info(f"Note: {not_in_db} domains from sheet are not in discovered_companies (different project or already in CRM)")

            except Exception as e:
                logger.error(f"Google Sheet cross-check failed: {e}")

            # ============================================================
            # SUMMARY
            # ============================================================
            logger.info("")
            logger.info("=" * 60)
            logger.info("SUMMARY")
            logger.info("=" * 60)

            summary = await session.execute(text("""
                SELECT
                    COUNT(*) as total_targets,
                    COUNT(*) FILTER (WHERE apollo_enriched_at IS NOT NULL) as apollo_enriched,
                    SUM(COALESCE(apollo_credits_used, 0)) FILTER (WHERE apollo_enriched_at IS NOT NULL) as total_credits,
                    SUM(COALESCE(apollo_people_count, 0)) FILTER (WHERE apollo_enriched_at IS NOT NULL) as total_people
                FROM discovered_companies
                WHERE project_id = 18 AND is_target = true
            """))
            s = summary.fetchone()
            logger.info(f"Deliryo targets: {s[0]} total, {s[1]} Apollo-enriched")
            logger.info(f"Apollo credits tracked: {s[2]}, people found: {s[3]}")
            logger.info("=" * 60)

    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
