"""Map GetSales sender profiles to projects via contacts table."""
import asyncio
import json
from app.db import async_session_maker
from sqlalchemy import text


async def main():
    async with async_session_maker() as s:
        # For each unknown sender_profile_uuid, find contacts' project_id
        r = await s.execute(text("""
            SELECT DISTINCT raw_webhook_data->>'sender_profile_uuid' AS sender_uuid
            FROM processed_replies
            WHERE source = 'getsales'
              AND (campaign_name IS NULL OR campaign_name = '')
              AND raw_webhook_data->>'sender_profile_uuid' IS NOT NULL
        """))
        unmapped_senders = [row[0] for row in r.fetchall()]
        print(f"Unmapped senders: {len(unmapped_senders)}")
        print("=" * 100)

        for su in unmapped_senders:
            # Find contacts that have activities from this sender
            r2 = await s.execute(text("""
                SELECT DISTINCT c.project_id, p.name AS project_name, c.email
                FROM contact_activities ca
                JOIN contacts c ON c.id = ca.contact_id
                LEFT JOIN projects p ON p.id = c.project_id
                WHERE ca.extra_data->>'sender_profile_uuid' = :su
                LIMIT 5
            """), {"su": su})
            rows = r2.fetchall()
            if rows:
                projects = set()
                for row in rows:
                    projects.add((row[0], row[1]))
                for pid, pname in projects:
                    print(f"  sender={su}  -> project_id={pid}  project={pname}")
            else:
                # Try finding via lead email from processed_replies
                r3 = await s.execute(text("""
                    SELECT pr.lead_email, c.project_id, p.name
                    FROM processed_replies pr
                    LEFT JOIN contacts c ON lower(c.email) = lower(pr.lead_email)
                    LEFT JOIN projects p ON p.id = c.project_id
                    WHERE pr.source = 'getsales'
                      AND pr.raw_webhook_data->>'sender_profile_uuid' = :su
                    LIMIT 3
                """), {"su": su})
                rows3 = r3.fetchall()
                for row in rows3:
                    pid = row[1] if row[1] else "NULL"
                    pname = row[2] if row[2] else "unknown"
                    print(f"  sender={su}  -> project={pid}/{pname}  (via contact email: {row[0]})")
                if not rows3:
                    print(f"  sender={su}  -> NO DATA FOUND")


asyncio.run(main())
