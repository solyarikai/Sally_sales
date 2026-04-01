"""Test real enrichment keywords with all possible field names.
Also dump full enrichment response to see ALL fields Apollo returns."""
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

    # STEP 1: Full enrichment dump — see ALL fields Apollo returns
    print("=" * 60)
    print("FULL ENRICHMENT RESPONSE — versace.com")
    print("=" * 60)
    async with httpx.AsyncClient(timeout=30) as c:
        resp = await c.post("https://api.apollo.io/api/v1/organizations/enrich",
                            headers=hdr, json={"domain": "versace.com"})
        org = resp.json().get("organization", {})
        # Print ALL keys
        for k in sorted(org.keys()):
            v = org[k]
            if isinstance(v, (list, dict)) and len(str(v)) > 200:
                v = str(v)[:200] + "..."
            print(f"  {k}: {v}")

    print("\n" + "=" * 60)
    print("KEYWORD-RELATED FIELDS FROM ENRICHMENT")
    print("=" * 60)
    print(f"  industry: {org.get('industry')}")
    print(f"  industry_tag_id: {org.get('industry_tag_id')}")
    print(f"  keywords: {org.get('keywords')}")
    print(f"  keyword_tags: {org.get('keyword_tags')}")
    print(f"  sic_codes: {org.get('sic_codes')}")
    print(f"  subindustries: {org.get('subindustries')}")
    print(f"  industries: {org.get('industries')}")
    print(f"  secondary_industry_tag_ids: {org.get('secondary_industry_tag_ids')}")
    print(f"  technology_names: {(org.get('technology_names') or [])[:10]}")
    print(f"  intent_strength: {org.get('intent_strength')}")

    # Real enrichment keywords
    real_kws = org.get("keywords") or []
    print(f"\n  REAL KEYWORDS TO TEST: {real_kws}")

    # STEP 2: Test each keyword field with real enrichment values
    url = "https://api.apollo.io/api/v1/mixed_companies/search"
    base = {"organization_locations": ["Italy"], "organization_num_employees_ranges": ["1,10","11,50","51,200"], "per_page": 100}

    print("\n" + "=" * 60)
    print("SEARCH WITH REAL ENRICHMENT KEYWORDS — 3 pages each")
    print("=" * 60)

    field_names = [
        "q_organization_keyword_tags",
        "organization_keywords",
        "q_keywords",
        "keywords",
    ]

    for field in field_names:
        pages = []
        total = 0
        for page in [1, 2, 3]:
            async with httpx.AsyncClient(timeout=30) as c:
                resp = await c.post(url, headers=hdr, json={**base, field: real_kws[:5], "page": page})
                d = resp.json()
                orgs = d.get("organizations", []) or d.get("accounts", [])
                total = d.get("pagination", {}).get("total_entries", 0)
                pages.append(len(orgs))
            await asyncio.sleep(0.35)
        print(f"  {field}: pages={pages} total={total}")

    # Also test with a SINGLE real keyword
    for kw in real_kws[:3]:
        pages = []
        total = 0
        for page in [1, 2, 3]:
            async with httpx.AsyncClient(timeout=30) as c:
                resp = await c.post(url, headers=hdr, json={**base, "q_organization_keyword_tags": [kw], "page": page})
                d = resp.json()
                orgs = d.get("organizations", []) or d.get("accounts", [])
                total = d.get("pagination", {}).get("total_entries", 0)
                pages.append(len(orgs))
            await asyncio.sleep(0.35)
        print(f"  single q_org_kw_tags '{kw}': pages={pages} total={total}")

asyncio.run(main())
