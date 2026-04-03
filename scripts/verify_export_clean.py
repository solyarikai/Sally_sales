"""Verify the exported Deliryo sheet has zero overlap with SmartLead Deliryo campaigns."""
import asyncio
import os
import httpx
from app.db.database import async_session_maker
from sqlalchemy import text


async def main():
    api_key = os.environ.get("SMARTLEAD_API_KEY")

    # Step 1: Fetch all Deliryo SmartLead emails
    print("Fetching ALL Deliryo SmartLead campaign emails...")
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.get(f"https://server.smartlead.ai/api/v1/campaigns?api_key={api_key}")
        campaigns = r.json()
        deliryo = [c for c in campaigns if "deliryo" in (c.get("name", "") or "").lower()]

        sl_emails = set()
        for camp in deliryo:
            cid = camp["id"]
            offset = 0
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
                            email = (lead_entry.get("lead", {}).get("email") or "").lower().strip()
                            if email and "@" in email:
                                sl_emails.add(email)
                        offset += 100
                        if offset >= int(data.get("total_leads", 0)):
                            break
                    else:
                        break
                except:
                    break

    sl_domains = set(e.split("@")[1] for e in sl_emails if "@" in e)
    print(f"SmartLead Deliryo: {len(sl_emails)} unique emails, {len(sl_domains)} unique domains")

    # Step 2: Get exported contacts (same filter as API)
    async with async_session_maker() as s:
        r3 = await s.execute(text(
            "SELECT ec.email, dc.domain FROM extracted_contacts ec "
            "JOIN discovered_companies dc ON ec.discovered_company_id = dc.id "
            "WHERE dc.project_id = 18 AND dc.is_target = true "
            "AND ec.email IS NOT NULL AND ec.email != '' "
            "AND lower(ec.email) NOT IN ("
            "  SELECT DISTINCT lower(c.email) FROM contacts c WHERE c.email IS NOT NULL"
            ") "
            "AND lower(dc.domain) NOT IN ("
            "  SELECT DISTINCT lower(c.domain) FROM contacts c "
            "  WHERE c.domain IS NOT NULL AND c.domain != ''"
            ")"
        ))
        exported = r3.fetchall()
        exported_emails = set(row[0].lower() for row in exported)
        exported_domains = set(row[1].lower() for row in exported)

    print(f"\nExported: {len(exported_emails)} emails, {len(exported_domains)} domains")

    # Step 3: Check overlaps
    email_overlap = exported_emails & sl_emails
    domain_overlap = exported_domains & sl_domains
    print(f"\nEMAIL OVERLAPS: {len(email_overlap)}")
    if email_overlap:
        for e in sorted(email_overlap)[:10]:
            print(f"  {e}")
    print(f"DOMAIN OVERLAPS: {len(domain_overlap)}")
    if domain_overlap:
        for d in sorted(domain_overlap)[:10]:
            print(f"  {d}")

    if not email_overlap and not domain_overlap:
        print("\n=== CLEAN: Zero overlaps with SmartLead Deliryo campaigns ===")
    else:
        print("\n!!! PROBLEM: Overlaps found !!!")


asyncio.run(main())
