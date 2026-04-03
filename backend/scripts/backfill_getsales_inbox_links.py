"""Backfill GetSales inbox_link from old unibox format to correct messenger format.

Old: https://amazing.getsales.io/unibox?lead={lead_uuid}
New: https://amazing.getsales.io/messenger/{lead_uuid}?senderProfileId="{sender_profile_uuid}"
"""
import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import text
from app.db.database import async_session_maker


async def main():
    async with async_session_maker() as s:
        result = await s.execute(text("""
            SELECT id, inbox_link, raw_webhook_data
            FROM processed_replies
            WHERE source = 'getsales'
              AND inbox_link LIKE '%unibox%'
        """))
        rows = result.fetchall()
        print(f"Found {len(rows)} replies with old unibox links")

        fixed = 0
        for row in rows:
            reply_id, old_link, raw_data = row
            if not old_link or "unibox" not in old_link:
                continue

            lead_uuid = old_link.split("lead=")[-1] if "lead=" in old_link else None
            if not lead_uuid:
                print(f"  id={reply_id}: cannot parse lead_uuid from {old_link}")
                continue

            sender_profile_uuid = ""
            if raw_data:
                if isinstance(raw_data, str):
                    raw_data = json.loads(raw_data)
                sender_profile_uuid = (
                    raw_data.get("sender_profile_uuid")
                    or (raw_data.get("automation", {}) or {}).get("sender_profile_uuid")
                    or ""
                )

            from urllib.parse import quote
            new_link = f"https://amazing.getsales.io/messenger/{lead_uuid}"
            if sender_profile_uuid:
                new_link += f'?senderProfileId={quote(chr(34) + sender_profile_uuid + chr(34))}'

            await s.execute(text("""
                UPDATE processed_replies SET inbox_link = :new_link WHERE id = :id
            """), {"new_link": new_link, "id": reply_id})
            fixed += 1
            print(f"  id={reply_id}: {old_link} -> {new_link}")

        await s.commit()
        print(f"\nFixed {fixed}/{len(rows)} inbox links")


if __name__ == "__main__":
    asyncio.run(main())
