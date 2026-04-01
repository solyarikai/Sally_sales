"""Dump raw Apollo people enrichment (bulk_match) response to file."""
import asyncio, httpx, json, sys
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

    # Step 1: FREE search for IDs
    async with httpx.AsyncClient(timeout=20) as c:
        resp = await c.post("https://api.apollo.io/api/v1/mixed_people/api_search",
            headers=hdr, json={"q_organization_domains": "dondup.com",
                               "person_seniorities": ["c_suite", "vp", "director"],
                               "per_page": 5})
        search_raw = resp.json()
        people = search_raw.get("people", [])
        ids = [p["id"] for p in people if p.get("id") and p.get("has_email")][:3]
        print(f"Search: {len(people)} people, {len(ids)} with email+id")

    # Step 2: Enrichment (bulk_match)
    async with httpx.AsyncClient(timeout=20) as c:
        resp = await c.post("https://api.apollo.io/api/v1/people/bulk_match",
            headers=hdr, json={"details": [{"id": pid} for pid in ids],
                               "reveal_personal_emails": True})
        enrichment_raw = resp.json()

    # Print key fields
    for m in enrichment_raw.get("matches", []):
        if m:
            print(f"\n--- {m.get('first_name')} {m.get('last_name')} ---")
            print(f"  Title: {m.get('title')}")
            print(f"  Email: {m.get('email')}")
            print(f"  Email Status: {m.get('email_status')}")
            print(f"  Seniority: {m.get('seniority')}")
            print(f"  LinkedIn: {m.get('linkedin_url')}")
            print(f"  Personal Emails: {m.get('personal_emails')}")
            print(f"  City: {m.get('city')}, Country: {m.get('country')}")

    # Save both raw responses
    output = {
        "search_raw": search_raw,
        "enrichment_raw": enrichment_raw,
    }
    with open("/app/tests/tmp/enrichment_full_raw.json", "w") as f:
        json.dump(output, f, indent=2)
    print("\nSaved to /app/tests/tmp/enrichment_full_raw.json")

asyncio.run(main())
