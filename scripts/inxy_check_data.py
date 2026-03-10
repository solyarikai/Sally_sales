"""Check Inxy project data quality."""
import asyncio
import sys, os
sys.path.insert(0, "/app")
os.chdir("/app")

async def main():
    from app.db import async_session_maker
    from sqlalchemy import text

    async with async_session_maker() as session:
        # 1. What queries were used?
        print("=" * 60)
        print("SEARCH QUERIES USED FOR INXY (project 48)")
        print("=" * 60)
        result = await session.execute(text("""
            SELECT sj.search_engine::text as engine,
                   sj.config->>'segment' as job_segment,
                   sq.query_text, sq.geo,
                   COUNT(DISTINCT sr.domain) as domains_found,
                   COUNT(DISTINCT CASE WHEN sr.is_target THEN sr.domain END) as targets_found
            FROM search_jobs sj
            JOIN search_queries sq ON sq.search_job_id = sj.id
            LEFT JOIN search_results sr ON sr.source_query_id = sq.id
            WHERE sj.project_id = 48
            GROUP BY sj.search_engine, sj.config->>'segment', sq.query_text, sq.geo
            ORDER BY targets_found DESC
            LIMIT 40
        """))
        for r in result.fetchall():
            print(f"  {r.engine:12s} [{r.geo or '?':5s}] {r.query_text:60s} domains={r.domains_found} targets={r.targets_found}")

        # 2. Segment breakdown with sample domains
        print()
        print("=" * 60)
        print("SEGMENT BREAKDOWN (is_target=true)")
        print("=" * 60)
        result = await session.execute(text("""
            SELECT COALESCE(sr.matched_segment, dc.matched_segment, 'NO SEGMENT') as segment,
                   COUNT(*) as cnt,
                   string_agg(dc.domain, ', ' ORDER BY dc.domain) as domains
            FROM discovered_companies dc
            LEFT JOIN search_results sr ON sr.id = dc.search_result_id
            WHERE dc.project_id = 48 AND dc.is_target = true
            GROUP BY segment
            ORDER BY cnt DESC
        """))
        for r in result.fetchall():
            domains_list = r.domains[:200] if r.domains else ''
            print(f"  {r.cnt:4d}  {r.segment:20s}  {domains_list}")

        # 3. not_target companies - reasoning
        print()
        print("=" * 60)
        print("'not_target' SEGMENT - WHY is_target=true?")
        print("=" * 60)
        result = await session.execute(text("""
            SELECT dc.domain, dc.confidence,
                   LEFT(COALESCE(sr.reasoning, dc.reasoning, ''), 150) as reasoning
            FROM discovered_companies dc
            LEFT JOIN search_results sr ON sr.id = dc.search_result_id
            WHERE dc.project_id = 48 AND dc.is_target = true
            AND COALESCE(sr.matched_segment, dc.matched_segment, '') = 'not_target'
            LIMIT 10
        """))
        for r in result.fetchall():
            print(f"  {r.domain:40s} conf={r.confidence}")
            print(f"    {r.reasoning}")

        # 4. How many total in project vs targets
        print()
        print("=" * 60)
        print("OVERALL STATS")
        print("=" * 60)
        result = await session.execute(text("""
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN is_target THEN 1 END) as targets,
                COUNT(CASE WHEN NOT is_target THEN 1 END) as non_targets
            FROM discovered_companies WHERE project_id = 48
        """))
        r = result.fetchone()
        print(f"  Total companies in project: {r.total}")
        print(f"  Marked as target: {r.targets}")
        print(f"  Not target: {r.non_targets}")

asyncio.run(main())
