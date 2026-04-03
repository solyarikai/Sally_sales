import asyncio, httpx, sys, json
sys.path.insert(0, "/app")
from app.db import async_session_maker
from app.models.integration import MCPIntegrationSetting
from app.services.encryption import decrypt_value
from sqlalchemy import select

async def main():
    async with async_session_maker() as s:
        r = await s.execute(select(MCPIntegrationSetting).where(
            MCPIntegrationSetting.integration_name == "apollo", MCPIntegrationSetting.user_id == 181))
        row = r.scalar_one_or_none()
        key = decrypt_value(row.api_key_encrypted).strip()

    hdr = {"X-Api-Key": key, "Content-Type": "application/json"}
    url = "https://api.apollo.io/api/v1/mixed_companies/search"

    # Page 20 = companies 1900-2000 range from industry_tag_ids search
    async with httpx.AsyncClient(timeout=30) as c:
        resp = await c.post(url, headers=hdr, json={
            "organization_industry_tag_ids": ["5567cd82736964540d0b0000"],
            "organization_locations": ["Italy"],
            "organization_num_employees_ranges": ["1,10","11,50","51,200"],
            "per_page": 100, "page": 20,
        })
        d = resp.json()
        orgs = d.get("organizations", []) or d.get("accounts", [])

    companies = []
    for o in orgs:
        companies.append({
            "name": o.get("name", "?"),
            "domain": o.get("primary_domain", "?"),
            "industry": o.get("industry", "?"),
            "employees": o.get("estimated_num_employees"),
            "description": (o.get("short_description") or "")[:200],
        })

    with open("/app/last100.json", "w") as f:
        json.dump(companies, f, indent=2)
    print(f"Saved {len(companies)} companies to /app/last100.json")

asyncio.run(main())
