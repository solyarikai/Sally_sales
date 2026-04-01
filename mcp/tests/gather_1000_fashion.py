"""Gather 1000 fashion companies in Italy using organization_industry_tag_ids."""
import asyncio, httpx, sys, json, time
sys.path.insert(0, "/app")
from app.db import async_session_maker
from app.models.integration import MCPIntegrationSetting
from app.services.encryption import decrypt_value
from sqlalchemy import select

async def main():
    async with async_session_maker() as s:
        r = await s.execute(select(MCPIntegrationSetting).where(
            MCPIntegrationSetting.integration_name == "apollo",
            MCPIntegrationSetting.user_id == 181))
        row = r.scalar_one_or_none()
        key = decrypt_value(row.api_key_encrypted).strip()

    hdr = {"X-Api-Key": key, "Content-Type": "application/json"}
    url = "https://api.apollo.io/api/v1/mixed_companies/search"
    params = {
        "organization_industry_tag_ids": ["5567cd82736964540d0b0000"],
        "organization_locations": ["Italy"],
        "organization_num_employees_ranges": ["1,10", "11,50", "51,200"],
        "per_page": 100,
    }

    all_domains = set()
    all_orgs = []
    t0 = time.time()

    for page in range(1, 51):
        async with httpx.AsyncClient(timeout=30) as c:
            resp = await c.post(url, headers=hdr, json={**params, "page": page})
            d = resp.json()
            orgs = d.get("organizations", []) or d.get("accounts", [])
            pag = d.get("pagination", {})
            total = pag.get("total_entries", 0)
            total_pages = pag.get("total_pages", 0)

            new = 0
            for o in orgs:
                dom = o.get("primary_domain") or ""
                if not dom:
                    wu = o.get("website_url") or ""
                    dom = wu.replace("https://", "").replace("http://", "").split("/")[0]
                if dom and dom not in all_domains:
                    all_domains.add(dom)
                    all_orgs.append({
                        "name": o.get("name"),
                        "domain": dom,
                        "industry": o.get("industry"),
                        "employees": o.get("estimated_num_employees"),
                    })
                    new += 1

            elapsed = time.time() - t0
            print(f"p{page}: {len(orgs)} ret, {new} new, {len(all_domains)} unique [{elapsed:.0f}s]")

            if len(orgs) == 0 or page >= total_pages:
                print(f"Stopped: orgs={len(orgs)}, page={page}/{total_pages}")
                break
            if len(all_domains) >= 1000:
                print("1000 reached!")
                break
        await asyncio.sleep(0.35)

    elapsed = time.time() - t0
    print(f"\nDONE: {len(all_domains)} unique from {page} pages in {elapsed:.0f}s ({page} credits)")
    samples = [o["name"] for o in all_orgs[:20]]
    print(f"Samples: {samples}")

    with open("/app/tests/tmp/fashion_italy_1000.json", "w") as f:
        json.dump(all_orgs, f, indent=2)
    print(f"Saved to /app/tests/tmp/fashion_italy_1000.json")

asyncio.run(main())
