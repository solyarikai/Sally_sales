"""E2E v4 — simplified pipeline (no exploration), all 6 segments, fresh projects.
Run: docker exec mcp-backend python /app/e2e_v4_simplified.py
"""
import asyncio, httpx, sys, json, time, os
from datetime import datetime
sys.path.insert(0, "/app")

TS = datetime.now().strftime("%Y%m%d_%H%M%S")
TMP = "/app/tests/tmp"
os.makedirs(TMP, exist_ok=True)

TOKEN = "mcp_c3234bd4d160e4ea7502567a93702e43bc1ad71e28d7b6cf4e8bf02431521566"
API = "http://localhost:8000"


async def call_tool(name, args):
    async with httpx.AsyncClient(timeout=600) as c:
        resp = await c.post(f"{API}/api/tools/call",
            headers={"Content-Type": "application/json", "X-MCP-Token": TOKEN},
            json={"name": name, "arguments": args})
        return resp.json().get("result", resp.json())


async def run_segment(seg_name, website, query, location):
    print(f"\n{'='*60}")
    print(f"{seg_name}: {query}")
    print(f"{'='*60}")
    t0 = time.time()

    # Create FRESH project
    proj = await call_tool("create_project", {"name": f"v4 {seg_name}", "website": website})
    pid = proj.get("project_id")
    if not pid:
        print(f"  FAIL: {proj.get('message', str(proj)[:100])}")
        return None
    await call_tool("confirm_offer", {"project_id": pid, "approved": True})
    print(f"  Project {pid} created")

    # Preview
    preview = await call_tool("tam_gather", {
        "project_id": pid, "source_type": "apollo.companies.api", "query": query,
        "filters": {"target_count": 100, "organization_locations": [location]},
    })
    strategy = preview.get("filters_preview", {}).get("filter_strategy", "?")
    print(f"  Strategy: {strategy}")

    # Confirm
    filters = preview.get("next_action", {}).get("args", {}).get("filters", {})
    if not filters:
        print(f"  FAIL: no filters")
        return None

    t_gather = time.time()
    gather = await call_tool("tam_gather", {
        "project_id": pid, "source_type": "apollo.companies.api", "query": query,
        "confirm_filters": True, "filters": filters,
    })
    run_id = gather.get("run_id")
    companies = gather.get("new_companies", 0)
    credits_gather = gather.get("credits_spent", 0)
    print(f"  Gathered: {companies} companies, {credits_gather} credits, {time.time()-t_gather:.0f}s")

    if not run_id:
        return None

    # Blacklist + approve
    bl = await call_tool("tam_blacklist_check", {"run_id": run_id})
    if bl.get("gate_id"):
        await call_tool("tam_approve_checkpoint", {"gate_id": bl["gate_id"]})

    # Pre-filter
    await call_tool("tam_pre_filter", {"run_id": run_id})

    # Scrape
    t_scrape = time.time()
    scrape = await call_tool("tam_scrape", {"run_id": run_id})
    scraped = scrape.get("scraped", 0)
    print(f"  Scraped: {scraped} in {time.time()-t_scrape:.0f}s")

    # Classify
    t_class = time.time()
    analyze = await call_tool("tam_analyze", {"run_id": run_id})
    targets = analyze.get("targets_found", 0)
    total_analyzed = analyze.get("total_analyzed", 0)
    rate = analyze.get("target_rate", "0%")
    print(f"  Targets: {targets}/{total_analyzed} ({rate}) in {time.time()-t_class:.0f}s")

    # Extract people
    t_people = time.time()
    people = await call_tool("extract_people", {"run_id": run_id})
    people_found = people.get("people_found", 0)
    print(f"  People: {people_found} in {time.time()-t_people:.0f}s")

    total = time.time() - t0
    kpi = people_found >= 100
    print(f"  TOTAL: {total:.0f}s, KPI: {'YES' if kpi else 'NO'} ({people_found}/100)")

    return {
        "segment": seg_name, "query": query, "strategy": strategy, "run_id": run_id,
        "companies": companies, "scraped": scraped, "analyzed": total_analyzed,
        "targets": targets, "rate": rate, "people": people_found,
        "credits": credits_gather, "time": round(total, 1), "kpi": kpi,
    }


async def main():
    print(f"E2E v4 — SIMPLIFIED PIPELINE — {TS}\n")

    segments = [
        ("TFP_Fashion", "https://thefashionpeople.com", "Fashion brands in Italy", "Italy"),
        ("ES_IT_Miami", "https://easystaff.io", "IT consulting companies in Miami", "Miami, Florida, United States"),
        ("ES_Video_London", "https://easystaff.io", "Video production companies in London", "London, England, United Kingdom"),
        ("ES_IT_US", "https://easystaff.io", "IT consulting companies in United States", "United States"),
        ("ES_Video_UK", "https://easystaff.io", "Video production companies in United Kingdom", "United Kingdom"),
        ("OnSocial_UK", "https://onsocial.ai", "Social media influencer agencies in United Kingdom", "United Kingdom"),
    ]

    results = {}
    for name, website, query, location in segments:
        r = await run_segment(name, website, query, location)
        if r:
            results[name] = r

    # Summary
    print(f"\n{'='*80}")
    print("FINAL SUMMARY — SIMPLIFIED PIPELINE v4")
    print(f"{'='*80}")
    print(f"{'Segment':<20} {'Strategy':<15} {'Comp':>6} {'Targ':>6} {'Rate':>6} {'People':>7} {'Time':>6} {'Cr':>4} {'KPI':>5}")
    print("-" * 85)
    for n, r in results.items():
        print(f"{n:<20} {r['strategy']:<15} {r['companies']:>6} {r['targets']:>6} {r['rate']:>6} {r['people']:>7} {r['time']:>5}s {r['credits']:>4} {'YES' if r['kpi'] else 'NO':>5}")

    outfile = f"{TMP}/e2e_v4_{TS}.json"
    with open(outfile, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved: {outfile}")

asyncio.run(main())
