"""Test: are Apollo filters OR or AND when combined?"""
import asyncio, httpx, sys
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
    base = {"organization_locations": ["Italy"], "organization_num_employees_ranges": ["11,50","51,200","201,500"], "per_page": 100, "page": 2}

    tests = {
        "A: industry_tag_ids ONLY": {**base, "organization_industry_tag_ids": ["5567cd82736964540d0b0000"]},
        "B: keyword_tags ONLY": {**base, "q_organization_keyword_tags": ["fashion", "luxury", "apparel"]},
        "C: industry_ids + keywords": {**base, "organization_industry_tag_ids": ["5567cd82736964540d0b0000"], "q_organization_keyword_tags": ["fashion", "luxury"]},
        "D: industry_ids + name_search": {**base, "organization_industry_tag_ids": ["5567cd82736964540d0b0000"], "q_organization_name": "fashion"},
        "E: ALL combined": {**base, "organization_industry_tag_ids": ["5567cd82736964540d0b0000"], "q_organization_keyword_tags": ["fashion"], "q_organization_name": "fashion"},
        "F: 2 industry_tag_ids": {**base, "organization_industry_tag_ids": ["5567cd82736964540d0b0000", "5567cd4773696439b10b0000"]},
    }

    for label, params in tests.items():
        async with httpx.AsyncClient(timeout=30) as c:
            resp = await c.post(url, headers=hdr, json=params)
            d = resp.json()
            orgs = d.get("organizations", []) or d.get("accounts", [])
            total = d.get("pagination", {}).get("total_entries", 0)
            names = [o.get("name", "?") for o in orgs[:3]]
            print(f"{label}: {len(orgs)} orgs p2, total={total}, samples={names}")
        await asyncio.sleep(0.5)

asyncio.run(main())
