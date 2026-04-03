"""Check which sender profiles are receiving replies and if they're mapped."""
import asyncio
from app.db import async_session_maker
from sqlalchemy import text
from app.services.crm_sync_service import GETSALES_FLOW_NAMES, GETSALES_SENDER_PROFILES


async def main():
    async with async_session_maker() as s:
        r = await s.execute(text("""
            SELECT
                raw_webhook_data->>'sender_profile_uuid' AS sender_uuid,
                COUNT(*) AS reply_count,
                MAX(created_at)::text AS latest
            FROM processed_replies
            WHERE source = 'getsales'
              AND raw_webhook_data->>'sender_profile_uuid' IS NOT NULL
            GROUP BY raw_webhook_data->>'sender_profile_uuid'
            ORDER BY COUNT(*) DESC
        """))
        rows = r.fetchall()
        print("GETSALES SENDER PROFILES IN REPLIES")
        print("=" * 100)
        for row in rows:
            uuid = row[0]
            person_name = GETSALES_SENDER_PROFILES.get(uuid, "NOT MAPPED")
            print(f"  {uuid}  count={row[1]:4d}  latest={row[2]}  -> {person_name}")

        print()
        print("KNOWN AUTOMATION MAPPINGS (GETSALES_FLOW_NAMES):")
        print("=" * 100)
        for uuid, name in sorted(GETSALES_FLOW_NAMES.items(), key=lambda x: x[1]):
            print(f"  {uuid}  -> {name}")

        print()
        print("KNOWN SENDER PROFILES (GETSALES_SENDER_PROFILES):")
        print("=" * 100)
        for uuid, name in sorted(GETSALES_SENDER_PROFILES.items(), key=lambda x: x[1]):
            print(f"  {uuid}  -> {name}")


asyncio.run(main())
