"""Analyze Deliryo search performance and suggest improvements."""
import asyncio
from app.db.database import async_session_maker
from sqlalchemy import text


async def main():
    async with async_session_maker() as s:
        # Check schema
        cols = await s.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'search_queries' ORDER BY ordinal_position"))
        print("=== SEARCH_QUERIES COLUMNS ===")
        for c in cols.fetchall():
            print(f"  {c[0]}")

        # Top queries by search_results linked
        r2 = await s.execute(text("""
            SELECT sq.query_text, sq.status, sj.search_engine,
                   COUNT(sr.id) as total_results,
                   COUNT(sr.id) FILTER (WHERE sr.is_target = true) as targets
            FROM search_queries sq
            JOIN search_jobs sj ON sq.search_job_id = sj.id
            LEFT JOIN search_results sr ON sr.source_query_id = sq.id
            WHERE sj.project_id = 18
            GROUP BY sq.id, sq.query_text, sq.status, sj.search_engine
            HAVING COUNT(sr.id) > 0
            ORDER BY COUNT(sr.id) FILTER (WHERE sr.is_target = true) DESC NULLS LAST
            LIMIT 30
        """))
        print("\n=== TOP 30 QUERIES BY TARGETS FOUND ===")
        for q in r2.fetchall():
            engine = 'Y' if 'yandex' in q.search_engine else 'G'
            print(f"  [{engine}] targets={q.targets}/{q.total_results} | {q.query_text}")

        # Target company analysis — what industries/services appear most
        r3 = await s.execute(text("""
            SELECT dc.domain, dc.name,
                   dc.company_info->>'industry' as industry,
                   dc.company_info->>'services' as services,
                   dc.company_info->>'location' as location,
                   dc.confidence
            FROM discovered_companies dc
            WHERE dc.project_id = 18 AND dc.is_target = true
            AND dc.confidence >= 0.8
            ORDER BY dc.confidence DESC
            LIMIT 50
        """))
        print("\n=== TOP 50 TARGET COMPANIES (by confidence) ===")
        industries = {}
        locations = {}
        for q in r3.fetchall():
            ind = q.industry or 'Unknown'
            loc = q.location or 'Unknown'
            industries[ind] = industries.get(ind, 0) + 1
            locations[loc] = locations.get(loc, 0) + 1
            print(f"  {q.confidence:.0%} | {q.domain} | {q.name or '-'} | {ind} | {loc}")

        print("\n=== INDUSTRY DISTRIBUTION (top targets) ===")
        for k, v in sorted(industries.items(), key=lambda x: -x[1])[:15]:
            print(f"  {v:3d} | {k}")

        print("\n=== LOCATION DISTRIBUTION (top targets) ===")
        for k, v in sorted(locations.items(), key=lambda x: -x[1])[:15]:
            print(f"  {v:3d} | {k}")

        # Search knowledge
        r4 = await s.execute(text("SELECT industry_keywords, anti_keywords, good_query_patterns, bad_query_patterns FROM project_search_knowledge WHERE project_id = 18"))
        row4 = r4.fetchone()
        if row4:
            print("\n=== SEARCH KNOWLEDGE ===")
            print(f"Industry keywords ({len(row4[0] or [])}): {(row4[0] or [])[:25]}")
            print(f"Anti keywords ({len(row4[1] or [])}): {(row4[1] or [])[:25]}")
            print(f"Good patterns ({len(row4[2] or [])}): {(row4[2] or [])[:10]}")
            print(f"Bad patterns ({len(row4[3] or [])}): {(row4[3] or [])[:10]}")

        # Geo coverage gaps
        r5 = await s.execute(text("""
            SELECT dc.company_info->>'location' as loc, COUNT(*) as cnt
            FROM discovered_companies dc
            WHERE dc.project_id = 18 AND dc.is_target = true
            GROUP BY dc.company_info->>'location'
            ORDER BY cnt DESC
            LIMIT 20
        """))
        print("\n=== GEO COVERAGE (all targets) ===")
        for q in r5.fetchall():
            print(f"  {q.cnt:4d} | {q.loc or 'Unknown'}")

        # Engine performance
        r6 = await s.execute(text("""
            SELECT sj.search_engine,
                   COUNT(DISTINCT sj.id) as jobs,
                   COUNT(DISTINCT sr.domain) as domains,
                   COUNT(sr.id) FILTER (WHERE sr.is_target) as targets
            FROM search_jobs sj
            LEFT JOIN search_results sr ON sr.search_job_id = sj.id
            WHERE sj.project_id = 18
            GROUP BY sj.search_engine
        """))
        print("\n=== ENGINE PERFORMANCE ===")
        for q in r6.fetchall():
            print(f"  {q.search_engine}: {q.jobs} jobs, {q.domains} domains, {q.targets} targets")

        # Pipeline status check
        r7 = await s.execute(text("""
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE is_target) as targets,
                COUNT(*) FILTER (WHERE apollo_enriched_at IS NOT NULL) as enriched,
                SUM(apollo_credits_used) as credits
            FROM discovered_companies WHERE project_id = 18
        """))
        row7 = r7.fetchone()
        print(f"\n=== PIPELINE TOTALS ===")
        print(f"  Discovered: {row7.total}, Targets: {row7.targets}, Enriched: {row7.enriched}, Apollo credits: {row7.credits}")


asyncio.run(main())
