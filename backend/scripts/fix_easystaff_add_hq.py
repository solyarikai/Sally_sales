"""Add back 'Easystaff - HQ in Russia' to easystaff ru campaign_filters."""
import asyncio
from app.db import async_session_maker
from sqlalchemy import text


async def main():
    async with async_session_maker() as s:
        await s.execute(text(
            "UPDATE projects "
            "SET campaign_filters = campaign_filters || '\"Easystaff - HQ in Russia\"'::jsonb "
            "WHERE id = 40 "
            "AND NOT campaign_filters @> '\"Easystaff - HQ in Russia\"'::jsonb"
        ))
        await s.commit()
        r = await s.execute(text("SELECT jsonb_array_length(campaign_filters) FROM projects WHERE id = 40"))
        print(f"Done. Total filters: {r.scalar()}")


asyncio.run(main())
