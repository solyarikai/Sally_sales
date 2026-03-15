"""
Count unique Rizzult contacts in GetSales by scanning all leads in all lists
and checking their flow assignments. Also try flow-specific endpoints.
"""
import asyncio, os, json, httpx

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
        # Try flow-specific lead endpoints
        test_uuid = "9515a70b-0020-4955-8bea-9c2f7b904be8"
        endpoints = [
            f"/flows/c3/api/flows/{test_uuid}/leads",
            f"/flows/api/flow-leads/{test_uuid}",
            f"/flows/api/flows/{test_uuid}/leads",
            f"/leads/c3/api/leads/list",  # with flow_uuid filter
        ]

        for ep in endpoints[:-1]:
            try:
                url = f"https://amazing.getsales.io{ep}"
                resp = await client.get(url, headers=headers, params={"limit": 1})
                print(f"GET {ep}: {resp.status_code}")
                if resp.status_code == 200:
                    data = resp.json()
                    print(f"  Response keys: {list(data.keys()) if isinstance(data, dict) else 'list'}")
                    print(f"  Sample: {json.dumps(data)[:300]}")
            except Exception as e:
                print(f"GET {ep}: ERROR {e}")

        # Try POST /leads/c3/api/leads/list with flow_uuid filter
        try:
            resp = await client.post(
                "https://amazing.getsales.io/leads/c3/api/leads/list",
                headers=headers,
                json={
                    "page": 1, "per_page": 1,
                    "include_flows": True,
                    "filter": {"flow_uuid": test_uuid}
                }
            )
            data = resp.json()
            print(f"\nPOST /leads/c3/api/leads/list with flow_uuid filter: {resp.status_code}")
            print(f"  total: {data.get('total', '?')}")
        except Exception as e:
            print(f"  ERROR: {e}")

        # Try flow_uuids array filter
        try:
            resp = await client.post(
                "https://amazing.getsales.io/leads/c3/api/leads/list",
                headers=headers,
                json={
                    "page": 1, "per_page": 1,
                    "include_flows": True,
                    "flow_uuids": [test_uuid]
                }
            )
            data = resp.json()
            print(f"\nPOST /leads/c3/api/leads/list with flow_uuids: {resp.status_code}")
            print(f"  total: {data.get('total', '?')}")
        except Exception as e:
            print(f"  ERROR: {e}")

        # Try the /flows/c3/api/flow-leads endpoint with POST
        for ep in ["/flows/c3/api/flow-leads", "/flows/c3/api/flows/leads"]:
            try:
                resp = await client.post(
                    f"https://amazing.getsales.io{ep}",
                    headers=headers,
                    json={"flow_uuid": test_uuid, "page": 1, "per_page": 1}
                )
                print(f"\nPOST {ep}: {resp.status_code}")
                if resp.status_code == 200:
                    data = resp.json()
                    print(f"  keys: {list(data.keys()) if isinstance(data, dict) else 'list'}")
                    print(f"  total: {data.get('total', '?')}")
                    print(f"  Sample: {json.dumps(data)[:300]}")
            except Exception as e:
                print(f"  ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(main())
