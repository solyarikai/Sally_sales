"""End-to-end pipeline test for all 6 segments via MCP tools API.
Tests the REAL pipeline: tam_gather → scrape → classify → extract people.
Measures: time, credits, companies found, targets, people extracted.

Run: docker exec mcp-backend python /app/e2e_pipeline_all_segments.py
"""
import asyncio, httpx, sys, json, time, os
from datetime import datetime
sys.path.insert(0, "/app")

TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
TMP = "/app/tests/tmp"
os.makedirs(TMP, exist_ok=True)

TOKEN = "mcp_c3234bd4d160e4ea7502567a93702e43bc1ad71e28d7b6cf4e8bf02431521566"
API_BASE = "http://localhost:8000"

SEGMENTS = [
    {"query": "Fashion brands in Italy", "project_id": 393},
    # Need to create projects for other segments first
]


async def call_tool(tool_name, arguments):
    """Call MCP tool via REST API."""
    async with httpx.AsyncClient(timeout=120) as c:
        resp = await c.post(f"{API_BASE}/api/tools/call",
            headers={"Content-Type": "application/json", "X-MCP-Token": TOKEN},
            json={"name": tool_name, "arguments": arguments})
        return resp.json().get("result", resp.json())


async def create_project(name, website, offer):
    """Create project + confirm offer."""
    result = await call_tool("create_project", {"name": name, "website": website})
    project_id = result.get("project_id")
    if not project_id:
        print(f"  Failed to create project: {result}")
        return None

    # Confirm offer
    await call_tool("confirm_offer", {"project_id": project_id, "approved": True})
    print(f"  Project {name} created (id={project_id}), offer confirmed")
    return project_id


async def run_pipeline_for_segment(query, project_id, segment_id):
    """Run full gathering pipeline for one segment. Returns stats."""
    print(f"\n{'='*60}")
    print(f"E2E TEST: {query} (project={project_id})")
    print(f"{'='*60}")

    t_start = time.time()

    # Step 1: tam_gather (preview)
    print("  Step 1: Filter preview...")
    t1 = time.time()
    preview = await call_tool("tam_gather", {
        "project_id": project_id,
        "source_type": "apollo.companies.api",
        "query": query,
        "filters": {"target_count": 100, "organization_locations": [query.split(" in ")[-1].strip()]},
    })
    strategy = preview.get("filters_preview", {}).get("filter_strategy", "?")
    industry_ids = preview.get("filters_preview", {}).get("organization_industry_tag_ids")
    total_available = preview.get("total_available", 0)
    cost_est = preview.get("cost_estimate", {}).get("total_credits", 0)
    print(f"    Strategy: {strategy}, available: {total_available}, est cost: {cost_est} credits")
    print(f"    Industry IDs: {industry_ids}")
    t1_elapsed = time.time() - t1

    # Step 2: tam_gather (confirm)
    print("  Step 2: Gathering...")
    t2 = time.time()
    filters = preview.get("next_action", {}).get("args", {}).get("filters", {})
    if not filters:
        print("    SKIP — no filters in preview")
        return None

    gather = await call_tool("tam_gather", {
        "project_id": project_id,
        "source_type": "apollo.companies.api",
        "query": query,
        "confirm_filters": True,
        "filters": filters,
    })
    run_id = gather.get("run_id")
    companies = gather.get("new_companies", 0)
    credits = gather.get("credits_spent", 0)
    t2_elapsed = time.time() - t2
    print(f"    Run #{run_id}: {companies} companies, {credits} credits, {t2_elapsed:.1f}s")

    if not run_id:
        print("    FAILED — no run_id")
        return None

    # Step 3: Scrape + Classify (via tam_scrape + tam_analyze or blacklist→pre_filter→scrape→analyze)
    print("  Step 3: Blacklist check...")
    t3 = time.time()
    bl = await call_tool("tam_blacklist_check", {"run_id": run_id})
    gate_id = bl.get("gate_id")
    if gate_id:
        await call_tool("tam_approve_checkpoint", {"gate_id": gate_id})
    t3_elapsed = time.time() - t3
    print(f"    Blacklist done, {t3_elapsed:.1f}s")

    print("  Step 4: Pre-filter...")
    t4 = time.time()
    await call_tool("tam_pre_filter", {"run_id": run_id})
    t4_elapsed = time.time() - t4
    print(f"    Pre-filter done, {t4_elapsed:.1f}s")

    print("  Step 5: Scrape websites...")
    t5 = time.time()
    scrape = await call_tool("tam_scrape", {"run_id": run_id})
    scraped = scrape.get("scraped", 0)
    t5_elapsed = time.time() - t5
    print(f"    Scraped {scraped} websites, {t5_elapsed:.1f}s")

    print("  Step 6: GPT classification...")
    t6 = time.time()
    analyze = await call_tool("tam_analyze", {"run_id": run_id})
    targets = analyze.get("targets_found", 0)
    total_analyzed = analyze.get("total_analyzed", 0)
    target_rate = analyze.get("target_rate", "0%")
    t6_elapsed = time.time() - t6
    print(f"    Targets: {targets}/{total_analyzed} ({target_rate}), {t6_elapsed:.1f}s")

    # Step 7: Extract people
    print("  Step 7: Extract people...")
    t7 = time.time()
    people = await call_tool("extract_people", {"run_id": run_id})
    people_found = people.get("people_found", 0)
    t7_elapsed = time.time() - t7
    print(f"    People: {people_found}, {t7_elapsed:.1f}s")

    t_total = time.time() - t_start

    result = {
        "segment": query,
        "project_id": project_id,
        "run_id": run_id,
        "strategy": strategy,
        "industry_tag_ids": industry_ids,
        "total_available": total_available,
        "companies_gathered": companies,
        "companies_scraped": scraped,
        "companies_analyzed": total_analyzed,
        "targets_found": targets,
        "target_rate": target_rate,
        "people_found": people_found,
        "credits_apollo": credits,
        "cost_estimate": cost_est,
        "timing": {
            "filter_preview": round(t1_elapsed, 1),
            "gathering": round(t2_elapsed, 1),
            "blacklist": round(t3_elapsed, 1),
            "pre_filter": round(t4_elapsed, 1),
            "scraping": round(t5_elapsed, 1),
            "classification": round(t6_elapsed, 1),
            "people_extraction": round(t7_elapsed, 1),
            "total": round(t_total, 1),
        },
        "kpi_met": people_found >= 100,
    }

    print(f"\n  RESULT: {targets} targets, {people_found} people, {t_total:.0f}s total, {credits} credits")
    print(f"  KPI MET: {'YES' if people_found >= 100 else 'NO'}")
    return result


async def main():
    print(f"E2E PIPELINE TEST — {TIMESTAMP}")

    # Create projects for segments that don't have one
    projects = {
        "Fashion brands in Italy": 393,  # Already exists
    }

    # Create EasyStaff projects
    print("\nCreating projects...")
    es_id = await create_project("EasyStaff Test", "https://easystaff.io", "payroll for international hiring")
    if es_id:
        projects["IT consulting companies in Miami"] = es_id
        projects["Video production companies in London"] = es_id
        projects["IT consulting companies in US"] = es_id
        projects["Video production companies in UK"] = es_id

    os_id = await create_project("OnSocial Test", "https://onsocial.ai", "AI social media management")
    if os_id:
        projects["Social media influencer agencies in UK"] = os_id

    # Run pipeline for each segment
    all_results = {}
    for query, pid in projects.items():
        result = await run_pipeline_for_segment(query, pid, query.replace(" ", "_").lower())
        if result:
            all_results[query] = result

    # Summary
    print(f"\n{'='*80}")
    print("FINAL SUMMARY")
    print(f"{'='*80}")
    print(f"{'Segment':<40} {'Strategy':<15} {'Targets':>8} {'People':>8} {'Time':>8} {'Credits':>8} {'KPI':>5}")
    print("-" * 100)
    for query, r in all_results.items():
        print(f"{query:<40} {r['strategy']:<15} {r['targets_found']:>8} {r['people_found']:>8} {r['timing']['total']:>7}s {r['credits_apollo']:>8} {'YES' if r['kpi_met'] else 'NO':>5}")

    # Save
    outfile = f"{TMP}/e2e_results_{TIMESTAMP}.json"
    with open(outfile, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nSaved: {outfile}")

asyncio.run(main())
