"""Check which Deliryo SmartLead campaigns have the highest overlap with discovered targets."""
import asyncio
import os
import httpx
from app.db.database import async_session_maker
from sqlalchemy import text


async def main():
    api_key = os.environ.get("SMARTLEAD_API_KEY")

    # Step 1: Get all target domains and emails from discovered companies
    async with async_session_maker() as s:
        r1 = await s.execute(text(
            "SELECT DISTINCT lower(dc.domain) FROM discovered_companies dc "
            "WHERE dc.project_id = 18 AND dc.is_target = true AND dc.domain IS NOT NULL"
        ))
        target_domains = set(row[0] for row in r1.fetchall())

        r2 = await s.execute(text(
            "SELECT DISTINCT lower(ec.email) FROM extracted_contacts ec "
            "JOIN discovered_companies dc ON ec.discovered_company_id = dc.id "
            "WHERE dc.project_id = 18 AND dc.is_target = true "
            "AND ec.email IS NOT NULL AND ec.email != ''"
        ))
        target_emails = set(row[0] for row in r2.fetchall())

    print(f"Pipeline targets: {len(target_domains)} domains, {len(target_emails)} emails")
    print()

    # Step 2: For each Deliryo campaign, fetch emails and check overlap
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.get(f"https://server.smartlead.ai/api/v1/campaigns?api_key={api_key}")
        campaigns = r.json()
        deliryo = [c for c in campaigns if "deliryo" in (c.get("name", "") or "").lower()]
        deliryo.sort(key=lambda x: x.get("id", 0), reverse=True)

        results = []
        for camp in deliryo:
            cid = camp["id"]
            cname = camp["name"]
            camp_emails = set()
            camp_domains = set()
            offset = 0
            while True:
                try:
                    await asyncio.sleep(0.3)
                    r2 = await client.get(
                        f"https://server.smartlead.ai/api/v1/campaigns/{cid}/leads",
                        params={"api_key": api_key, "offset": offset, "limit": 100},
                    )
                    if r2.status_code == 429:
                        await asyncio.sleep(3)
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
                                camp_emails.add(email)
                                camp_domains.add(email.split("@")[1])
                        offset += 100
                        if offset >= int(data.get("total_leads", 0)):
                            break
                    else:
                        break
                except Exception:
                    break

            if camp_emails:
                email_overlap = len(target_emails & camp_emails)
                domain_overlap = len(target_domains & camp_domains)
                if email_overlap > 0 or domain_overlap > 0:
                    results.append({
                        "id": cid,
                        "name": cname,
                        "total_leads": len(camp_emails),
                        "email_overlap": email_overlap,
                        "domain_overlap": domain_overlap,
                    })

        # Sort by domain overlap descending
        results.sort(key=lambda x: x["domain_overlap"], reverse=True)

        print(f"{'Campaign':<50s} {'Leads':>6s} {'Email ∩':>8s} {'Domain ∩':>9s}")
        print("-" * 75)
        for r in results[:30]:
            print(f"{r['name'][:50]:<50s} {r['total_leads']:>6d} {r['email_overlap']:>8d} {r['domain_overlap']:>9d}")

        print()
        total_email_overlap = sum(r["email_overlap"] for r in results)
        total_domain_overlap = sum(r["domain_overlap"] for r in results)
        print(f"Campaigns with overlap: {len(results)}")
        print(f"Sum email overlaps: {total_email_overlap} (some contacts in multiple campaigns)")
        print(f"Sum domain overlaps: {total_domain_overlap}")


asyncio.run(main())
