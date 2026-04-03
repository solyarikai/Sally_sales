"""Run all Apollo search approaches across all segments.
Fetches 5 pages per approach, logs everything.
Run: docker exec mcp-backend python /app/run_approach_tests.py
"""
import asyncio, httpx, sys, json, time, os
from datetime import datetime
sys.path.insert(0, "/app")
from app.db import async_session_maker
from app.models.integration import MCPIntegrationSetting
from app.services.encryption import decrypt_value
from sqlalchemy import select

TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
TMP_DIR = "/app/tests/tmp"
os.makedirs(TMP_DIR, exist_ok=True)

# Known industry_tag_ids from enrichment
INDUSTRY_TAGS = {
    "fashion": "5567cd82736964540d0b0000",  # apparel & fashion (from Versace)
}


async def get_key(user_id=181):
    async with async_session_maker() as s:
        r = await s.execute(select(MCPIntegrationSetting).where(
            MCPIntegrationSetting.integration_name == "apollo",
            MCPIntegrationSetting.user_id == user_id))
        row = r.scalar_one_or_none()
        return decrypt_value(row.api_key_encrypted).strip() if row else None


async def apollo_search(key, params, pages=5):
    """Search Apollo, return all companies from N pages."""
    hdr = {"X-Api-Key": key, "Content-Type": "application/json"}
    url = "https://api.apollo.io/api/v1/mixed_companies/search"
    all_orgs = []
    domains_seen = set()
    page_counts = []
    t0 = time.time()

    for page in range(1, pages + 1):
        async with httpx.AsyncClient(timeout=30) as c:
            resp = await c.post(url, headers=hdr, json={**params, "page": page, "per_page": 100})
            d = resp.json()
            orgs = d.get("organizations", []) or d.get("accounts", [])
            total = d.get("pagination", {}).get("total_entries", 0)
            new = 0
            for o in orgs:
                dom = o.get("primary_domain") or (o.get("website_url") or "").replace("https://","").replace("http://","").split("/")[0]
                if dom and dom not in domains_seen:
                    domains_seen.add(dom)
                    all_orgs.append({
                        "name": o.get("name", "?"),
                        "domain": dom,
                        "industry": o.get("industry"),
                        "employees": o.get("estimated_num_employees"),
                        "description": (o.get("short_description") or "")[:150],
                    })
                    new += 1
            page_counts.append(len(orgs))
        await asyncio.sleep(0.35)

    elapsed = time.time() - t0
    return {
        "companies": all_orgs,
        "unique_count": len(all_orgs),
        "page_counts": page_counts,
        "pages_fetched": pages,
        "credits": pages,
        "elapsed_seconds": round(elapsed, 1),
        "apollo_total": total,
    }


# ── Segments ──
SEGMENTS = [
    {
        "id": "tfp_fashion_italy",
        "company": "TFP (thefashionpeople.com)",
        "offer": "Branded resale platform for fashion brands",
        "segment": "Fashion brands",
        "geo": "Italy",
        "location": ["Italy"],
        "size": ["1,10", "11,50", "51,200"],
        "industry_tag_id": "5567cd82736964540d0b0000",
        "keywords_specific": ["fashion design", "fashion brand", "leather goods", "italian fashion"],
        "keywords_broad": ["fashion", "apparel", "luxury"],
        "target_definition": "Fashion BRAND selling own products (clothing/shoes/bags). Has inventory. NOT: schools, consulting, textile suppliers, showrooms, retailers.",
    },
    {
        "id": "es_it_miami",
        "company": "EasyStaff (easystaff.io)",
        "offer": "Payroll and contractor payment for companies hiring internationally",
        "segment": "IT consulting",
        "geo": "Miami",
        "location": ["Miami, Florida, United States"],
        "size": ["11,50", "51,200"],
        "industry_tag_id": None,  # Need to discover via enrichment
        "keywords_specific": ["IT consulting", "software development", "managed IT services", "IT outsourcing"],
        "keywords_broad": ["information technology", "software", "consulting"],
        "target_definition": "IT consulting/services company (11-200 emp). NOT: product companies, SaaS, hardware, recruiters.",
    },
    {
        "id": "es_video_london",
        "company": "EasyStaff (easystaff.io)",
        "offer": "Payroll and contractor payment for companies hiring internationally",
        "segment": "Video production",
        "geo": "London",
        "location": ["London, England, United Kingdom"],
        "size": ["11,50", "51,200"],
        "industry_tag_id": None,
        "keywords_specific": ["video production", "film production", "content creation", "media production"],
        "keywords_broad": ["media", "film", "video"],
        "target_definition": "Video/film production company (11-200 emp). NOT: ad agencies, broadcasters, cinemas, freelancers.",
    },
    {
        "id": "es_it_us",
        "company": "EasyStaff (easystaff.io)",
        "offer": "Payroll and contractor payment",
        "segment": "IT consulting",
        "geo": "US (broad)",
        "location": ["United States"],
        "size": ["11,50", "51,200"],
        "industry_tag_id": None,
        "keywords_specific": ["IT consulting", "software development", "managed IT services"],
        "keywords_broad": ["information technology", "software"],
        "target_definition": "IT consulting/services company (11-200 emp). NOT: product companies, SaaS, hardware.",
    },
    {
        "id": "es_video_uk",
        "company": "EasyStaff (easystaff.io)",
        "offer": "Payroll and contractor payment",
        "segment": "Video production",
        "geo": "UK (broad)",
        "location": ["United Kingdom"],
        "size": ["11,50", "51,200"],
        "industry_tag_id": None,
        "keywords_specific": ["video production", "film production", "content creation"],
        "keywords_broad": ["media", "film", "video"],
        "target_definition": "Video/film production company (11-200 emp). NOT: ad agencies, broadcasters.",
    },
    {
        "id": "onsocial_uk",
        "company": "OnSocial (onsocial.ai)",
        "offer": "AI-powered social media management platform",
        "segment": "Social media influencer agencies",
        "geo": "UK",
        "location": ["United Kingdom"],
        "size": ["1,10", "11,50", "51,200"],
        "industry_tag_id": None,
        "keywords_specific": ["influencer marketing", "social media agency", "influencer agency", "creator management"],
        "keywords_broad": ["social media", "marketing", "influencer"],
        "target_definition": "Influencer/social media agency (1-200 emp). NOT: general marketing, PR, ad agencies, tech platforms.",
    },
]


async def run_approaches_for_segment(key, segment):
    """Run multiple approaches for one segment, return results."""
    seg_id = segment["id"]
    base = {
        "organization_locations": segment["location"],
        "organization_num_employees_ranges": segment["size"],
    }
    results = {}

    print(f"\n{'='*60}")
    print(f"SEGMENT: {segment['segment']} in {segment['geo']} ({segment['company']})")
    print(f"{'='*60}")

    # A1: industry_tag_ids (if available)
    if segment.get("industry_tag_id"):
        print(f"\n  A1: industry_tag_ids...")
        r = await apollo_search(key, {**base, "organization_industry_tag_ids": [segment["industry_tag_id"]]}, pages=5)
        results["A1_industry_tag"] = r
        print(f"    → {r['unique_count']} unique, pages={r['page_counts']}, {r['elapsed_seconds']}s")

    # A2: single specific keyword
    kw = segment["keywords_specific"][0]
    print(f"\n  A2: single keyword '{kw}'...")
    r = await apollo_search(key, {**base, "q_organization_keyword_tags": [kw]}, pages=5)
    results["A2_single_kw"] = r
    print(f"    → {r['unique_count']} unique, pages={r['page_counts']}, {r['elapsed_seconds']}s")

    # A3: multiple specific keywords
    kws = segment["keywords_specific"]
    print(f"\n  A3: multiple keywords {kws}...")
    r = await apollo_search(key, {**base, "q_organization_keyword_tags": kws}, pages=5)
    results["A3_multi_kw"] = r
    print(f"    → {r['unique_count']} unique, pages={r['page_counts']}, {r['elapsed_seconds']}s")

    # A8: broad keywords (no enrichment)
    kws_broad = segment["keywords_broad"]
    print(f"\n  A8: broad keywords {kws_broad}...")
    r = await apollo_search(key, {**base, "q_organization_keyword_tags": kws_broad}, pages=5)
    results["A8_broad_kw"] = r
    print(f"    → {r['unique_count']} unique, pages={r['page_counts']}, {r['elapsed_seconds']}s")

    # A4: industry + specific keywords (AND)
    if segment.get("industry_tag_id"):
        print(f"\n  A4: industry + specific keywords...")
        r = await apollo_search(key, {**base,
            "organization_industry_tag_ids": [segment["industry_tag_id"]],
            "q_organization_keyword_tags": segment["keywords_specific"]}, pages=5)
        results["A4_industry_plus_kw"] = r
        print(f"    → {r['unique_count']} unique, pages={r['page_counts']}, {r['elapsed_seconds']}s")

    # A6: parallel multi-keyword (run each keyword separately, dedup)
    print(f"\n  A6: parallel multi-keyword (4 separate searches)...")
    t0 = time.time()
    parallel_results = await asyncio.gather(*[
        apollo_search(key, {**base, "q_organization_keyword_tags": [kw]}, pages=3)
        for kw in segment["keywords_specific"][:4]
    ])
    all_domains = set()
    all_companies = []
    total_credits = 0
    for pr in parallel_results:
        total_credits += pr["credits"]
        for c in pr["companies"]:
            if c["domain"] not in all_domains:
                all_domains.add(c["domain"])
                all_companies.append(c)
    elapsed = time.time() - t0
    results["A6_parallel_multi"] = {
        "companies": all_companies,
        "unique_count": len(all_companies),
        "credits": total_credits,
        "elapsed_seconds": round(elapsed, 1),
        "sub_results": [{"kw": kw, "unique": pr["unique_count"], "pages": pr["page_counts"]}
                        for kw, pr in zip(segment["keywords_specific"][:4], parallel_results)],
    }
    print(f"    → {len(all_companies)} unique (deduped), {total_credits} credits, {elapsed:.1f}s")

    # Save all results
    # Strip company lists for summary (keep only counts)
    summary = {}
    for approach, r in results.items():
        summary[approach] = {
            "unique_count": r["unique_count"],
            "credits": r["credits"],
            "elapsed_seconds": r["elapsed_seconds"],
            "page_counts": r.get("page_counts"),
            "apollo_total": r.get("apollo_total"),
        }
        if "sub_results" in r:
            summary[approach]["sub_results"] = r["sub_results"]

    # Save full data
    outfile = f"{TMP_DIR}/approaches_{seg_id}_{TIMESTAMP}.json"
    with open(outfile, "w") as f:
        json.dump({
            "segment": {k: v for k, v in segment.items() if k != "target_definition"},
            "results": summary,
            "sample_companies": {
                approach: [c["name"] for c in r["companies"][:10]]
                for approach, r in results.items()
            },
        }, f, indent=2)
    print(f"\n  Saved: {outfile}")

    return seg_id, summary


async def main():
    key = await get_key()
    if not key:
        print("No Apollo key")
        return

    print(f"APOLLO APPROACH TESTING — {TIMESTAMP}")
    print(f"Testing {len(SEGMENTS)} segments × 5-6 approaches each")

    all_summaries = {}
    for segment in SEGMENTS:
        seg_id, summary = await run_approaches_for_segment(key, segment)
        all_summaries[seg_id] = summary

    # Final comparison
    print("\n" + "=" * 80)
    print("FINAL COMPARISON")
    print("=" * 80)
    print(f"\n{'Segment':<25} {'Approach':<25} {'Unique':>7} {'Credits':>8} {'Time':>6}")
    print("-" * 75)
    for seg_id, approaches in all_summaries.items():
        for approach, data in approaches.items():
            print(f"{seg_id:<25} {approach:<25} {data['unique_count']:>7} {data['credits']:>8} {data['elapsed_seconds']:>5}s")

    # Save final comparison
    final_file = f"{TMP_DIR}/approach_comparison_{TIMESTAMP}.json"
    with open(final_file, "w") as f:
        json.dump(all_summaries, f, indent=2)
    print(f"\nFinal comparison saved: {final_file}")


asyncio.run(main())
