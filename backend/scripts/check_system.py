"""System health check: webhook events, DB tables, project monitoring status."""
import asyncio
from app.db import async_session_maker
from sqlalchemy import text


async def main():
    async with async_session_maker() as s:
        # 1. All monitored projects
        r = await s.execute(text("""
            SELECT id, name, webhooks_enabled, telegram_chat_id,
                   campaign_filters
            FROM projects
            WHERE deleted_at IS NULL
            ORDER BY id
        """))
        projects = r.fetchall()
        print("=" * 80)
        print("MONITORED PROJECTS")
        print("=" * 80)
        for p in projects:
            mon = "ON" if p[2] else "OFF"
            camps = p[4] if p[4] else "[]"
            tg = p[3] or "none"
            print(f"  [{mon:3s}] id={p[0]:3d}  {p[1]:30s}  tg={tg}  camps={camps}")

        # 2. GetSales / LinkedIn webhook events last 48h
        r = await s.execute(text("""
            SELECT event_type, processed, COUNT(*), MAX(created_at)::text
            FROM webhook_events
            WHERE (event_type LIKE 'linkedin%' OR event_type LIKE 'getsales%')
              AND created_at > NOW() - INTERVAL '48 hours'
            GROUP BY event_type, processed
            ORDER BY MAX(created_at) DESC
        """))
        rows = r.fetchall()
        print()
        print("=" * 80)
        print("GETSALES / LINKEDIN WEBHOOK EVENTS (48h)")
        print("=" * 80)
        for row in rows:
            print(f"  type={row[0]:30s}  processed={str(row[1]):5s}  count={row[2]:4d}  latest={row[3]}")
        if not rows:
            print("  (none)")

        # 3. SmartLead webhook events last 48h
        r = await s.execute(text("""
            SELECT event_type, processed, COUNT(*), MAX(created_at)::text
            FROM webhook_events
            WHERE event_type NOT LIKE 'linkedin%' AND event_type NOT LIKE 'getsales%'
              AND created_at > NOW() - INTERVAL '48 hours'
            GROUP BY event_type, processed
            ORDER BY MAX(created_at) DESC
        """))
        rows = r.fetchall()
        print()
        print("=" * 80)
        print("SMARTLEAD WEBHOOK EVENTS (48h)")
        print("=" * 80)
        for row in rows:
            print(f"  type={row[0]:30s}  processed={str(row[1]):5s}  count={row[2]:4d}  latest={row[3]}")
        if not rows:
            print("  (none)")

        # 4. Last 15 events of any type
        r = await s.execute(text("""
            SELECT id, event_type, lead_email, campaign_id, processed,
                   COALESCE(error, '')::text AS err, created_at::text
            FROM webhook_events
            ORDER BY created_at DESC LIMIT 15
        """))
        rows = r.fetchall()
        print()
        print("=" * 80)
        print("LATEST 15 WEBHOOK EVENTS (all types)")
        print("=" * 80)
        for row in rows:
            email = (row[2] or "N/A")[:35]
            camp = (str(row[3]) or "")[:25]
            err = f" ERR={row[5][:50]}" if row[5] else ""
            print(f"  id={row[0]:6d} {row[1]:20s} {email:35s} proc={str(row[4]):5s}{err}  {row[6]}")

        # 5. Processed replies by category (last 48h)
        r = await s.execute(text("""
            SELECT category, source, channel, COUNT(*), MAX(created_at)::text
            FROM processed_replies
            WHERE created_at > NOW() - INTERVAL '48 hours'
            GROUP BY category, source, channel
            ORDER BY COUNT(*) DESC
        """))
        rows = r.fetchall()
        print()
        print("=" * 80)
        print("PROCESSED REPLIES BY CATEGORY (48h)")
        print("=" * 80)
        for row in rows:
            cat = (row[0] or "unknown")[:20]
            src = (row[1] or "?")[:12]
            ch = (row[2] or "?")[:8]
            print(f"  {cat:20s}  src={src:12s} ch={ch:8s}  count={row[3]:4d}  latest={row[4]}")
        if not rows:
            print("  (none)")

        # 6. DB table sizes
        r = await s.execute(text("""
            SELECT
                c.relname AS table_name,
                pg_total_relation_size(c.oid)::bigint AS total_bytes,
                pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size,
                c.reltuples::bigint AS est_rows
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relkind = 'r'
            ORDER BY pg_total_relation_size(c.oid) DESC
        """))
        rows = r.fetchall()
        print()
        print("=" * 80)
        print("DATABASE TABLES")
        print("=" * 80)
        total_bytes = 0
        print(f"  {'TABLE':<40s} {'SIZE':>10s} {'EST ROWS':>12s}")
        print(f"  {'-'*62}")
        for row in rows:
            print(f"  {row[0]:<40s} {row[2]:>10s} {int(row[3]):>12,}")
            total_bytes += row[1]
        print(f"  {'-'*62}")
        mb = total_bytes / 1024 / 1024
        print(f"  {'TOTAL':<40s} {mb:>8.1f} MB")


asyncio.run(main())
