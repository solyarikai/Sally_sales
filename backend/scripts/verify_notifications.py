"""Verify notification routing works for all of Victoria's projects."""
import asyncio
from app.db import async_session_maker
from sqlalchemy import text


VICTORIA_CHAT_ID = "5263019058"


async def main():
    async with async_session_maker() as s:
        # 1. Victoria's subscriptions
        r = await s.execute(text("""
            SELECT ts.project_id, p.name, p.webhooks_enabled
            FROM telegram_subscriptions ts
            JOIN projects p ON p.id = ts.project_id
            WHERE ts.chat_id = :chat_id
            ORDER BY p.name
        """), {"chat_id": VICTORIA_CHAT_ID})
        projects = r.fetchall()
        print("VICTORIA'S PROJECT SUBSCRIPTIONS")
        print("=" * 60)
        for row in projects:
            status = "ACTIVE" if row[2] else "DISABLED"
            print(f"  [{status:8s}] {row[1]:25s} (id={row[0]})")

        # 2. For each project, check notification coverage
        print()
        print("NOTIFICATION ROUTING COVERAGE")
        print("=" * 60)
        for row in projects:
            pid = row[0]
            pname = row[1]

            # SmartLead replies
            r2 = await s.execute(text("""
                SELECT COUNT(*) AS total,
                       COUNT(telegram_sent_at) AS notified
                FROM processed_replies
                WHERE source = 'smartlead' AND campaign_name IN (
                    SELECT cf FROM projects, jsonb_array_elements_text(campaign_filters) AS cf
                    WHERE projects.id = :pid
                )
            """), {"pid": pid})
            sl = r2.fetchone()

            # GetSales replies (using sender profile mapping)
            r3 = await s.execute(text("""
                SELECT COUNT(*) AS total,
                       COUNT(telegram_sent_at) AS notified,
                       COUNT(CASE WHEN campaign_name IS NULL OR campaign_name = '' THEN 1 END) AS no_campaign
                FROM processed_replies
                WHERE source = 'getsales'
            """))
            gs = r3.fetchone()

            print(f"\n  Project: {pname} (id={pid})")
            print(f"    SmartLead: {sl[0]} replies, {sl[1]} notified")
            print(f"    GetSales:  {gs[0]} total, {gs[1]} notified, {gs[2]} still missing campaign_name")

        # 3. Check for replies that SHOULD have gone to Victoria but didn't
        print()
        print("=" * 60)
        print("RECENT REPLIES FOR VICTORIA'S PROJECTS (last 20)")
        print("=" * 60)
        r4 = await s.execute(text("""
            SELECT pr.id, pr.campaign_name, pr.source, pr.channel,
                   pr.telegram_sent_at IS NOT NULL AS was_notified,
                   pr.created_at::text
            FROM processed_replies pr
            WHERE pr.campaign_name IN (
                SELECT cf FROM projects p, jsonb_array_elements_text(p.campaign_filters) AS cf
                WHERE p.id IN (SELECT project_id FROM telegram_subscriptions WHERE chat_id = :chat_id)
            )
            ORDER BY pr.created_at DESC
            LIMIT 20
        """), {"chat_id": VICTORIA_CHAT_ID})
        for row in r4.fetchall():
            notif = "OK" if row[4] else "MISSED"
            print(f"  [{notif:6s}] id={row[0]:6d}  {row[2]}/{row[3]:8s}  {(row[1] or '?')[:40]:40s}  {row[5]}")


asyncio.run(main())
