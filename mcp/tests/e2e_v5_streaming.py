"""E2E v5 — Streaming pipeline test. Single segment, measure timing.
Run: docker exec mcp-backend python /app/e2e_v5_streaming.py
"""
import asyncio, httpx, sys, json, time
sys.path.insert(0, "/app")

TOKEN = "mcp_c3234bd4d160e4ea7502567a93702e43bc1ad71e28d7b6cf4e8bf02431521566"
API = "http://localhost:8000"


async def call_tool(name, args):
    async with httpx.AsyncClient(timeout=600) as c:
        resp = await c.post(f"{API}/api/tools/call",
            headers={"Content-Type": "application/json", "X-MCP-Token": TOKEN},
            json={"name": name, "arguments": args})
        return resp.json().get("result", resp.json())


async def main():
    t0 = time.time()
    print("E2E v5 — STREAMING PIPELINE — Fashion Italy")

    # Create project
    proj = await call_tool("create_project", {"name": "v5 Streaming", "website": "https://thefashionpeople.com"})
    pid = proj.get("project_id")
    print(f"Project: {pid} ({time.time()-t0:.0f}s)")
    await call_tool("confirm_offer", {"project_id": pid, "approved": True})

    # Preview
    preview = await call_tool("tam_gather", {
        "project_id": pid, "source_type": "apollo.companies.api",
        "query": "Fashion brands in Italy",
        "filters": {"target_count": 100, "organization_locations": ["Italy"]},
    })
    strategy = preview.get("filters_preview", {}).get("filter_strategy", "?")
    print(f"Strategy: {strategy} ({time.time()-t0:.0f}s)")

    # Confirm + gather
    filters = preview.get("next_action", {}).get("args", {}).get("filters", {})
    t_gather = time.time()
    gather = await call_tool("tam_gather", {
        "project_id": pid, "source_type": "apollo.companies.api",
        "query": "Fashion brands in Italy", "confirm_filters": True, "filters": filters,
    })
    run_id = gather.get("run_id")
    print(f"Run: {run_id}, {gather.get('new_companies')} companies ({time.time()-t_gather:.0f}s)")

    if not run_id:
        print(f"FAIL: {gather}")
        return

    # Run auto pipeline (streaming)
    t_pipeline = time.time()
    result = await call_tool("run_auto_pipeline", {
        "run_id": run_id, "target_people": 100, "max_people_per_company": 3, "confirm": True,
    })
    pipeline_time = time.time() - t_pipeline
    total_time = time.time() - t0

    print(f"\n{'='*60}")
    print(f"RESULT:")
    print(f"  Status: {result.get('status')}")
    print(f"  People: {result.get('total_people', result.get('people_found', '?'))}")
    print(f"  Targets: {result.get('total_targets', '?')}")
    print(f"  Companies: {result.get('total_companies', '?')}")
    print(f"  Credits: {result.get('credits_used', '?')}")
    print(f"  Pipeline time: {pipeline_time:.0f}s")
    print(f"  Total time: {total_time:.0f}s")
    print(f"  KPI met: {result.get('kpi_met', '?')}")
    print(f"  Message: {result.get('message', '')[:200]}")

    # Save
    with open("/app/tests/tmp/e2e_v5_streaming.json", "w") as f:
        json.dump({"result": result, "pipeline_time": pipeline_time, "total_time": total_time}, f, indent=2)

asyncio.run(main())
