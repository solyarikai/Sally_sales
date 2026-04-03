"""Test: industry_tag_ids + keywords COMBINED — does it enlarge or narrow?
Also: organization_keywords vs q_organization_keyword_tags head to head."""
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
    tag_id = "5567cd82736964540d0b0000"  # apparel & fashion

    tests = [
        # Baselines
        ("industry_tag_ids ONLY", {"organization_industry_tag_ids": [tag_id]}),
        ("q_org_kw_tags 'fashion design' ONLY", {"q_organization_keyword_tags": ["fashion design"]}),
        ("org_keywords 'fashion design' ONLY", {"organization_keywords": ["fashion design"]}),

        # Combined: industry + q_organization_keyword_tags
        ("industry + q_kw_tags 'fashion design'", {"organization_industry_tag_ids": [tag_id], "q_organization_keyword_tags": ["fashion design"]}),
        ("industry + q_kw_tags 'leather goods'", {"organization_industry_tag_ids": [tag_id], "q_organization_keyword_tags": ["leather goods"]}),
        ("industry + q_kw_tags 'fashion brand'", {"organization_industry_tag_ids": [tag_id], "q_organization_keyword_tags": ["fashion brand"]}),
        ("industry + q_kw_tags 3 keywords", {"organization_industry_tag_ids": [tag_id], "q_organization_keyword_tags": ["fashion design", "leather goods", "fashion brand"]}),

        # Combined: industry + organization_keywords
        ("industry + org_kw 'fashion design'", {"organization_industry_tag_ids": [tag_id], "organization_keywords": ["fashion design"]}),
        ("industry + org_kw 'leather goods'", {"organization_industry_tag_ids": [tag_id], "organization_keywords": ["leather goods"]}),
        ("industry + org_kw 'fashion brand'", {"organization_industry_tag_ids": [tag_id], "organization_keywords": ["fashion brand"]}),
        ("industry + org_kw 3 keywords", {"organization_industry_tag_ids": [tag_id], "organization_keywords": ["fashion design", "leather goods", "fashion brand"]}),

        # Head to head: org_keywords vs q_org_keyword_tags (same keywords)
        ("q_kw_tags ['leather goods']", {"q_organization_keyword_tags": ["leather goods"]}),
        ("org_kw ['leather goods']", {"organization_keywords": ["leather goods"]}),
        ("q_kw_tags ['textile']", {"q_organization_keyword_tags": ["textile"]}),
        ("org_kw ['textile']", {"organization_keywords": ["textile"]}),
        ("q_kw_tags ['shopping']", {"q_organization_keyword_tags": ["shopping"]}),
        ("org_kw ['shopping']", {"organization_keywords": ["shopping"]}),
    ]

    print(f"{'Filter':<45} {'P1':>4} {'P2':>4} {'P3':>4} {'P4':>4} {'P5':>4} {'P6':>4} {'P7':>4} {'P8':>4} {'P9':>4} {'P10':>4} {'Sum':>5} {'Total':>7}")
    print("-" * 130)

    for label, extra in tests:
        pages = []
        total = 0
        for page in range(1, 11):
            async with httpx.AsyncClient(timeout=30) as c:
                resp = await c.post(url, headers=hdr, json={**base, **extra, "page": page})
                d = resp.json()
                orgs = d.get("organizations", []) or d.get("accounts", [])
                total = d.get("pagination", {}).get("total_entries", 0)
                pages.append(len(orgs))
            await asyncio.sleep(0.35)
        s = sum(pages)
        print(f"{label:<45} {pages[0]:>4} {pages[1]:>4} {pages[2]:>4} {pages[3]:>4} {pages[4]:>4} {pages[5]:>4} {pages[6]:>4} {pages[7]:>4} {pages[8]:>4} {pages[9]:>4} {s:>5} {total:>7}")

asyncio.run(main())
