"""Apollo API pagination test — how to get 1000 unique companies."""
import asyncio
import httpx
import json
from datetime import datetime

async def main():
    # Get Apollo key from DB
    from app.services.encryption import decrypt_value
    from sqlalchemy import select
    from app.db import async_session_maker
    from app.models.integration import MCPIntegrationSetting

    async with async_session_maker() as s:
        r = await s.execute(select(MCPIntegrationSetting).where(
            MCPIntegrationSetting.user_id == 179,
            MCPIntegrationSetting.integration_name == "apollo",
        ))
        row = r.scalar_one()
        api_key = decrypt_value(row.api_key_encrypted)

    filters = {
        "api_key": api_key,
        "q_organization_keyword_tags": ["information technology & services", "IT consulting", "software development"],
        "organization_locations": ["Miami, Florida, United States"],
        "organization_num_employees_ranges": ["11,200"],
    }

    all_domains = set()
    all_org_ids = set()
    results = []
    total_entries = None

    print(f"{'='*80}")
    print(f"Apollo Pagination Test — {datetime.now().isoformat()}")
    print(f"Filters: {json.dumps({k:v for k,v in filters.items() if k != 'api_key'}, indent=2)}")
    print(f"{'='*80}\n")

    for per_page in [25, 100]:
        print(f"\n{'#'*60}")
        print(f"# TEST: per_page={per_page}")
        print(f"{'#'*60}")

        page_domains = set()
        page_org_ids = set()

        for page in range(1, 12):  # Up to 11 pages
            payload = {**filters, "page": page, "per_page": per_page}

            async with httpx.AsyncClient(timeout=15) as c:
                resp = await c.post(
                    "https://api.apollo.io/api/v1/mixed_companies/search",
                    json=payload,
                )
                data = resp.json()

            orgs = data.get("organizations", [])
            pag = data.get("pagination", {})
            te = pag.get("total_entries", 0)
            tp = pag.get("total_pages", 0)

            if page == 1:
                total_entries = te

            # Extract domains and IDs
            page_new_domains = set()
            page_new_ids = set()
            duplicates_in_page = 0

            for org in orgs:
                domain = org.get("primary_domain") or org.get("website_url", "").replace("https://", "").replace("http://", "").split("/")[0]
                org_id = org.get("id", "")

                if domain in page_domains:
                    duplicates_in_page += 1
                else:
                    page_new_domains.add(domain)

                if org_id in page_org_ids:
                    pass
                else:
                    page_new_ids.add(org_id)

                page_domains.add(domain)
                page_org_ids.add(org_id)

            result = {
                "per_page": per_page,
                "page": page,
                "returned": len(orgs),
                "total_entries": te,
                "total_pages": tp,
                "new_unique_domains": len(page_new_domains),
                "cumulative_unique_domains": len(page_domains),
                "duplicates_within_all_pages": duplicates_in_page,
            }
            results.append(result)

            print(f"  Page {page:>2}: returned={len(orgs):>3}  total={te:>5}  "
                  f"new_unique={len(page_new_domains):>3}  "
                  f"cumulative={len(page_domains):>4}  "
                  f"dupes={duplicates_in_page}")

            if len(orgs) == 0:
                print(f"  → No more results. Stopping.")
                break

            await asyncio.sleep(0.3)  # Rate limit

        print(f"\n  SUMMARY (per_page={per_page}):")
        print(f"    Total entries reported by Apollo: {total_entries}")
        print(f"    Pages fetched: {page}")
        print(f"    Unique domains collected: {len(page_domains)}")
        print(f"    Unique org IDs collected: {len(page_org_ids)}")

    # Save full results
    output = {
        "timestamp": datetime.now().isoformat(),
        "filters": {k: v for k, v in filters.items() if k != "api_key"},
        "results": results,
    }

    with open("/app/apollo_debug_results.json", "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to /app/apollo_debug_results.json")


if __name__ == "__main__":
    asyncio.run(main())
