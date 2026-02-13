"""Check data consistency between Pipeline Dashboard and Pipeline Page."""
import asyncio
from app.db.database import async_session_maker
from sqlalchemy import text


async def main():
    async with async_session_maker() as s:
        print("=== DATA CONSISTENCY CHECK ===\n")

        # 1. Apollo credits
        r1 = await s.execute(text(
            "SELECT SUM(apollo_credits_used) FROM discovered_companies WHERE project_id = 18"
        ))
        dc_credits = r1.scalar() or 0
        print(f"discovered_companies.apollo_credits_used SUM = {dc_credits}")

        # 2. Apollo people count
        r2 = await s.execute(text(
            "SELECT SUM(apollo_people_count) FROM discovered_companies WHERE project_id = 18"
        ))
        dc_people = r2.scalar() or 0
        print(f"discovered_companies.apollo_people_count SUM = {dc_people}")

        # 3. Source enum values
        r3 = await s.execute(text("SELECT unnest(enum_range(NULL::contactsource))"))
        sources = [row[0] for row in r3.fetchall()]
        print(f"\ncontactsource enum values: {sources}")

        # 4. Contacts by source
        r4 = await s.execute(text("""
            SELECT ec.source, COUNT(*),
                   COUNT(*) FILTER (WHERE ec.email IS NOT NULL AND ec.email <> '')
            FROM extracted_contacts ec
            JOIN discovered_companies dc ON ec.discovered_company_id = dc.id
            WHERE dc.project_id = 18
            GROUP BY ec.source
        """))
        print("\nExtracted contacts by source:")
        for row in r4.fetchall():
            print(f"  {row[0]}: {row[1]} total, {row[2]} with email")

        # 5. Target contacts with email
        r5 = await s.execute(text("""
            SELECT COUNT(*) FROM extracted_contacts ec
            JOIN discovered_companies dc ON ec.discovered_company_id = dc.id
            WHERE dc.project_id = 18 AND dc.is_target = true
            AND ec.email IS NOT NULL AND ec.email <> ''
        """))
        target_emails = r5.scalar() or 0
        print(f"\nTarget contacts with email = {target_emails}")

        # 6. ALL target contacts
        r6 = await s.execute(text("""
            SELECT COUNT(*) FROM extracted_contacts ec
            JOIN discovered_companies dc ON ec.discovered_company_id = dc.id
            WHERE dc.project_id = 18 AND dc.is_target = true
        """))
        all_target = r6.scalar() or 0
        print(f"All target contacts = {all_target}")

        # 7. Search engine query counts
        r7 = await s.execute(text("""
            SELECT
                COUNT(DISTINCT sq.id) FILTER (WHERE sj.search_engine = 'YANDEX_API') as yandex_queries,
                COUNT(DISTINCT sq.id) FILTER (WHERE sj.search_engine = 'GOOGLE_SERP') as google_queries,
                COUNT(DISTINCT sj.id) FILTER (WHERE sj.search_engine = 'YANDEX_API') as yandex_jobs,
                COUNT(DISTINCT sj.id) FILTER (WHERE sj.search_engine = 'GOOGLE_SERP') as google_jobs
            FROM search_queries sq
            JOIN search_jobs sj ON sq.search_job_id = sj.id
            WHERE sj.project_id = 18
        """))
        row7 = r7.fetchone()
        print(f"\nYandex queries: {row7[0]}, jobs: {row7[2]}")
        print(f"Google queries: {row7[1]}, jobs: {row7[3]}")
        print(f"  Yandex cost @$0.006/q: ${row7[0] * 0.006:.2f}")

        # 8. Enriched
        r8 = await s.execute(text("""
            SELECT COUNT(*) FROM discovered_companies
            WHERE project_id = 18 AND apollo_enriched_at IS NOT NULL
        """))
        enriched = r8.scalar() or 0
        print(f"\nEnriched companies = {enriched}")

        # 9. Spending from project_spending or pipeline_events
        r9 = await s.execute(text("""
            SELECT pe.event_type, COUNT(*),
                   SUM((pe.metadata->>'credits_used')::int) FILTER (WHERE pe.metadata->>'credits_used' IS NOT NULL)
            FROM pipeline_events pe
            WHERE pe.project_id = 18
            GROUP BY pe.event_type
            ORDER BY pe.event_type
        """))
        print("\nPipeline events:")
        for row in r9.fetchall():
            print(f"  {row[0]}: {row[1]} events, credits_sum={row[2]}")

        # 10. Crona cost source
        r10 = await s.execute(text("""
            SELECT COUNT(*) FROM discovered_companies
            WHERE project_id = 18 AND website_scraped_at IS NOT NULL
        """))
        scraped = r10.scalar() or 0
        print(f"\nWebsite scraped companies = {scraped}")

        print("\n=== SUMMARY ===")
        print(f"Apollo credits used: {dc_credits}")
        print(f"Apollo people found: {dc_people}")
        print(f"  Bug: Pipeline page shows people count as 'credits'")
        print(f"  Actual cost: {dc_credits} x $0.01 = ${dc_credits * 0.01:.2f}")
        print(f"  Pipeline page says: {dc_people} x $0.01 = ${dc_people * 0.01:.2f} (wrong)")


asyncio.run(main())
