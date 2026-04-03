"""Test media_production tag_id for Video UK — the CORRECT tag."""
import asyncio, httpx, sys, random
sys.path.insert(0, "/app")
from app.db import async_session_maker
from app.models.integration import MCPIntegrationSetting
from app.services.encryption import decrypt_value
from app.services.scraper_service import ScraperService
from sqlalchemy import select

async def main():
    async with async_session_maker() as s:
        r = await s.execute(select(MCPIntegrationSetting).where(
            MCPIntegrationSetting.integration_name == "apollo", MCPIntegrationSetting.user_id == 181))
        apollo_key = decrypt_value(r.scalar_one_or_none().api_key_encrypted).strip()
        r2 = await s.execute(select(MCPIntegrationSetting).where(
            MCPIntegrationSetting.integration_name == "apify", MCPIntegrationSetting.user_id == 181))
        apify_pw = decrypt_value(r2.scalar_one_or_none().api_key_encrypted).strip()

    hdr = {"X-Api-Key": apollo_key, "Content-Type": "application/json"}

    # media production = 5567e0ea7369640d2ba31600
    async with httpx.AsyncClient(timeout=30) as c:
        resp = await c.post("https://api.apollo.io/api/v1/mixed_companies/search", headers=hdr, json={
            "organization_industry_tag_ids": ["5567e0ea7369640d2ba31600"],
            "organization_locations": ["United Kingdom"],
            "organization_num_employees_ranges": ["11,50", "51,200"],
            "per_page": 100, "page": 3,
        })
        orgs = resp.json().get("organizations", [])
        print(f"Page 3: {len(orgs)} companies")

    with_domains = [o for o in orgs if o.get("primary_domain")]
    sample = random.sample(with_domains, min(15, len(with_domains)))

    scraper = ScraperService(apify_proxy_password=apify_pw)
    tasks = [scraper.scrape_website(f"https://{o['primary_domain']}") for o in sample]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for org, sr in zip(sample, results):
        text = ""
        if isinstance(sr, dict) and sr.get("success"):
            text = sr["text"][:150]
        print(f"  {org.get('name','?')} ({org.get('primary_domain','?')}) — {text or '(no text)'}")

asyncio.run(main())
