"""Test which filters work on GetSales search API."""
import asyncio, os, httpx

async def try_search(client, headers, label, payload):
    try:
        resp = await client.post(
            "https://amazing.getsales.io/leads/api/leads/search",
            headers=headers,
            json=payload,
            timeout=15
        )
        if resp.status_code != 200:
            print(f"  {label}: HTTP {resp.status_code} | {resp.text[:100]}")
            return
        try:
            data = resp.json()
            total = data.get("total", "?")
            count = len(data.get("data", []))
            print(f"  {label}: total={total}, returned={count}")
            return total
        except:
            print(f"  {label}: non-JSON response | {resp.text[:100]}")
    except Exception as e:
        print(f"  {label}: ERROR {str(e)[:80]}")

async def main():
    api_key = os.environ.get("GETSALES_API_KEY", "")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    async with httpx.AsyncClient() as client:
        # Baseline
        base = await try_search(client, headers, "no filter", {"filter": {}, "limit": 1, "offset": 0})

        # Date formats
        for label, flt in [
            ("created_at_from ISO", {"created_at_from": "2026-03-01T00:00:00Z"}),
            ("created_at_from date", {"created_at_from": "2026-03-01"}),
            ("created_at_from ts", {"created_at_from": 1740787200}),
            ("created_from date", {"created_from": "2026-03-01"}),
        ]:
            await try_search(client, headers, label, {"filter": flt, "limit": 1, "offset": 0})

        # List-based (known working)
        print("\nList filter (known working):")
        # Get a list UUID
        resp = await client.get("https://amazing.getsales.io/leads/api/lists", headers=headers)
        lists = resp.json() if isinstance(resp.json(), list) else resp.json().get("data", [])
        if lists:
            luuid = lists[0].get("uuid", "")
            await try_search(client, headers, f"list_uuid={luuid[:8]}", {"filter": {"list_uuid": luuid}, "limit": 1, "offset": 0})

        # Try c3 API with sort_by for deterministic pagination
        print("\n/leads/c3/api/leads/list filter tests:")
        for label, payload in [
            ("baseline", {"page": 1, "per_page": 1, "include_flows": True}),
            ("sort by created_at", {"page": 1, "per_page": 1, "include_flows": True, "sort_by": "created_at", "sort_order": "asc"}),
            ("sort by uuid", {"page": 1, "per_page": 1, "include_flows": True, "sort_by": "uuid", "sort_order": "asc"}),
        ]:
            try:
                resp = await client.post(
                    "https://amazing.getsales.io/leads/c3/api/leads/list",
                    headers=headers,
                    json=payload,
                    timeout=15
                )
                data = resp.json()
                total = data.get("total", "?")
                items = data.get("data", [])
                if items:
                    lead = items[0].get("lead", items[0])
                    print(f"  {label}: total={total}, first_uuid={lead.get('uuid', '?')[:12]}, created={lead.get('created_at', '?')[:16]}")
                else:
                    print(f"  {label}: total={total}, no data")
            except Exception as e:
                print(f"  {label}: ERROR {str(e)[:80]}")

        # Check what page numbers work
        print("\nPagination test (c3 API, trying high pages):")
        for pg in [1, 100, 500, 1000, 2500, 2507]:
            try:
                resp = await client.post(
                    "https://amazing.getsales.io/leads/c3/api/leads/list",
                    headers=headers,
                    json={"page": pg, "per_page": 100, "include_flows": True},
                    timeout=15
                )
                data = resp.json()
                total = data.get("total", "?")
                items = data.get("data", [])
                if items:
                    lead = items[0].get("lead", items[0])
                    has_flows = any(True for i in items if i.get("flows"))
                    print(f"  page {pg}: total={total}, returned={len(items)}, has_flows={has_flows}, first_created={lead.get('created_at', '?')[:16]}")
                else:
                    print(f"  page {pg}: total={total}, returned=0")
            except Exception as e:
                print(f"  page {pg}: ERROR {str(e)[:80]}")

if __name__ == "__main__":
    asyncio.run(main())
