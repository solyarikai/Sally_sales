"""Get current Deliryo pipeline stats."""
import asyncio
from app.db.database import async_session_maker
from sqlalchemy import text


async def main():
    async with async_session_maker() as s:
        r1 = await s.execute(text("SELECT COUNT(*) FROM discovered_companies WHERE project_id = 18 AND is_target = true"))
        print(f"TOTAL_TARGETS: {r1.scalar()}")

        r2 = await s.execute(text(
            "SELECT COUNT(*) FROM extracted_contacts ec "
            "JOIN discovered_companies dc ON ec.discovered_company_id = dc.id "
            "WHERE dc.project_id = 18 AND dc.is_target = true "
            "AND ec.email IS NOT NULL AND ec.email != ''"
        ))
        print(f"CONTACTS_WITH_EMAIL: {r2.scalar()}")

        r3 = await s.execute(text("SELECT COUNT(*) FROM search_jobs WHERE project_id = 18"))
        print(f"TOTAL_SEARCH_JOBS: {r3.scalar()}")

        r4 = await s.execute(text(
            "SELECT id, search_engine, status, created_at FROM search_jobs "
            "WHERE project_id = 18 ORDER BY id DESC LIMIT 5"
        ))
        print("LATEST JOBS:")
        for row in r4.fetchall():
            print(f"  JOB {row[0]}: {row[1]} {row[2]} at {row[3]}")

        r5 = await s.execute(text("SELECT COUNT(*) FROM discovered_companies WHERE project_id = 18"))
        print(f"TOTAL_DISCOVERED: {r5.scalar()}")

        r6 = await s.execute(text(
            "SELECT COUNT(*) FROM discovered_companies WHERE project_id = 18 AND apollo_enriched_at IS NOT NULL"
        ))
        print(f"APOLLO_ENRICHED: {r6.scalar()}")

        r7 = await s.execute(text(
            "SELECT COUNT(*) FROM search_queries WHERE search_job_id IN "
            "(SELECT id FROM search_jobs WHERE project_id = 18)"
        ))
        print(f"TOTAL_QUERIES: {r7.scalar()}")

        # Targets not in SmartLead (email-only exclusion)
        r8 = await s.execute(text(
            "SELECT COUNT(*) FROM extracted_contacts ec "
            "JOIN discovered_companies dc ON ec.discovered_company_id = dc.id "
            "WHERE dc.project_id = 18 AND dc.is_target = true "
            "AND ec.email IS NOT NULL AND ec.email != '' "
            "AND lower(ec.email) NOT IN ("
            "  SELECT DISTINCT lower(c.email) FROM contacts c WHERE c.email IS NOT NULL"
            ")"
        ))
        print(f"NEW_EMAILS_NOT_IN_SMARTLEAD: {r8.scalar()}")


asyncio.run(main())
