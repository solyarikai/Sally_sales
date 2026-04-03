"""Fetch ALL Deliryo SmartLead campaign emails and sync missing ones to contacts table."""
import asyncio
import os
import httpx
from app.db.database import async_session_maker
from sqlalchemy import text


async def main():
    api_key = os.environ.get("SMARTLEAD_API_KEY")
    if not api_key:
        print("NO SMARTLEAD_API_KEY")
        return

    async with httpx.AsyncClient(timeout=60) as client:
        # Get ALL campaigns with deliryo in name
        r = await client.get(f"https://server.smartlead.ai/api/v1/campaigns?api_key={api_key}")
        campaigns = r.json()
        deliryo = [c for c in campaigns if "deliryo" in (c.get("name", "") or "").lower()]
        print(f"Found {len(deliryo)} Deliryo campaigns")

        all_leads = {}  # email -> lead data
        for camp in deliryo:
            cid = camp["id"]
            cname = camp["name"]
            offset = 0
            camp_count = 0
            while True:
                try:
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
                                        "campaign": cname,
                                    }
                                camp_count += 1
                        offset += 100
                        total = int(data.get("total_leads", 0))
                        if offset >= total:
                            break
                    else:
                        break
                except Exception as e:
                    print(f"  Error on campaign {cid} ({cname}): {e}")
                    break
            if camp_count:
                print(f"  {cid}: {cname} -> {camp_count} leads")

        print(f"\nTotal unique emails from ALL Deliryo campaigns: {len(all_leads)}")

        # Save for reference
        with open("/tmp/all_deliryo_sl_emails.txt", "w") as f:
            for e in sorted(all_leads.keys()):
                f.write(e + "\n")

        # Check which are missing from contacts table
        async with async_session_maker() as s:
            r3 = await s.execute(text("SELECT DISTINCT lower(email) FROM contacts WHERE email IS NOT NULL"))
            db_emails = set(row[0] for row in r3.fetchall())

            missing_emails = set(all_leads.keys()) - db_emails
            print(f"Emails NOT in contacts table: {len(missing_emails)}")

            if missing_emails:
                # Insert missing contacts
                inserted = 0
                for email in missing_emails:
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
                        print(f"  Error inserting {email}: {e}")
                await s.commit()
                print(f"Inserted {inserted} missing contacts")

            # Verify
            r4 = await s.execute(text("SELECT DISTINCT lower(email) FROM contacts WHERE email IS NOT NULL"))
            db_emails_after = set(row[0] for row in r4.fetchall())
            still_missing = set(all_leads.keys()) - db_emails_after
            print(f"Still missing after sync: {len(still_missing)}")


asyncio.run(main())
