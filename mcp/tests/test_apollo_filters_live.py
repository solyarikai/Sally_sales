"""Test different Apollo filter approaches to find the best one.
Run: docker exec mcp-backend python /app/tests/test_apollo_filters_live.py
"""
import asyncio
import httpx
import json
import sys
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


async def search(key, params, label):
    headers = {"X-Api-Key": key, "Content-Type": "application/json"}
    url = "https://api.apollo.io/api/v1/mixed_companies/search"
    async with httpx.AsyncClient(timeout=30) as c:
        resp = await c.post(url, headers=headers, json=params)
        data = resp.json()
        orgs = data.get("organizations", []) or data.get("accounts", [])
        pagination = data.get("pagination", {})
        total = pagination.get("total_entries", 0)
        total_pages = pagination.get("total_pages", 0)
        print(f"  {label}: {len(orgs)} orgs, total={total}, pages={total_pages}")
        if orgs:
            for o in orgs[:3]:
                print(f"    - {o.get('name', '?')} ({o.get('primary_domain', '?')}) industry={o.get('industry', '?')}")
        return len(orgs), total


async def main():
    key = await get_key()
    if not key:
        print("No Apollo key for user 181")
        return

    print("=" * 60)
    print("APOLLO FILTER TESTS — Fashion Brands Italy")
    print("=" * 60)

    # Test 1: q_organization_keyword_tags (current approach)
    print("\n1. q_organization_keyword_tags (current):")
    for page in [1, 2, 3]:
        await search(key, {
            "q_organization_keyword_tags": ["apparel & fashion"],
            "organization_locations": ["Italy"],
            "organization_num_employees_ranges": ["11,200"],
            "per_page": 100, "page": page,
        }, f"page {page}")
    await asyncio.sleep(0.5)

    # Test 2: Multiple keyword_tags
    print("\n2. Multiple keyword_tags:")
    await search(key, {
        "q_organization_keyword_tags": ["apparel & fashion", "luxury goods & jewelry", "textiles"],
        "organization_locations": ["Italy"],
        "organization_num_employees_ranges": ["11,200"],
        "per_page": 100, "page": 2,
    }, "multi-tags p2")
    await asyncio.sleep(0.5)

    # Test 3: q_organization_name (text search)
    print("\n3. q_organization_name (text search 'fashion'):")
    await search(key, {
        "q_organization_name": "fashion",
        "organization_locations": ["Italy"],
        "per_page": 100, "page": 1,
    }, "name=fashion p1")
    await asyncio.sleep(0.5)

    # Test 4: No keywords, just industry + location
    print("\n4. No keywords, just location + size:")
    await search(key, {
        "organization_locations": ["Italy"],
        "organization_num_employees_ranges": ["11,200"],
        "per_page": 100, "page": 2,
    }, "location+size p2")
    await asyncio.sleep(0.5)

    # Test 5: q_keywords (maybe different from keyword_tags?)
    print("\n5. q_keywords instead of q_organization_keyword_tags:")
    await search(key, {
        "q_keywords": "fashion brand apparel",
        "organization_locations": ["Italy"],
        "per_page": 100, "page": 1,
    }, "q_keywords p1")
    await asyncio.sleep(0.5)

    # Test 6: organization_industry_tag_ids with string names
    print("\n6. organization_industry_tag_ids (string names):")
    await search(key, {
        "organization_industry_tag_ids": ["apparel & fashion", "luxury goods & jewelry"],
        "organization_locations": ["Italy"],
        "per_page": 100, "page": 2,
    }, "industry_ids p2")
    await asyncio.sleep(0.5)

    # Test 7: Broader — just "fashion" in Italy, all sizes
    print("\n7. q_organization_keyword_tags=['fashion'] only:")
    for page in [1, 2, 3, 4, 5]:
        count, _ = await search(key, {
            "q_organization_keyword_tags": ["fashion"],
            "organization_locations": ["Italy"],
            "per_page": 100, "page": page,
        }, f"page {page}")
        if count == 0:
            break


asyncio.run(main())
