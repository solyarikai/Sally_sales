"""Add missing campaign filter to easystaff ru project."""
import asyncio
from app.db import async_session_maker
from sqlalchemy import text


async def main():
    async with async_session_maker() as s:
        await s.execute(text(
            "UPDATE projects "
            "SET campaign_filters = campaign_filters || '\"EasyStaff - Sigma\"'::jsonb "
            "WHERE id = 40 "
            "AND NOT campaign_filters @> '\"EasyStaff - Sigma\"'::jsonb"
        ))
        await s.commit()

        r = await s.execute(text("SELECT campaign_filters FROM projects WHERE id = 40"))
        filters = r.scalar()
        print(f"EasyStaff RU now has {len(filters or [])} campaign filters")
        for f in (filters or []):
            print(f"  - {f}")


asyncio.run(main())
