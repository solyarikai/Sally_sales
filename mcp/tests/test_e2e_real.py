"""THE REAL E2E TEST — per suck.md rules.

NO hardcoded filters. NO isolated GPT checks. NO format validation.
The ONLY metric: target companies found through the real pipeline.

Flow: user query → filter_mapper → Apollo API → scrape → classify → count targets.
Tests multiple models for the GPT filter mapper step.
Logs EVERYTHING to files.

Run:
    cd mcp && python3 tests/test_e2e_real.py
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

SEGMENTS = [
    {
        "name": "EasyStaff IT consulting Miami",
        "query": "IT consulting companies in Miami",
        "offer": "EasyStaff — global platform for payroll, freelance payments, and invoice management. Helps companies hire and pay contractors worldwide.",
    },
    {
        "name": "TFP Fashion brands Italy",
        "query": "Fashion brands in Italy",
        "offer": "The Fashion People — branded resale platform that turns old stock, returns and pre-owned into revenue for fashion brands. 20+ EU countries.",
    },
    {
        "name": "OnSocial Creator platforms UK",
        "query": "Influencer marketing platforms and creator economy companies in UK",
        "offer": "OnSocial — AI-powered creator data solution. Creator Discovery, Creator Analytics, Social Data API. For agencies, platforms, brands doing influencer marketing.",
    },
]

MODELS_TO_TEST = ["gpt-4.1-mini", "gpt-4.1-nano", "gpt-4o-mini"]


async def apollo_search(filters: dict) -> dict:
    """Real Apollo API call."""
    body = {"per_page": 25, "page": 1}
    for k in ["q_organization_keyword_tags", "organization_locations", "organization_num_employees_ranges"]:
        if filters.get(k):
            body[k] = filters[k]

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


async def scrape_and_classify(companies, query, offer):
    """Real scraping + classification."""
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
        return {"scraped": 0, "targets": 0, "rate": 0, "domains": [], "all_scraped": []}

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
        "rate": len(targets) / len(scraped) * 100 if scraped else 0,
        "domains": target_domains,
        "all_scraped": [c.get("primary_domain", c.get("domain", "")) for c in scraped],
    }


async def run_enrichment_feedback(companies, segment_name, openai_key):
    """Enrich top companies and feed keywords back to taxonomy."""
    from app.services.taxonomy_service import taxonomy_service

    new_kw_total = 0
    for c in companies[:5]:
        domain = c.get("primary_domain") or c.get("domain", "")
        if not domain:
            continue
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    "https://api.apollo.io/api/v1/organizations/enrich",
                    headers={"X-Api-Key": APOLLO_KEY},
                    params={"domain": domain},
                )
                data = resp.json()
                org = data.get("organization", {})
                if org:
                    new_kw = taxonomy_service.add_from_enrichment(org, segment_name)
                    new_kw_total += new_kw
        except Exception as e:
            logger.warning(f"Enrichment failed for {domain}: {e}")

    return new_kw_total


import logging
logger = logging.getLogger(__name__)


async def main():
    from app.services.filter_mapper import map_query_to_filters
    from app.services.taxonomy_service import taxonomy_service

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    lines = []
    all_results = []

    def log(msg):
        print(msg)
        lines.append(msg)

    log("=" * 100)
    log(f"E2E REAL EXPLORATION TEST — {ts}")
    log(f"Per suck.md: no hardcoded filters, real Apollo, real scraping, real classification")
    log(f"Models: {MODELS_TO_TEST}")
    log(f"Segments: {[s['name'] for s in SEGMENTS]}")
    log("=" * 100)

    # Show taxonomy state
    stats = taxonomy_service.stats()
    log(f"\nTaxonomy state: {json.dumps(stats)}")

    for model in MODELS_TO_TEST:
        log(f"\n{'#'*100}")
        log(f"  MODEL: {model}")
        log(f"{'#'*100}")

        model_results = {"model": model, "segments": []}

        for seg in SEGMENTS:
            log(f"\n{'='*70}")
            log(f"  {seg['name']} | model={model}")
            log(f"{'='*70}")

            # Step 1: Filter mapping (THE STEP WE'RE TESTING)
            log(f"\n  STEP 1: map_query_to_filters()")
            t0 = time.time()
            filters = await map_query_to_filters(
                query=seg["query"],
                offer=seg["offer"],
                openai_key=OPENAI_KEY,
                model=model,
            )
            elapsed = time.time() - t0

            details = filters.get("mapping_details", {})
            log(f"  Time: {elapsed:.1f}s")
            log(f"  Industries: {details.get('industries_selected', [])}")
            log(f"  Keywords (verified): {details.get('keywords_selected', [])}")
            log(f"  Keywords (unverified): {details.get('unverified_keywords', [])}")
            log(f"  Employee ranges: {details.get('employee_ranges', [])}")
            log(f"  Locations: {details.get('locations', [])}")
            log(f"  Keyword map size: {details.get('keyword_map_size', 0)}")

            # Show EXACT filters sent to Apollo
            apollo_filters = {
                "q_organization_keyword_tags": filters["q_organization_keyword_tags"],
                "organization_locations": filters["organization_locations"],
                "organization_num_employees_ranges": filters["organization_num_employees_ranges"],
            }
            log(f"\n  FILTERS SENT TO APOLLO:")
            log(f"  {json.dumps(apollo_filters, indent=4)}")

            # Step 2: Apollo search
            log(f"\n  STEP 2: Apollo search")
            t0 = time.time()
            search = await apollo_search(apollo_filters)
            elapsed = time.time() - t0
            log(f"  Total available: {search['total']}")
            log(f"  Returned: {len(search['companies'])} ({elapsed:.1f}s)")

            if not search["companies"]:
                log(f"  ❌ 0 RESULTS — filters too narrow or invalid")
                model_results["segments"].append({
                    "segment": seg["name"], "filters": apollo_filters,
                    "total": 0, "scraped": 0, "targets": 0, "rate": 0,
                })
                continue

            for c in search["companies"][:5]:
                log(f"    {c.get('name', '?')[:35]} ({c.get('primary_domain', '?')})")

            # Step 3: Scrape + classify
            log(f"\n  STEP 3: Scrape + Classify")
            t0 = time.time()
            cls = await scrape_and_classify(search["companies"], seg["query"], seg["offer"])
            elapsed = time.time() - t0

            icon = "✅" if cls["rate"] >= 50 else "⚠️" if cls["rate"] >= 20 else "❌"
            log(f"  {icon} Scraped: {cls['scraped']}, Targets: {cls['targets']}/{cls['scraped']} ({cls['rate']:.0f}%)")
            log(f"  Target domains: {cls['domains']}")
            log(f"  All scraped: {cls['all_scraped']}")
            log(f"  Time: {elapsed:.1f}s")

            est_total = int(search["total"] * cls["rate"] / 100) if cls["rate"] > 0 else 0
            log(f"  Estimated total targets in Apollo: ~{est_total}")

            model_results["segments"].append({
                "segment": seg["name"],
                "filters": apollo_filters,
                "mapping_details": details,
                "total_available": search["total"],
                "scraped": cls["scraped"],
                "targets": cls["targets"],
                "rate": cls["rate"],
                "target_domains": cls["domains"],
                "est_total_targets": est_total,
            })

            await asyncio.sleep(1)

        all_results.append(model_results)

    # ── Enrichment feedback (learn from results) ──
    log(f"\n{'='*100}")
    log("ENRICHMENT FEEDBACK — teaching taxonomy from best results")
    log(f"{'='*100}")

    # Pick best model's results for enrichment
    best_model = max(all_results, key=lambda m: sum(s.get("targets", 0) for s in m["segments"]))
    log(f"Best model: {best_model['model']}")

    for seg_result in best_model["segments"]:
        if seg_result.get("targets", 0) > 0:
            # Re-search to get companies for enrichment
            search = await apollo_search(seg_result["filters"])
            if search["companies"]:
                # Only enrich targets (scrape+classify first)
                cls = await scrape_and_classify(search["companies"], seg_result["segment"], "")
                target_companies = [c for c in search["companies"]
                                   if c.get("primary_domain", "") in cls.get("domains", [])]
                if target_companies:
                    new_kw = await run_enrichment_feedback(
                        target_companies, seg_result["segment"], OPENAI_KEY
                    )
                    log(f"  {seg_result['segment']}: +{new_kw} new keywords from enrichment")

    stats_after = taxonomy_service.stats()
    log(f"\nTaxonomy after: {json.dumps(stats_after)}")

    # ── Summary ──
    log(f"\n{'='*100}")
    log("SUMMARY")
    log(f"{'='*100}")
    log(f"{'Model':<20} {'Segment':<35} {'Apollo':>8} {'Scraped':>8} {'Targets':>8} {'Rate':>6} {'Est.':>8}")
    log("-" * 95)

    for mr in all_results:
        for sr in mr["segments"]:
            log(f"{mr['model']:<20} {sr['segment']:<35} {sr.get('total_available',0):>8} "
                f"{sr.get('scraped',0):>8} {sr.get('targets',0):>8} "
                f"{sr.get('rate',0):>5.0f}% {sr.get('est_total_targets',0):>8}")

    # Best model per segment
    log(f"\nBEST MODEL PER SEGMENT:")
    for seg in SEGMENTS:
        best = None
        best_targets = -1
        for mr in all_results:
            for sr in mr["segments"]:
                if sr["segment"] == seg["name"] and sr.get("targets", 0) > best_targets:
                    best_targets = sr["targets"]
                    best = mr["model"]
        log(f"  {seg['name']}: {best} ({best_targets} targets)")

    # Overall best
    model_totals = {}
    for mr in all_results:
        total = sum(sr.get("targets", 0) for sr in mr["segments"])
        model_totals[mr["model"]] = total
    best_overall = max(model_totals, key=model_totals.get)
    log(f"\nOVERALL BEST: {best_overall} ({model_totals[best_overall]} total targets)")

    # Save everything
    log_file = TMP_DIR / f"{ts}_e2e_real.log"
    log_file.write_text("\n".join(lines))
    results_file = TMP_DIR / f"{ts}_e2e_real.json"
    results_file.write_text(json.dumps({
        "ts": ts, "models": MODELS_TO_TEST,
        "results": all_results,
        "taxonomy_before": stats,
        "taxonomy_after": stats_after,
        "best_model": best_overall,
    }, indent=2, default=str))
    log(f"\nSaved: {log_file.name}, {results_file.name}")


if __name__ == "__main__":
    if not APOLLO_KEY or not OPENAI_KEY:
        print("ERROR: need APOLLO_API_KEY and OPENAI_API_KEY in mcp/.env")
        sys.exit(1)
    asyncio.run(main())
