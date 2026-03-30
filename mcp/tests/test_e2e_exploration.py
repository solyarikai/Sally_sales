"""THE REAL TEST: user prompt → intent parser → Apollo API → scrape → classify → target rate.

No hardcoded filters. No isolated components. The full pipeline.
For each segment: parse intent → build filters → search Apollo → scrape → classify → score.

Tests different filter strategies:
1. Keywords only (current)
2. Keywords + industries (if Apollo supports it)
3. Different keyword sets from intent parser

Run:
    cd mcp && python3 tests/test_e2e_exploration.py
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime

import httpx

_env = Path(__file__).parent.parent / ".env"
if _env.exists():
    for line in _env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip()
            if v and len(v) > 3:
                os.environ.setdefault(k, v)

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")
APOLLO_KEY = os.environ.get("APOLLO_API_KEY", "")
TMP_DIR = Path(__file__).parent / "tmp"

SEGMENTS = [
    {
        "name": "EasyStaff IT consulting Miami",
        "query": "IT consulting companies in Miami",
        "offer": "EasyStaff — global platform for payroll, freelance payments, and invoice management",
        "size_range": ["11,50", "51,200"],
    },
    {
        "name": "TFP Fashion brands Italy",
        "query": "Fashion brands in Italy",
        "offer": "The Fashion People — branded resale platform for fashion brands",
        "size_range": ["51,200", "201,500"],
    },
    {
        "name": "OnSocial Creator platforms UK",
        "query": "Influencer marketing platforms and creator economy companies in UK",
        "offer": "OnSocial — AI-powered creator data solution for influencer marketing: discovery, analytics, social data API",
        "size_range": ["11,50", "51,200"],
    },
]


async def search_apollo(filters: dict) -> dict:
    """Call Apollo API with given filters. Returns companies + total count."""
    body = {
        "per_page": 25,
        "page": 1,
    }
    if filters.get("q_organization_keyword_tags"):
        body["q_organization_keyword_tags"] = filters["q_organization_keyword_tags"]
    if filters.get("organization_locations"):
        body["organization_locations"] = filters["organization_locations"]
    if filters.get("organization_num_employees_ranges"):
        body["organization_num_employees_ranges"] = filters["organization_num_employees_ranges"]
    # NEW: try industry filter if available
    if filters.get("organization_industry_tag_ids"):
        body["organization_industry_tag_ids"] = filters["organization_industry_tag_ids"]

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.apollo.io/api/v1/mixed_companies/search",
            headers={"X-Api-Key": APOLLO_KEY, "Content-Type": "application/json"},
            json=body,
        )
        data = resp.json()
        companies = data.get("accounts") or data.get("organizations") or []
        total = data.get("pagination", {}).get("total_entries", 0)
        return {"companies": companies, "total": total}


async def scrape_and_classify(companies: list, query: str, offer: str) -> dict:
    """Scrape websites + classify targets. Returns stats."""
    from app.services.scraper_service import ScraperService
    from app.services.exploration_service import _classify_targets

    scraper = ScraperService()
    scraped = []
    for c in companies[:15]:
        domain = c.get("primary_domain") or c.get("domain", "")
        if not domain:
            continue
        result = await scraper.scrape_website(domain, timeout=10)
        if result.get("success") and result.get("text"):
            scraped.append({**c, "scraped_text": result["text"][:3000]})

    if not scraped:
        return {"scraped": 0, "targets": 0, "target_rate": 0, "target_domains": []}

    targets = await _classify_targets(scraped, query, offer, OPENAI_KEY)
    target_domains = []
    for t in targets:
        d = t.get("domain", t.get("primary_domain", ""))
        if not d and "classification" in t:
            d = t["classification"].get("domain", "")
        target_domains.append(d)

    return {
        "scraped": len(scraped),
        "targets": len(targets),
        "target_rate": len(targets) / len(scraped) * 100 if scraped else 0,
        "target_domains": target_domains,
    }


async def main():
    from app.services.intent_parser import parse_gathering_intent

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    lines = []

    def log(msg):
        print(msg)
        lines.append(msg)

    log("=" * 90)
    log(f"E2E EXPLORATION TEST — {ts}")
    log("user prompt → intent parser → Apollo filters → Apollo API → scrape → classify")
    log("=" * 90)

    all_results = []

    for seg in SEGMENTS:
        log(f"\n{'='*70}")
        log(f"  SEGMENT: {seg['name']}")
        log(f"  Query: {seg['query']}")
        log(f"  Offer: {seg['offer'][:60]}...")
        log(f"{'='*70}")

        # Step 1: Intent parser generates filters
        log("\n  STEP 1: Intent Parser")
        t0 = time.time()
        parsed = await parse_gathering_intent(seg["query"], seg["offer"], OPENAI_KEY)
        elapsed = time.time() - t0
        log(f"  Time: {elapsed:.1f}s")

        if not parsed or not parsed.get("segments"):
            log(f"  FAIL: no segments returned")
            continue

        pseg = parsed["segments"][0]
        keywords = pseg.get("apollo_keywords", [])
        industries = pseg.get("apollo_industries", [])
        geo = pseg.get("geo", "") or pseg.get("country", "")
        log(f"  Keywords: {keywords}")
        log(f"  Industries: {industries}")
        log(f"  Geo: {geo}")

        # Step 2: Build Apollo filters from intent parser output
        # Strategy A: keywords only (what currently happens)
        filters_a = {
            "q_organization_keyword_tags": keywords,
            "organization_locations": [geo] if geo else [],
            "organization_num_employees_ranges": seg["size_range"],
        }

        # Strategy B: keywords + industries as keywords (industries added to keyword tags)
        filters_b = {
            "q_organization_keyword_tags": keywords + industries,
            "organization_locations": [geo] if geo else [],
            "organization_num_employees_ranges": seg["size_range"],
        }

        # Strategy C: industries only as keywords
        filters_c = {
            "q_organization_keyword_tags": industries,
            "organization_locations": [geo] if geo else [],
            "organization_num_employees_ranges": seg["size_range"],
        }

        strategies = [
            ("A: keywords only", filters_a),
            ("B: keywords + industries", filters_b),
            ("C: industries only", filters_c),
        ]

        seg_results = {"segment": seg["name"], "strategies": []}

        for strat_name, filters in strategies:
            log(f"\n  STEP 2-3: Apollo search — {strat_name}")
            log(f"  Filters: {json.dumps(filters, indent=4)}")

            t0 = time.time()
            search = await search_apollo(filters)
            elapsed = time.time() - t0

            companies = search["companies"]
            total = search["total"]
            log(f"  Results: {len(companies)} returned, {total} total available ({elapsed:.1f}s)")

            if not companies:
                log(f"  NO COMPANIES — filters too narrow")
                seg_results["strategies"].append({
                    "name": strat_name, "filters": filters,
                    "total_available": 0, "returned": 0,
                })
                continue

            for c in companies[:5]:
                name = c.get("name", "?")
                domain = c.get("primary_domain", "?")
                industry = c.get("industry", "?")
                emp = c.get("estimated_num_employees", "?")
                log(f"    {name} ({domain}) — {industry}, {emp} emp")

            # Step 4: Scrape + classify
            log(f"\n  STEP 4-5: Scrape + Classify")
            t0 = time.time()
            cls_result = await scrape_and_classify(companies, seg["query"], seg["offer"])
            elapsed = time.time() - t0

            log(f"  Scraped: {cls_result['scraped']}/{min(15, len(companies))}")
            log(f"  Targets: {cls_result['targets']}/{cls_result['scraped']} ({cls_result['target_rate']:.0f}%)")
            log(f"  Target domains: {cls_result['target_domains']}")
            log(f"  Time: {elapsed:.1f}s")
            log(f"  Total available × target rate = ~{int(total * cls_result['target_rate'] / 100)} estimated targets in Apollo")

            seg_results["strategies"].append({
                "name": strat_name,
                "filters": filters,
                "total_available": total,
                "returned": len(companies),
                "scraped": cls_result["scraped"],
                "targets": cls_result["targets"],
                "target_rate": cls_result["target_rate"],
                "target_domains": cls_result["target_domains"],
                "estimated_total_targets": int(total * cls_result["target_rate"] / 100),
            })

        all_results.append(seg_results)

    # Summary
    log(f"\n{'='*90}")
    log("SUMMARY")
    log(f"{'='*90}")
    log(f"{'Segment':<35} {'Strategy':<25} {'Apollo':>8} {'Scraped':>8} {'Targets':>8} {'Rate':>6} {'Est.Total':>10}")
    log("-" * 105)

    for seg_r in all_results:
        for s in seg_r["strategies"]:
            log(f"{seg_r['segment']:<35} {s['name']:<25} {s.get('total_available',0):>8} {s.get('scraped',0):>8} {s.get('targets',0):>8} {s.get('target_rate',0):>5.0f}% {s.get('estimated_total_targets',0):>10}")

    # Save
    log_file = TMP_DIR / f"{ts}_e2e_exploration.log"
    log_file.write_text("\n".join(lines))
    results_file = TMP_DIR / f"{ts}_e2e_exploration.json"
    results_file.write_text(json.dumps({"ts": ts, "results": all_results}, indent=2, default=str))
    log(f"\nSaved: {log_file.name}, {results_file.name}")


if __name__ == "__main__":
    if not APOLLO_KEY or not OPENAI_KEY:
        print("ERROR: need APOLLO_API_KEY and OPENAI_API_KEY")
        sys.exit(1)
    asyncio.run(main())
