"""Test every keyword — 10 pages each for consistent pagination data."""
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

    keywords = [
        # From enrichment
        "retail apparel & fashion", "fashion", "leather goods", "men's clothing",
        "shopping", "women's clothing",
        # Simple / derived
        "fashion brand", "luxury fashion", "apparel", "luxury", "clothing",
        "textile", "fashion design", "fashion retail", "italian fashion", "haute couture",
        # Also test industry_tag_ids for comparison
    ]

    print(f"{'Keyword':<30} {'P1':>4} {'P2':>4} {'P3':>4} {'P4':>4} {'P5':>4} {'P6':>4} {'P7':>4} {'P8':>4} {'P9':>4} {'P10':>4} {'Sum':>5} {'Total':>7}")
    print("-" * 120)

    for kw in keywords:
        pages = []
        total = 0
        for page in range(1, 11):
            async with httpx.AsyncClient(timeout=30) as c:
                resp = await c.post(url, headers=hdr, json={**base, "q_organization_keyword_tags": [kw], "page": page})
                d = resp.json()
                orgs = d.get("organizations", []) or d.get("accounts", [])
                total = d.get("pagination", {}).get("total_entries", 0)
                pages.append(len(orgs))
            await asyncio.sleep(0.35)
        s = sum(pages)
        print(f"{kw:<30} {pages[0]:>4} {pages[1]:>4} {pages[2]:>4} {pages[3]:>4} {pages[4]:>4} {pages[5]:>4} {pages[6]:>4} {pages[7]:>4} {pages[8]:>4} {pages[9]:>4} {s:>5} {total:>7}")

    # Also test industry_tag_id for comparison
    print(f"\n{'INDUSTRY_TAG_ID':<30}", end="")
    pages = []
    total = 0
    for page in range(1, 11):
        async with httpx.AsyncClient(timeout=30) as c:
            resp = await c.post(url, headers=hdr, json={**base, "organization_industry_tag_ids": ["5567cd82736964540d0b0000"], "page": page})
            d = resp.json()
            orgs = d.get("organizations", []) or d.get("accounts", [])
            total = d.get("pagination", {}).get("total_entries", 0)
            pages.append(len(orgs))
        await asyncio.sleep(0.35)
    s = sum(pages)
    print(f" {pages[0]:>4} {pages[1]:>4} {pages[2]:>4} {pages[3]:>4} {pages[4]:>4} {pages[5]:>4} {pages[6]:>4} {pages[7]:>4} {pages[8]:>4} {pages[9]:>4} {s:>5} {total:>7}")

asyncio.run(main())
