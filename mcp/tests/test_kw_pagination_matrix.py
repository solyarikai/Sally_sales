"""Test EVERY keyword from enrichment + simple variants — 5 pages each.
Find which keywords give good pagination vs broken."""
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
    base = {"organization_locations": ["Italy"], "organization_num_employees_ranges": ["1,10","11,50","51,200"], "per_page": 100}

    # From Versace enrichment
    enrichment_keywords = [
        "retail apparel & fashion",
        "fashion",
        "leather goods",
        "men's clothing",
        "shopping",
        "women's clothing",
    ]

    # Simple / derived keywords
    simple_keywords = [
        "fashion brand",
        "luxury fashion",
        "apparel",
        "luxury",
        "clothing",
        "textile",
        "fashion design",
        "fashion retail",
        "italian fashion",
        "haute couture",
    ]

    all_keywords = enrichment_keywords + simple_keywords

    print(f"{'Keyword':<30} {'P1':>5} {'P2':>5} {'P3':>5} {'P4':>5} {'P5':>5} {'Total':>8} {'Pagination':>12}")
    print("-" * 95)

    for kw in all_keywords:
        pages = []
        total = 0
        for page in range(1, 6):
            async with httpx.AsyncClient(timeout=30) as c:
                resp = await c.post(url, headers=hdr, json={
                    **base,
                    "q_organization_keyword_tags": [kw],
                    "page": page,
                })
                d = resp.json()
                orgs = d.get("organizations", []) or d.get("accounts", [])
                total = d.get("pagination", {}).get("total_entries", 0)
                pages.append(len(orgs))
            await asyncio.sleep(0.35)

        # Judge pagination quality
        if len(pages) >= 3 and pages[1] >= 20 and pages[2] >= 20:
            quality = "GOOD"
        elif pages[0] >= 50 and pages[1] < 10:
            quality = "BROKEN"
        else:
            quality = "OK"

        print(f"{kw:<30} {pages[0]:>5} {pages[1]:>5} {pages[2]:>5} {pages[3]:>5} {pages[4]:>5} {total:>8} {quality:>12}")

asyncio.run(main())
