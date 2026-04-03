"""Check total lists count, pagination, and archived lists."""
import asyncio, os, json, httpx

async def main():
    api_key = os.environ.get("GETSALES_API_KEY", "")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    base = "https://amazing.getsales.io"

    async with httpx.AsyncClient(timeout=30) as client:
        # Check get_lists (what the sync uses)
        resp = await client.get(f"{base}/leads/api/lists", headers=headers)
        lists = resp.json() if isinstance(resp.json(), list) else resp.json().get("data", [])
        print(f"GET /leads/api/lists: {len(lists)} lists")
        for l in lists:
            name = l.get("name", "?")
            count = l.get("leads_count", "?")
            print(f"  {name:55s} leads={count}")

        # Try paginated version
        resp = await client.post(f"{base}/leads/c3/api/lists", headers=headers,
                                  json={"page": 1, "per_page": 100})
        if resp.status_code == 200:
            data = resp.json()
            print(f"\nPOST /leads/c3/api/lists: total={data.get('total', '?')}, data count={len(data.get('data', []))}")
            for l in data.get("data", []):
                name = l.get("name", "?")
                count = l.get("leads_count", "?")
                rizzult = "rizzult" in name.lower()
                if rizzult:
                    print(f"  [RIZZULT] {name:50s} leads={count}")

        # Try data sources (import batches)
        resp = await client.get(f"{base}/leads/api/data-sources", headers=headers)
        if resp.status_code == 200:
            sources = resp.json() if isinstance(resp.json(), list) else resp.json().get("data", [])
            print(f"\nGET /leads/api/data-sources: {len(sources)} sources")
            rizzult_sources = [s for s in sources if "rizzult" in s.get("name", "").lower()]
            print(f"  Rizzult sources: {len(rizzult_sources)}")
            for s in rizzult_sources:
                print(f"    {s.get('name', '?'):55s} leads={s.get('leads_count', '?')}")

if __name__ == "__main__":
    asyncio.run(main())
