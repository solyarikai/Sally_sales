"""Test: Which keyword strategy gives the HIGHEST TARGET RATE in scraped results?

Strategies:
1. Specific keywords only ("IT consulting")
2. Industry names only ("information technology & services")
3. Mixed (both together)
4. Specific keywords + size filter
5. Industry name + specific keyword (narrow combination test)

For each: search Apollo → scrape top 15 → classify → measure target rate.
THIS is what matters — not how many results Apollo returns, but how many of the
scraped companies are actual targets.

Run:
    cd mcp && python3 tests/test_keyword_strategies.py
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
APOLLO_KEY = os.environ.get("APOLLO_API_KEY", "")
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")
TMP_DIR = Path(__file__).parent / "tmp"


async def apollo_search(kw_tags, locations, size_ranges=None):
    body = {"per_page": 25, "page": 1, "q_organization_keyword_tags": kw_tags}
    if locations:
        body["organization_locations"] = locations
    if size_ranges:
        body["organization_num_employees_ranges"] = size_ranges
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.apollo.io/api/v1/mixed_companies/search",
            headers={"X-Api-Key": APOLLO_KEY, "Content-Type": "application/json"},
            json=body,
        )
        data = resp.json()
        companies = data.get("accounts") or data.get("organizations") or []
        total = data.get("pagination", {}).get("total_entries", 0)
        return companies, total


async def scrape_and_classify(companies, query, offer):
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
        return 0, 0, [], []

    targets = await _classify_targets(scraped, query, offer, OPENAI_KEY)
    target_domains = []
    for t in targets:
        d = t.get("domain", t.get("primary_domain", ""))
        if not d and "classification" in t:
            d = t["classification"].get("domain", "")
        target_domains.append(d)

    return len(scraped), len(targets), target_domains, [
        c.get("primary_domain", c.get("domain", "")) for c in scraped
    ]


SEGMENTS = [
    {
        "name": "EasyStaff IT consulting Miami",
        "query": "IT consulting companies in Miami",
        "offer": "EasyStaff — payroll and contractor management platform",
        "location": ["Miami, Florida, United States"],
        "size": ["11,50", "51,200"],
        "strategies": {
            "specific_only": ["IT consulting"],
            "specific_broad": ["IT consulting", "technology consulting", "IT services"],
            "industry_only": ["information technology & services"],
            "industry_2": ["information technology & services", "management consulting"],
            "mixed_industry_plus_specific": ["information technology & services", "IT consulting"],
            "mixed_all": ["information technology & services", "management consulting", "IT consulting", "technology consulting"],
        },
    },
    {
        "name": "TFP Fashion Italy",
        "query": "Fashion brands in Italy",
        "offer": "The Fashion People — branded resale platform for fashion brands",
        "location": ["Italy"],
        "size": ["51,200", "201,500"],
        "strategies": {
            "specific_only": ["fashion brands"],
            "specific_broad": ["fashion brands", "fashion", "clothing brands"],
            "industry_only": ["apparel & fashion"],
            "industry_2": ["apparel & fashion", "luxury goods & jewelry"],
            "mixed_industry_plus_specific": ["apparel & fashion", "fashion brands"],
            "mixed_all": ["apparel & fashion", "luxury goods & jewelry", "fashion brands", "clothing"],
        },
    },
    {
        "name": "OnSocial Creator UK",
        "query": "Influencer marketing platforms and creator economy companies in UK",
        "offer": "OnSocial — AI-powered creator data and analytics for influencer marketing",
        "location": ["United Kingdom"],
        "size": ["11,50", "51,200"],
        "strategies": {
            "specific_only": ["influencer marketing"],
            "specific_broad": ["influencer marketing", "creator economy", "creator platform"],
            "industry_only": ["marketing & advertising"],
            "industry_2": ["marketing & advertising", "internet"],
            "mixed_industry_plus_specific": ["marketing & advertising", "influencer marketing"],
            "mixed_all": ["marketing & advertising", "internet", "influencer marketing", "creator economy"],
        },
    },
]


async def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    lines = []
    all_results = []

    def log(msg):
        print(msg)
        lines.append(msg)

    log(f"KEYWORD STRATEGY TEST — {ts}")
    log("Which keyword approach gives highest target rate in scraped results?")
    log("=" * 100)

    for seg in SEGMENTS:
        log(f"\n{'='*80}")
        log(f"  {seg['name']}")
        log(f"  Query: {seg['query']}")
        log(f"{'='*80}")

        seg_results = []

        for strat_name, keywords in seg["strategies"].items():
            log(f"\n  --- {strat_name}: {keywords} ---")

            t0 = time.time()
            companies, total = await apollo_search(keywords, seg["location"], seg["size"])
            search_time = time.time() - t0

            log(f"  Apollo: {total} total, {len(companies)} returned ({search_time:.1f}s)")

            if not companies:
                log(f"  SKIP — 0 results")
                seg_results.append({
                    "strategy": strat_name, "keywords": keywords,
                    "total": 0, "scraped": 0, "targets": 0, "rate": 0,
                })
                continue

            # Show first 5 companies
            for c in companies[:5]:
                log(f"    {c.get('name','?')[:30]} ({c.get('primary_domain','?')})")

            t0 = time.time()
            scraped, targets, target_domains, all_domains = await scrape_and_classify(
                companies, seg["query"], seg["offer"]
            )
            classify_time = time.time() - t0

            rate = targets / scraped * 100 if scraped else 0
            est_total_targets = int(total * rate / 100) if rate > 0 else 0

            log(f"  Scraped: {scraped}, Targets: {targets}/{scraped} ({rate:.0f}%) [{classify_time:.1f}s]")
            log(f"  Target domains: {target_domains}")
            log(f"  Est. total targets in Apollo: ~{est_total_targets}")

            seg_results.append({
                "strategy": strat_name, "keywords": keywords,
                "total": total, "scraped": scraped, "targets": targets,
                "rate": rate, "est_targets": est_total_targets,
                "target_domains": target_domains, "all_domains": all_domains,
            })

            await asyncio.sleep(0.5)

        # Segment summary
        log(f"\n  {'Strategy':<35} {'Apollo':>8} {'Scraped':>8} {'Targets':>8} {'Rate':>6} {'Est.':>8}")
        log(f"  {'-'*80}")
        best = max(seg_results, key=lambda x: x["rate"]) if seg_results else None
        for r in seg_results:
            marker = " ★" if r == best else ""
            log(f"  {r['strategy']:<35} {r['total']:>8} {r['scraped']:>8} {r['targets']:>8} {r['rate']:>5.0f}% {r.get('est_targets',0):>8}{marker}")

        all_results.append({"segment": seg["name"], "results": seg_results})

    # Overall summary
    log(f"\n{'='*100}")
    log("OVERALL BEST STRATEGY PER SEGMENT")
    log(f"{'='*100}")
    for seg_r in all_results:
        valid = [r for r in seg_r["results"] if r["scraped"] > 0]
        if valid:
            best = max(valid, key=lambda x: x["rate"])
            log(f"  {seg_r['segment']}: {best['strategy']} ({best['rate']:.0f}% target rate, {best['total']} available)")
        else:
            log(f"  {seg_r['segment']}: NO RESULTS")

    # Save
    log_file = TMP_DIR / f"{ts}_keyword_strategies.log"
    log_file.write_text("\n".join(lines))
    results_file = TMP_DIR / f"{ts}_keyword_strategies.json"
    results_file.write_text(json.dumps({"ts": ts, "results": all_results}, indent=2, default=str))
    log(f"\nSaved: {log_file.name}, {results_file.name}")


if __name__ == "__main__":
    asyncio.run(main())
