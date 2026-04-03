"""
Scan ALL GetSales leads by chunking through date ranges.
Uses /leads/api/leads/search which supports real filtering.
Find all unique Rizzult contacts and import missing ones to CRM.
"""
import asyncio, os, json, httpx
from datetime import datetime, timedelta

RIZZULT_FLOW_UUIDS = {
    "9515a70b-0020-4955-8bea-9c2f7b904be8", "779377b5-4856-4f0e-b028-19ebff994dce",
    "3323b4f3-d0e9-427e-9540-191e10b8d4d7", "5a8628e0-f8b5-43f7-9477-0bd825bb7ee5",
    "0089aa05-f8a3-4a0b-ab94-00db9603dd7d", "df157019-c1fb-4562-b136-b92c9a9c99ab",
    "60b1ab51-5139-4256-a2fa-92bd88252d7d", "8c164da8-d63c-42b9-9a83-1c5e7194d5ba",
    "65a4fa58-434a-4760-a6e7-dc6ce3903ff6", "4bbd26d3-706b-4168-9262-d70fe09a5b25",
    "23f9f8fa-a1e3-4871-8ca9-8bdb983c9342", "822cb361-7b5f-4432-bef1-5408ae1b1d8b",
    "b88fda57-2d47-46a5-91bc-01cc33f73c90", "0e9ecb75-919a-4491-b7ac-6e774028722b",
    "6bfeca8c-23a6-49da-a8e8-b0dacae88857", "1e18fad6-2d9d-4ec8-8256-9850a6ea43bc",
    "10120436-8605-448b-80f0-f2a25730163d", "ef930f4c-c113-4d80-bea6-492ff60b68cf",
    "f917f58a-2b77-4613-9adb-63ca94183dac", "1450e076-dd6f-4d10-a193-eb6a1a92e692",
    "497cae2b-1b79-40cf-84d7-4c92bb0ace64", "b002e2fc-d647-491f-808f-89af1ac671f0",
    "b2182d2f-45d2-4174-b388-d43f644b84b4",
}

async def main():
    api_key = os.environ.get("GETSALES_API_KEY", "")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=30) as client:
        # First, test if date filters work on /leads/api/leads/search
        print("Testing date filter support on /leads/api/leads/search...")

        test_filter = {
            "created_at_from": "2026-03-01",
            "created_at_to": "2026-03-08",
        }
        resp = await client.post(
            "https://amazing.getsales.io/leads/api/leads/search",
            headers=headers,
            json={"filter": test_filter, "limit": 1, "offset": 0}
        )
        data = resp.json()
        total_march = data.get("total", "?")
        print(f"  March 1-8 2026: total={total_march}")

        # Also try without date filter
        resp = await client.post(
            "https://amazing.getsales.io/leads/api/leads/search",
            headers=headers,
            json={"filter": {}, "limit": 1, "offset": 0}
        )
        total_all = resp.json().get("total", "?")
        print(f"  No filter: total={total_all}")

        # If the totals differ, date filtering works!
        if total_march != total_all:
            print(f"  DATE FILTERING WORKS! ({total_march} vs {total_all})")
        else:
            # Try alternative filter formats
            for fmt_name, fmt_filter in [
                ("created_from/to", {"created_from": "2026-03-01", "created_to": "2026-03-08"}),
                ("date range", {"date_from": "2026-03-01", "date_to": "2026-03-08"}),
                ("created_at range obj", {"created_at": {"from": "2026-03-01", "to": "2026-03-08"}}),
            ]:
                resp = await client.post(
                    "https://amazing.getsales.io/leads/api/leads/search",
                    headers=headers,
                    json={"filter": fmt_filter, "limit": 1, "offset": 0}
                )
                t = resp.json().get("total", "?")
                print(f"  {fmt_name}: total={t}")
                if t != total_all:
                    print(f"    WORKS!")
                    break

        # Try top-level date params instead of inside filter
        for fmt_name, payload in [
            ("top-level created_at_from", {"created_at_from": "2026-03-01", "created_at_to": "2026-03-08", "limit": 1, "offset": 0}),
            ("top-level date_from", {"date_from": "2026-03-01", "date_to": "2026-03-08", "limit": 1, "offset": 0}),
        ]:
            resp = await client.post(
                "https://amazing.getsales.io/leads/api/leads/search",
                headers=headers,
                json=payload
            )
            t = resp.json().get("total", "?")
            print(f"  {fmt_name}: total={t}")
            if t != total_all:
                print(f"    WORKS!")

        # Try text search / query filter
        for fmt_name, flt in [
            ("q=rizzult", {"q": "rizzult"}),
            ("query=rizzult", {"query": "rizzult"}),
            ("search=rizzult", {"search": "rizzult"}),
            ("name filter", {"name": "rizzult"}),
        ]:
            resp = await client.post(
                "https://amazing.getsales.io/leads/api/leads/search",
                headers=headers,
                json={"filter": flt, "limit": 1, "offset": 0}
            )
            t = resp.json().get("total", "?")
            print(f"  {fmt_name}: total={t}")
            if t != total_all:
                print(f"    WORKS!")

        # Try /leads/c3/api/leads/list with proper filtering
        print("\nTesting /leads/c3/api/leads/list with filters...")
        for fmt_name, payload in [
            ("created_at_from top-level", {"page": 1, "per_page": 1, "include_flows": True, "created_at_from": "2026-03-01", "created_at_to": "2026-03-08"}),
            ("filter.created_at_from", {"page": 1, "per_page": 1, "include_flows": True, "filter": {"created_at_from": "2026-03-01", "created_at_to": "2026-03-08"}}),
            ("filters array", {"page": 1, "per_page": 1, "include_flows": True, "filters": [{"field": "created_at", "operator": ">=", "value": "2026-03-01"}, {"field": "created_at", "operator": "<=", "value": "2026-03-08"}]}),
        ]:
            resp = await client.post(
                "https://amazing.getsales.io/leads/c3/api/leads/list",
                headers=headers,
                json=payload
            )
            t = resp.json().get("total", "?")
            print(f"  {fmt_name}: total={t}")
            if t != total_all and t != 250624:
                print(f"    WORKS! (different from {total_all})")

if __name__ == "__main__":
    asyncio.run(main())
