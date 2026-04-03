"""Try various GetSales export endpoints."""
import asyncio, os, httpx

async def main():
    api_key = os.environ.get("GETSALES_API_KEY", "")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    base = "https://amazing.getsales.io"

    test_flow = "9515a70b-0020-4955-8bea-9c2f7b904be8"

    endpoints = [
        ("POST", "/leads/api/leads/export", {"filter": {}, "flow_uuid": test_flow}),
        ("POST", "/leads/c3/api/leads/export", {"filter": {}, "flow_uuid": test_flow}),
        ("POST", f"/flows/api/flows/{test_flow}/export", {}),
        ("POST", f"/flows/c3/api/flows/{test_flow}/export", {}),
        ("POST", "/flows/api/flow-leads/export", {"flow_uuid": test_flow}),
        ("POST", f"/flows/c3/api/flow-leads/{test_flow}/export", {}),
        ("GET", f"/flows/api/flows/{test_flow}/export", None),
        ("GET", f"/leads/api/leads/export?flow_uuid={test_flow}", None),
        ("POST", "/leads/api/export", {"filter": {"flow_uuid": test_flow}}),
        ("POST", "/leads/c3/api/export", {"flow_uuid": test_flow}),
        # Try flow-leads listing endpoints
        ("POST", f"/flows/api/flow-leads", {"flow_uuid": test_flow, "page": 1, "per_page": 5}),
        ("POST", f"/flows/c3/api/flow-leads", {"flow_uuid": test_flow, "page": 1, "per_page": 5}),
        ("GET", f"/flows/api/flow-leads?flow_uuid={test_flow}&limit=5", None),
        ("POST", "/flows/c3/api/flows/leads", {"flow_uuid": test_flow, "page": 1, "per_page": 5}),
        ("POST", "/flows/c3/api/flows/leads/list", {"flow_uuid": test_flow, "page": 1, "per_page": 5}),
        # Try with filter object
        ("POST", "/leads/c3/api/leads/list", {"page": 1, "per_page": 5, "include_flows": True, "filter": {"flow_uuid": test_flow}}),
        ("POST", "/leads/c3/api/leads/list", {"page": 1, "per_page": 5, "include_flows": True, "filters": [{"field": "flow_uuid", "value": test_flow}]}),
    ]

    async with httpx.AsyncClient(timeout=15) as client:
        for method, ep, body in endpoints:
            try:
                url = f"{base}{ep}"
                if method == "POST":
                    resp = await client.post(url, headers=headers, json=body)
                else:
                    resp = await client.get(url, headers=headers)
                status = resp.status_code
                text = resp.text[:300]
                # Highlight successful/interesting responses
                if status == 200:
                    print(f"  *** {method} {ep}: {status}")
                    print(f"      {text[:200]}")
                elif status not in (404, 405, 422):
                    print(f"  {method} {ep}: {status} | {text[:100]}")
            except Exception as e:
                print(f"  {method} {ep}: ERROR {str(e)[:80]}")

if __name__ == "__main__":
    asyncio.run(main())
