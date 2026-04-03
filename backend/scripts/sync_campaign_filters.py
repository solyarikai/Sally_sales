"""Sync campaign_filters: add all known campaign names to their projects."""
import asyncio
import json
from app.db import async_session_maker
from sqlalchemy import text

PROJECT_PREFIXES = {
    "easystaff": 40,
    "mifort": 21,
    "mft": 21,
    "tfp": 13,
    "rem": 44,
}


async def main():
    async with async_session_maker() as s:
        # Get all distinct campaign names from processed_replies
        r = await s.execute(text("""
            SELECT DISTINCT campaign_name
            FROM processed_replies
            WHERE campaign_name IS NOT NULL AND campaign_name != ''
        """))
        all_campaigns = [row[0] for row in r.fetchall()]
        print(f"Total distinct campaign names: {len(all_campaigns)}")

        # Get existing filters for each project
        projects = {}
        for pid in set(PROJECT_PREFIXES.values()):
            r2 = await s.execute(text("SELECT campaign_filters FROM projects WHERE id = :pid"), {"pid": pid})
            existing = r2.scalar() or []
            projects[pid] = set(existing)
            print(f"Project {pid}: {len(existing)} existing filters")

        # Match campaigns to projects by prefix
        added = {}
        for camp in all_campaigns:
            camp_lower = camp.lower().strip()
            for prefix, pid in PROJECT_PREFIXES.items():
                if camp_lower.startswith(prefix):
                    if camp not in projects[pid]:
                        projects[pid].add(camp)
                        added.setdefault(pid, []).append(camp)
                    break

        # Update projects with new filters
        for pid, new_camps in added.items():
            print(f"\nAdding {len(new_camps)} campaigns to project {pid}:")
            for c in sorted(new_camps):
                print(f"  + {c}")
            filters_json = json.dumps(sorted(projects[pid]))
            await s.execute(text(
                "UPDATE projects SET campaign_filters = CAST(:filters AS jsonb) WHERE id = :pid"
            ), {"filters": filters_json, "pid": pid})

        await s.commit()
        print("\nDone!")


asyncio.run(main())
