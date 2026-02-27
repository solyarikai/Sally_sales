"""Check Telegram notification configuration and routing across projects."""
import asyncio
from app.db import async_session_maker
from sqlalchemy import text


async def main():
    async with async_session_maker() as s:
        # 1. All projects with telegram configured
        r = await s.execute(text("""
            SELECT id, name, telegram_chat_id, telegram_username,
                   telegram_first_name, webhooks_enabled
            FROM projects
            WHERE telegram_chat_id IS NOT NULL AND deleted_at IS NULL
            ORDER BY id
        """))
        rows = r.fetchall()
        print("=" * 80)
        print("PROJECTS WITH TELEGRAM CONFIGURED")
        print("=" * 80)
        for row in rows:
            wh = "ON" if row[5] else "OFF"
            user = row[3] or "?"
            name = row[4] or "?"
            print(f"  id={row[0]:3d} [{wh:3s}]  {row[1]:30s}  chat_id={row[2]}  @{user}  ({name})")

        # 2. Group by chat_id to see which projects share same recipient
        r2 = await s.execute(text("""
            SELECT telegram_chat_id, telegram_first_name,
                   array_agg(name ORDER BY id) AS projects,
                   COUNT(*) AS project_count
            FROM projects
            WHERE telegram_chat_id IS NOT NULL AND deleted_at IS NULL
            GROUP BY telegram_chat_id, telegram_first_name
            ORDER BY project_count DESC
        """))
        rows2 = r2.fetchall()
        print()
        print("=" * 80)
        print("TELEGRAM RECIPIENTS (grouped by chat_id)")
        print("=" * 80)
        for row in rows2:
            projects_list = row[2] if isinstance(row[2], list) else [row[2]]
            print(f"  chat_id={row[0]}  name={row[1] or '?'}  ({len(projects_list)} projects):")
            for p in projects_list:
                print(f"    - {p}")

        # 3. Recent telegram notifications sent
        r3 = await s.execute(text("""
            SELECT campaign_name, lead_email, telegram_sent_at::text, source, channel
            FROM processed_replies
            WHERE telegram_sent_at IS NOT NULL
            ORDER BY telegram_sent_at DESC
            LIMIT 10
        """))
        rows3 = r3.fetchall()
        print()
        print("=" * 80)
        print("LAST 10 TELEGRAM NOTIFICATIONS SENT")
        print("=" * 80)
        for row in rows3:
            camp = (row[0] or "?")[:40]
            email = (row[1] or "?")[:30]
            print(f"  {camp:40s}  {email:30s}  {row[3]}/{row[4]}  at={row[2]}")

        # 4. Check projects with webhooks_enabled but no telegram
        r4 = await s.execute(text("""
            SELECT id, name, webhooks_enabled
            FROM projects
            WHERE (telegram_chat_id IS NULL OR telegram_chat_id = '')
              AND webhooks_enabled = true
              AND deleted_at IS NULL
        """))
        rows4 = r4.fetchall()
        if rows4:
            print()
            print("=" * 80)
            print("WARNING: PROJECTS WITH WEBHOOKS ON BUT NO TELEGRAM")
            print("=" * 80)
            for row in rows4:
                print(f"  id={row[0]:3d}  {row[1]}")


asyncio.run(main())
