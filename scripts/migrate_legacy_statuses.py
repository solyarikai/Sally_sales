"""
Migrate legacy statuses to 13-status funnel for a project.

Usage:
    python scripts/migrate_legacy_statuses.py [--project-id 40] [--dry-run]

Maps: touched→sent, replied→interested, warm→interested, scheduling→negotiating_meeting,
      out_of_office→ooo, wrong_person→not_interested, new→to_be_sent, lead→to_be_sent,
      contacted→sent
"""
import asyncio
import argparse
import sys
import os

# Add backend to path (works both locally and inside Docker where /app = backend)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, "/app")

from app.db.database import async_session_maker
from app.services.status_machine import LEGACY_STATUS_MAP, normalize_status
from sqlalchemy import text


async def migrate(project_id: int, dry_run: bool):
    async with async_session_maker() as session:
        # Get current status distribution
        result = await session.execute(text(
            "SELECT status, COUNT(*) FROM contacts WHERE project_id = :pid GROUP BY status ORDER BY COUNT(*) DESC"
        ), {"pid": project_id})
        rows = result.fetchall()

        print(f"\n=== Project {project_id} — Current Status Distribution ===")
        total = 0
        to_migrate = 0
        for status, count in rows:
            is_legacy = status in LEGACY_STATUS_MAP
            marker = " ← LEGACY" if is_legacy else ""
            mapped = f" → {LEGACY_STATUS_MAP[status]}" if is_legacy else ""
            print(f"  {status:25s} {count:>6d}{marker}{mapped}")
            total += count
            if is_legacy:
                to_migrate += count
        print(f"  {'TOTAL':25s} {total:>6d}")
        print(f"  To migrate: {to_migrate}")

        if to_migrate == 0:
            print("\nNothing to migrate!")
            return

        if dry_run:
            print("\n[DRY RUN] No changes made.")
            return

        # Perform migration
        migrated = 0
        for legacy_status, new_status in LEGACY_STATUS_MAP.items():
            result = await session.execute(text(
                "UPDATE contacts SET status = :new WHERE project_id = :pid AND status = :old"
            ), {"new": new_status, "pid": project_id, "old": legacy_status})
            if result.rowcount > 0:
                print(f"  Migrated {legacy_status} → {new_status}: {result.rowcount} rows")
                migrated += result.rowcount

        # Also handle NULL/empty and other unmapped statuses
        for unmapped in [None, "", "other", "synced"]:
            if unmapped is None:
                where = "status IS NULL"
            elif unmapped == "":
                where = "status = ''"
            else:
                where = f"status = '{unmapped}'"
            result = await session.execute(text(
                f"UPDATE contacts SET status = 'to_be_sent' WHERE project_id = :pid AND {where}"
            ), {"pid": project_id})
            if result.rowcount > 0:
                label = unmapped if unmapped else "NULL/empty"
                print(f"  Migrated {label} → to_be_sent: {result.rowcount} rows")
                migrated += result.rowcount

        await session.commit()
        print(f"\nMigrated {migrated} contacts total.")

        # Show new distribution
        result = await session.execute(text(
            "SELECT status, COUNT(*) FROM contacts WHERE project_id = :pid GROUP BY status ORDER BY COUNT(*) DESC"
        ), {"pid": project_id})
        rows = result.fetchall()
        print(f"\n=== Post-Migration Status Distribution ===")
        for status, count in rows:
            print(f"  {status:25s} {count:>6d}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-id", type=int, default=40)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    asyncio.run(migrate(args.project_id, args.dry_run))
