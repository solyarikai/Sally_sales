"""Find the correlation: Apollo enrichment labels → search filter parameters.

Step 1: Enrich known fashion companies → get ALL their Apollo labels
Step 2: Test each label type as a search filter → which gives good pagination?
Step 3: Find which enrichment field maps to which search parameter

Run: docker exec mcp-backend python /app/test_apollo_label_correlation.py
"""
import asyncio
import httpx
import json
import sys
import time
sys.path.insert(0, "/app")

from app.db import async_session_maker
from app.models.integration import MCPIntegrationSetting
from app.services.encryption import decrypt_value
from sqlalchemy import select


async def get_key():
    async with async_session_maker() as s:
        r = await s.execute(select(MCPIntegrationSetting).where(
            MCPIntegrationSetting.integration_name == "apollo",
            MCPIntegrationSetting.user_id == 181
        ))
        row = r.scalar_one_or_none()
        return decrypt_value(row.api_key_encrypted).strip() if row else None


async def enrich(key, domain):
    """Enrich a single company — extract ALL Apollo labels."""
    headers = {"X-Api-Key": key, "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as c:
        resp = await c.post(
            "https://api.apollo.io/api/v1/organizations/enrich",
            headers=headers, json={"domain": domain},
        )
        data = resp.json()
        org = data.get("organization", {})
        return org


async def search(key, params, label=""):
    """Search and return count + first 3 results."""
    headers = {"X-Api-Key": key, "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as c:
        resp = await c.post(
            "https://api.apollo.io/api/v1/mixed_companies/search",
            headers=headers, json=params,
        )
        data = resp.json()
        orgs = data.get("organizations", []) or data.get("accounts", [])
        pagination = data.get("pagination", {})
        return {
            "count": len(orgs),
            "total": pagination.get("total_entries", 0),
            "total_pages": pagination.get("total_pages", 0),
            "samples": [o.get("name", "?") for o in orgs[:3]],
        }


async def search_pages(key, params, max_pages=5):
    """Search multiple pages, return total unique companies."""
    all_names = set()
    per_page_counts = []
    for page in range(1, max_pages + 1):
        p = {**params, "page": page, "per_page": 100}
        r = await search(key, p)
        per_page_counts.append(r["count"])
        # Can't dedup without full data, just count
        if r["count"] == 0:
            break
        await asyncio.sleep(0.3)
    return per_page_counts


async def main():
    key = await get_key()
    if not key:
        print("No key"); return

    print("=" * 70)
    print("STEP 1: ENRICH known Italian fashion companies")
    print("=" * 70)

    targets = ["versace.com", "armani.com", "prada.com", "gucci.com", "moncler.com"]
    enriched = {}

    for domain in targets:
        org = await enrich(key, domain)
        if org:
            enriched[domain] = {
                "name": org.get("name", "?"),
                "industry": org.get("industry"),
                "industry_tag_id": org.get("industry_tag_id"),
                "keywords": org.get("keywords") or org.get("keyword_tags") or [],
                "sic_codes": org.get("sic_codes") or [],
                "short_description": (org.get("short_description") or "")[:100],
                "raw_industry_fields": {
                    "industry": org.get("industry"),
                    "industry_tag_id": org.get("industry_tag_id"),
                    "subindustries": org.get("subindustries"),
                    "secondary_industry_tag_ids": org.get("secondary_industry_tag_ids"),
                    "technology_names": (org.get("technology_names") or [])[:10],
                    "intent_strength": org.get("intent_strength"),
                    "departmental_head_count": org.get("departmental_head_count"),
                },
            }
            print(f"\n  {domain} ({org.get('name', '?')}):")
            print(f"    industry: {org.get('industry')}")
            print(f"    industry_tag_id: {org.get('industry_tag_id')}")
            print(f"    keywords: {(org.get('keywords') or org.get('keyword_tags') or [])[:10]}")
            print(f"    sic_codes: {org.get('sic_codes')}")
        else:
            print(f"\n  {domain}: ENRICH FAILED")
        await asyncio.sleep(0.5)

    # Collect common labels
    all_keywords = []
    all_industries = set()
    all_industry_ids = set()
    all_sic = set()
    for d, e in enriched.items():
        all_keywords.extend(e.get("keywords", []))
        if e.get("industry"):
            all_industries.add(e["industry"])
        if e.get("industry_tag_id"):
            all_industry_ids.add(e["industry_tag_id"])
        for s in e.get("sic_codes", []):
            all_sic.add(str(s))

    from collections import Counter
    keyword_freq = Counter(k.lower() for k in all_keywords)
    common_keywords = [k for k, v in keyword_freq.most_common(15)]

    print(f"\n\nCommon keywords: {common_keywords}")
    print(f"Industries: {all_industries}")
    print(f"Industry tag IDs: {all_industry_ids}")
    print(f"SIC codes: {all_sic}")

    print("\n" + "=" * 70)
    print("STEP 2: Test each label type as search filter (Italy, 5 pages)")
    print("=" * 70)

    # Base params
    base = {"organization_locations": ["Italy"], "per_page": 100}

    tests = [
        # Test with enrichment keyword_tags values
        ("q_organization_keyword_tags = common keywords", {
            **base, "q_organization_keyword_tags": common_keywords[:5],
        }),
        # Test with industry name
        ("q_organization_keyword_tags = industry names", {
            **base, "q_organization_keyword_tags": list(all_industries),
        }),
        # Test with industry_tag_id (if found)
        ("organization_industry_tag_ids = tag IDs", {
            **base, "organization_industry_tag_ids": list(all_industry_ids),
        }),
        # Test with just ONE simple keyword
        ("q_organization_keyword_tags = ['fashion']", {
            **base, "q_organization_keyword_tags": ["fashion"],
        }),
        # Test with q_organization_name
        ("q_organization_name = 'fashion brand'", {
            **base, "q_organization_name": "fashion brand",
        }),
        # Test with SIC codes
        ("organization_sic_codes = from enrichment", {
            **base, "q_organization_keyword_tags": ["fashion"],
        }),
        # Test enrichment keywords as q_organization_keyword_tags
        ("q_organization_keyword_tags = top 3 enrichment keywords", {
            **base, "q_organization_keyword_tags": common_keywords[:3],
        }),
        # CRITICAL: test without any keyword, just industry_tag_id + location
        ("organization_industry_tag_ids ONLY (no keywords)", {
            **base, "organization_industry_tag_ids": list(all_industry_ids),
        }),
    ]

    for label, params in tests:
        print(f"\n  {label}:")
        pages = await search_pages(key, params, max_pages=5)
        total_orgs = sum(pages)
        print(f"    Pages: {pages}")
        print(f"    Total: {total_orgs} orgs from {len([p for p in pages if p > 0])} pages")
        r = await search(key, {**params, "page": 1})
        print(f"    Apollo total_entries: {r['total']}")
        print(f"    Samples: {r['samples']}")
        await asyncio.sleep(1)

    # Save all results
    results = {"enriched": enriched, "common_keywords": common_keywords,
               "industries": list(all_industries), "industry_ids": list(all_industry_ids)}
    with open("/app/tests/tmp/apollo_label_correlation.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to /app/tests/tmp/apollo_label_correlation.json")


asyncio.run(main())
