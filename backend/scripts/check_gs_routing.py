"""Check GetSales reply routing - why campaign_name is empty."""
import asyncio
import json
from app.db import async_session_maker
from sqlalchemy import text


async def main():
    async with async_session_maker() as s:
        r = await s.execute(text("""
            SELECT id, campaign_name, campaign_id, raw_webhook_data::text
            FROM processed_replies
            WHERE source = 'getsales' AND telegram_sent_at IS NOT NULL
            ORDER BY telegram_sent_at DESC LIMIT 5
        """))
        for row in r.fetchall():
            camp_name = row[1] or "(empty)"
            camp_id = row[2] or "(empty)"
            raw = json.loads(row[3]) if row[3] else {}
            automation = raw.get("automation", {})
            sender_uuid = raw.get("sender_profile_uuid", "?")
            lead_uuid = raw.get("lead_uuid", "?")
            
            if isinstance(automation, dict):
                auto_name = automation.get("name", "?")
                auto_uuid = automation.get("uuid", "?")
            else:
                auto_name = str(automation)
                auto_uuid = "?"
            
            print(f"id={row[0]}  camp_name='{camp_name}'  camp_id='{camp_id}'")
            print(f"  automation_name='{auto_name}'  automation_uuid='{auto_uuid}'")
            print(f"  sender_profile_uuid='{sender_uuid}'")
            print()


asyncio.run(main())
