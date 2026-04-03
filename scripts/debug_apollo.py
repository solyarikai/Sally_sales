"""Debug Apollo bulk_match response structure."""
import asyncio
import json
import logging
import os
import sys

sys.path.insert(0, "/app")
os.environ.setdefault("DATABASE_URL", os.environ.get("DATABASE_URL", ""))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("debug_apollo")
logging.getLogger("httpx").setLevel(logging.WARNING)

import httpx

API_KEY = os.environ.get("APOLLO_API_KEY", "")
BASE = "https://api.apollo.io/api/v1"
HEADERS = {"Content-Type": "application/json", "Cache-Control": "no-cache", "X-Api-Key": API_KEY}


async def test_domain(domain: str):
    logger.info(f"=== Testing {domain} ===")
    async with httpx.AsyncClient(timeout=30) as client:
        # Step 1: Search
        resp = await client.post(f"{BASE}/mixed_people/api_search", json={
            "q_organization_domains": domain,
            "page": 1,
            "per_page": 5,
        }, headers=HEADERS)
        resp.raise_for_status()
        search_data = resp.json()
        people = search_data.get("people", [])
        logger.info(f"Search found {len(people)} people")
        for p in people[:3]:
            logger.info(f"  - {p.get('first_name')} {p.get('last_name')}: {p.get('title')} | email={p.get('email')} | linkedin={p.get('linkedin_url')}")

        if not people:
            return

        # Step 2: Build details for bulk_match
        details = []
        for person in people:
            first_name = person.get("first_name")
            if not first_name:
                continue
            details.append({
                "first_name": first_name,
                "last_name": person.get("last_name") or "",
                "domain": domain,
            })

        logger.info(f"Bulk matching {len(details)} people...")
        await asyncio.sleep(2)  # rate limit

        resp2 = await client.post(f"{BASE}/people/bulk_match", json={
            "details": details,
            "reveal_personal_emails": True,
        }, headers=HEADERS)
        resp2.raise_for_status()
        bulk_data = resp2.json()

        # Print raw keys
        logger.info(f"bulk_match response keys: {list(bulk_data.keys())}")
        matches = bulk_data.get("matches", [])
        logger.info(f"matches count: {len(matches)}")

        for i, match in enumerate(matches):
            if match is None:
                logger.info(f"  match[{i}]: None")
            elif isinstance(match, dict):
                logger.info(f"  match[{i}]: id={match.get('id')} email={match.get('email')} "
                           f"name={match.get('first_name')} {match.get('last_name')} "
                           f"title={match.get('title')} linkedin={match.get('linkedin_url')} "
                           f"email_status={match.get('email_status')}")
            else:
                logger.info(f"  match[{i}]: type={type(match)} value={str(match)[:200]}")

        # Also dump first match raw
        if matches and matches[0] is not None:
            logger.info(f"First match raw keys: {list(matches[0].keys()) if isinstance(matches[0], dict) else 'N/A'}")
            logger.info(f"First match raw (truncated): {json.dumps(matches[0], default=str)[:500]}")

        # Try alternative: /people/match (single person)
        logger.info(f"\n--- Also testing /people/match for first person ---")
        if details:
            await asyncio.sleep(2)
            resp3 = await client.post(f"{BASE}/people/match", json={
                "first_name": details[0]["first_name"],
                "last_name": details[0]["last_name"],
                "domain": domain,
                "reveal_personal_emails": True,
            }, headers=HEADERS)
            resp3.raise_for_status()
            match_data = resp3.json()
            logger.info(f"/people/match keys: {list(match_data.keys())}")
            person = match_data.get("person")
            if person:
                logger.info(f"  person: id={person.get('id')} email={person.get('email')} "
                           f"name={person.get('first_name')} {person.get('last_name')} "
                           f"title={person.get('title')} linkedin={person.get('linkedin_url')}")
            else:
                logger.info(f"  person: None")
                logger.info(f"  full response: {json.dumps(match_data, default=str)[:500]}")


async def main():
    # Test with known working domain first
    await test_domain("getsally.io")
    await asyncio.sleep(3)
    # Test with a domain that showed "bulk_matched=5 but 0 enriched"
    await test_domain("naresco.ae")


if __name__ == "__main__":
    asyncio.run(main())
