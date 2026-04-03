"""Backfill campaign_name for GetSales replies using automation UUID from raw_webhook_data.

IMPORTANT: Only uses automation UUIDs (from webhook/API automation field),
NEVER sender_profile UUIDs — a sender can work across multiple projects.
"""
import asyncio
from app.db import async_session_maker
from app.services.crm_sync_service import GETSALES_FLOW_NAMES
from sqlalchemy import text


async def main():
    async with async_session_maker() as s:
        # Find replies with missing campaign_name that have automation data
        r = await s.execute(text("""
            SELECT id,
                   raw_webhook_data->'automation'->>'uuid' AS auto_uuid,
                   raw_webhook_data->'automation'->>'name' AS auto_name
            FROM processed_replies
            WHERE source = 'getsales'
              AND (campaign_name IS NULL OR campaign_name = '')
        """))
        rows = r.fetchall()
        print(f"Found {len(rows)} replies with missing campaign_name")

        updated = 0
        for row in rows:
            reply_id, auto_uuid, auto_name = row[0], row[1], row[2]
            flow_name = None

            # Priority 1: automation name from raw data
            if auto_name and auto_name not in ("synced", ""):
                flow_name = auto_name
            # Priority 2: automation UUID → GETSALES_FLOW_NAMES
            elif auto_uuid and auto_uuid in GETSALES_FLOW_NAMES:
                flow_name = GETSALES_FLOW_NAMES[auto_uuid]

            if flow_name:
                await s.execute(text(
                    "UPDATE processed_replies SET campaign_name = :name, campaign_id = :uuid WHERE id = :id"
                ), {"name": flow_name, "uuid": auto_uuid or "", "id": reply_id})
                updated += 1

        await s.commit()
        print(f"Updated {updated}/{len(rows)} replies with campaign_name from automation data")


asyncio.run(main())
