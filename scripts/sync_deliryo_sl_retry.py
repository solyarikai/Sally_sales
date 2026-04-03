"""Retry syncing Deliryo campaigns that failed before, with rate limiting."""
import asyncio
import os
import httpx
from app.db.database import async_session_maker
from sqlalchemy import text


async def main():
    api_key = os.environ.get("SMARTLEAD_API_KEY")

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.get(f"https://server.smartlead.ai/api/v1/campaigns?api_key={api_key}")
        campaigns = r.json()
        deliryo = [c for c in campaigns if "deliryo" in (c.get("name", "") or "").lower()]

        all_leads = {}
        for camp in deliryo:
            cid = camp["id"]
            cname = camp["name"]
            offset = 0
            camp_count = 0
            while True:
                try:
                    await asyncio.sleep(0.5)  # Rate limit
                    r2 = await client.get(
                        f"https://server.smartlead.ai/api/v1/campaigns/{cid}/leads",
                        params={"api_key": api_key, "offset": offset, "limit": 100},
                    )
                    if r2.status_code != 200:
                        print(f"  {cid} ({cname}): HTTP {r2.status_code}, retrying...")
                        await asyncio.sleep(2)
                        r2 = await client.get(
                            f"https://server.smartlead.ai/api/v1/campaigns/{cid}/leads",
                            params={"api_key": api_key, "offset": offset, "limit": 100},
                        )
                    data = r2.json()
                    if isinstance(data, dict) and "data" in data:
                        leads = data["data"]
                        if not leads:
                            break
                        for lead_entry in leads:
                            lead = lead_entry.get("lead", {})
                            email = (lead.get("email") or "").lower().strip()
                            if email and "@" in email:
                                if email not in all_leads:
                                    all_leads[email] = {
                                        "email": email,
                                        "first_name": lead.get("first_name", ""),
                                        "last_name": lead.get("last_name", ""),
                                        "company_name": lead.get("company_name", ""),
                                        "domain": email.split("@")[1],
                                    }
                                camp_count += 1
                        offset += 100
                        total = int(data.get("total_leads", 0))
                        if offset >= total:
                            break
                    else:
                        print(f"  {cid} ({cname}): unexpected response, skipping")
                        break
                except Exception as e:
                    print(f"  {cid} ({cname}): {e}")
                    await asyncio.sleep(2)
                    break
            if camp_count:
                print(f"  {cid}: {cname} -> {camp_count}")

        print(f"\nTotal unique emails: {len(all_leads)}")

        # Sync missing to contacts
        async with async_session_maker() as s:
            r3 = await s.execute(text("SELECT DISTINCT lower(email) FROM contacts WHERE email IS NOT NULL"))
            db_emails = set(row[0] for row in r3.fetchall())
            missing = set(all_leads.keys()) - db_emails
            print(f"Missing from contacts: {len(missing)}")

            if missing:
                inserted = 0
                for email in missing:
                    lead = all_leads[email]
                    try:
                        await s.execute(
                            text(
                                "INSERT INTO contacts (company_id, email, first_name, last_name, "
                                "company_name, domain, source, status, is_active, created_at, updated_at) "
                                "VALUES (1, :email, :first_name, :last_name, :company_name, :domain, "
                                "'smartlead_deliryo_sync', 'synced', true, NOW(), NOW()) "
                                "ON CONFLICT DO NOTHING"
                            ),
                            {
                                "email": lead["email"],
                                "first_name": lead["first_name"],
                                "last_name": lead["last_name"],
                                "company_name": lead["company_name"],
                                "domain": lead["domain"],
                            },
                        )
                        inserted += 1
                    except Exception as e:
                        print(f"  Insert error {email}: {e}")
                await s.commit()
                print(f"Inserted {inserted}")

            # Final verify
            r4 = await s.execute(text("SELECT DISTINCT lower(email) FROM contacts WHERE email IS NOT NULL"))
            db_after = set(row[0] for row in r4.fetchall())
            still_missing = set(all_leads.keys()) - db_after
            print(f"Still missing: {len(still_missing)}")


asyncio.run(main())
