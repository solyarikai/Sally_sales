#!/usr/bin/env python3
"""Fix Phase 1 pipeline issues: dedup, placeholders, output refs."""
import sys
import asyncio

sys.path.insert(0, '/app')


async def main():
    from app.db import async_session_maker, init_db
    from sqlalchemy import text

    await init_db()
    async with async_session_maker() as s:
        # 1.3: Dedup analysis results — keep latest per company
        r = await s.execute(text("""
            DELETE FROM analysis_results WHERE id IN (
                SELECT id FROM (
                    SELECT id, ROW_NUMBER() OVER (
                        PARTITION BY discovered_company_id ORDER BY analysis_run_id DESC
                    ) as rn FROM analysis_results
                ) sub WHERE rn > 1
            )
        """))
        print(f"Deduped analysis_results: {r.rowcount} duplicates removed")

        # 1.5: Mark placeholder domains as PENDING_RESOLVE
        r2 = await s.execute(text("""
            UPDATE discovered_companies SET status = 'NEW'
            WHERE domain LIKE '%!_apollo!_%' ESCAPE '!' AND project_id = 9
        """))
        print(f"Placeholder domains: {r2.rowcount} kept as NEW (need domain resolution)")

        # 1.6: Set raw_output_ref
        refs = {
            1: "easystaff-global/data/uae_god_search_companies.json",
            2: "easystaff-global/data/uae_20k_companies.json",
            3: "easystaff-global/data/uae_expanded_companies_expanded.json",
            4: "easystaff-global/data/uae_god_search_companies.json",
            5: "easystaff-global/data/uae_expanded_companies_expanded.json",
            54: "easystaff-global/data/uae_wave2_companies.json",
            55: "easystaff-global/data/uae_wave2_companies.json",
        }
        for run_id, ref in refs.items():
            await s.execute(
                text("UPDATE gathering_runs SET raw_output_ref = :ref WHERE id = :id"),
                {"ref": ref, "id": run_id},
            )
        print(f"raw_output_ref set for {len(refs)} runs")

        await s.commit()
        print("All Phase 1 fixes applied")


if __name__ == "__main__":
    asyncio.run(main())
