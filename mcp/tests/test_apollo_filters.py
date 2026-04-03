"""Test Apollo filter behavior — AND vs OR, industry tag IDs, keyword matching.

Questions to answer:
1. Does industry + keywords = AND or OR?
2. What are the actual industry tag IDs?
3. Does adding industry filter increase or decrease results vs keywords-only?
4. What keywords do real companies actually have?
5. How does location format affect results?

Run:
    cd mcp && python3 tests/test_apollo_filters.py
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

APOLLO_KEY = os.environ.get("APOLLO_API_KEY", "")
TMP_DIR = Path(__file__).parent / "tmp"


async def apollo(body: dict) -> dict:
    """Call Apollo search. Returns {total, companies, raw}."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.apollo.io/api/v1/mixed_companies/search",
            headers={"X-Api-Key": APOLLO_KEY, "Content-Type": "application/json"},
            json={"per_page": 10, "page": 1, **body},
        )
        data = resp.json()
        if "error" in str(data.get("error", "")):
            return {"total": -1, "companies": [], "error": data.get("error")}
        companies = data.get("accounts") or data.get("organizations") or []
        total = data.get("pagination", {}).get("total_entries", 0)
        return {"total": total, "companies": companies}


async def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    lines = []

    def log(msg):
        print(msg)
        lines.append(msg)

    log(f"APOLLO FILTER BEHAVIOR TEST — {ts}")
    log("=" * 90)

    all_tests = []

    def record(name, filters, result):
        entry = {"name": name, "filters": filters, "total": result["total"]}
        if result.get("error"):
            entry["error"] = str(result["error"])
        if result["companies"]:
            entry["sample"] = [
                {"name": c.get("name"), "domain": c.get("primary_domain"),
                 "industry": c.get("industry"), "keywords": (c.get("keywords") or c.get("keyword_tags") or [])[:5]}
                for c in result["companies"][:5]
            ]
        all_tests.append(entry)

    # ═══════════════════════════════════════════════════════════
    # TEST 1: Baseline — keywords only
    # ═══════════════════════════════════════════════════════════
    log("\n--- TEST 1: Keywords only ---")

    for name, kw, loc in [
        ("IT consulting Miami", ["IT consulting"], ["Miami, Florida, United States"]),
        ("IT consulting Miami 3kw", ["IT consulting", "technology consulting", "IT services"], ["Miami, Florida, United States"]),
        ("Fashion Italy", ["fashion"], ["Italy"]),
        ("Fashion Italy 3kw", ["fashion brand", "apparel", "clothing"], ["Italy"]),
        ("Influencer UK", ["influencer marketing"], ["United Kingdom"]),
        ("Influencer UK 3kw", ["influencer marketing", "creator economy", "influencer platform"], ["United Kingdom"]),
    ]:
        filters = {"q_organization_keyword_tags": kw, "organization_locations": loc}
        r = await apollo(filters)
        log(f"  {name}: {r['total']} companies | kw={kw}")
        record(f"1_kw_only_{name}", filters, r)
        await asyncio.sleep(0.5)

    # ═══════════════════════════════════════════════════════════
    # TEST 2: Industry names as keyword tags (does Apollo treat them differently?)
    # ═══════════════════════════════════════════════════════════
    log("\n--- TEST 2: Industry names as keyword tags ---")

    for name, kw, loc in [
        ("IT as industry name", ["information technology & services"], ["Miami, Florida, United States"]),
        ("Fashion as industry name", ["apparel & fashion"], ["Italy"]),
        ("Marketing as industry name", ["marketing & advertising"], ["United Kingdom"]),
    ]:
        filters = {"q_organization_keyword_tags": kw, "organization_locations": loc}
        r = await apollo(filters)
        log(f"  {name}: {r['total']} companies | kw={kw}")
        record(f"2_industry_as_kw_{name}", filters, r)
        await asyncio.sleep(0.5)

    # ═══════════════════════════════════════════════════════════
    # TEST 3: Try organization_industry_tag_ids (need to find valid IDs)
    # First, get IDs from a company's data
    # ═══════════════════════════════════════════════════════════
    log("\n--- TEST 3: Discover industry tag IDs ---")

    # Search for a known company to extract its industry tag ID
    r = await apollo({"q_organization_keyword_tags": ["IT consulting"], "organization_locations": ["United States"], "per_page": 25})
    log(f"  US IT companies search: {r['total']} total, {len(r['companies'])} returned")

    industry_ids = {}
    for c in r["companies"]:
        ind = c.get("industry")
        ind_tag = c.get("industry_tag_id") or c.get("organization_industry_tag_id")
        if ind and ind_tag and ind not in industry_ids:
            industry_ids[ind] = ind_tag
            log(f"  Found: '{ind}' → tag_id: {ind_tag}")

    # Also check all available fields on a company
    if r["companies"]:
        sample = r["companies"][0]
        industry_fields = {k: v for k, v in sample.items() if "industr" in k.lower() or "tag" in k.lower()}
        log(f"  Industry-related fields on company: {list(industry_fields.keys())}")
        log(f"  Values: {json.dumps(industry_fields, default=str)[:500]}")

    await asyncio.sleep(0.5)

    # ═══════════════════════════════════════════════════════════
    # TEST 4: Use discovered industry tag IDs
    # ═══════════════════════════════════════════════════════════
    log("\n--- TEST 4: Industry tag IDs as filter ---")

    if industry_ids:
        for ind_name, ind_id in list(industry_ids.items())[:3]:
            # Industry only
            filters_ind = {"organization_industry_tag_ids": [ind_id], "organization_locations": ["United States"]}
            r_ind = await apollo(filters_ind)
            log(f"  Industry only '{ind_name}' (id={ind_id}): {r_ind['total']} companies")
            record(f"4_industry_id_only_{ind_name}", filters_ind, r_ind)
            await asyncio.sleep(0.5)

            # Industry + keywords (AND or OR?)
            filters_both = {
                "organization_industry_tag_ids": [ind_id],
                "q_organization_keyword_tags": ["IT consulting"],
                "organization_locations": ["United States"],
            }
            r_both = await apollo(filters_both)
            log(f"  Industry '{ind_name}' + kw 'IT consulting': {r_both['total']} companies")
            record(f"4_industry_plus_kw_{ind_name}", filters_both, r_both)
            await asyncio.sleep(0.5)

            # Compare
            if r_ind["total"] > 0 and r_both["total"] > 0:
                if r_both["total"] < r_ind["total"]:
                    log(f"    → AND behavior (both < industry-only: {r_both['total']} < {r_ind['total']})")
                elif r_both["total"] > r_ind["total"]:
                    log(f"    → OR behavior (both > industry-only: {r_both['total']} > {r_ind['total']})")
                else:
                    log(f"    → Same count ({r_both['total']})")
    else:
        log("  No industry IDs discovered — trying known format")
        # Try with string industry names
        for param_name in ["organization_industry_tag_ids", "q_organization_industry_tag_ids", "industry_tag_ids"]:
            filters = {param_name: ["information technology & services"], "organization_locations": ["United States"]}
            r = await apollo(filters)
            log(f"  {param_name} with string name: {r['total']} | error={r.get('error', 'none')}")
            record(f"4_try_{param_name}", filters, r)
            await asyncio.sleep(0.5)

    # ═══════════════════════════════════════════════════════════
    # TEST 5: Location format variations
    # ═══════════════════════════════════════════════════════════
    log("\n--- TEST 5: Location format ---")

    for name, loc in [
        ("UK", ["UK"]),
        ("United Kingdom", ["United Kingdom"]),
        ("London", ["London"]),
        ("London, United Kingdom", ["London, United Kingdom"]),
        ("London, England, United Kingdom", ["London, England, United Kingdom"]),
    ]:
        filters = {"q_organization_keyword_tags": ["marketing"], "organization_locations": loc}
        r = await apollo(filters)
        log(f"  '{name}': {r['total']} companies")
        record(f"5_location_{name}", filters, r)
        await asyncio.sleep(0.5)

    # ═══════════════════════════════════════════════════════════
    # TEST 6: Employee size with and without keywords
    # ═══════════════════════════════════════════════════════════
    log("\n--- TEST 6: Size filter interaction ---")

    base_kw = {"q_organization_keyword_tags": ["IT consulting"], "organization_locations": ["United States"]}

    r_no_size = await apollo(base_kw)
    log(f"  No size filter: {r_no_size['total']}")
    record("6_no_size", base_kw, r_no_size)
    await asyncio.sleep(0.5)

    r_small = await apollo({**base_kw, "organization_num_employees_ranges": ["11,50"]})
    log(f"  11-50 employees: {r_small['total']}")
    record("6_size_11_50", {**base_kw, "organization_num_employees_ranges": ["11,50"]}, r_small)
    await asyncio.sleep(0.5)

    r_medium = await apollo({**base_kw, "organization_num_employees_ranges": ["11,50", "51,200"]})
    log(f"  11-200 employees: {r_medium['total']}")
    record("6_size_11_200", {**base_kw, "organization_num_employees_ranges": ["11,50", "51,200"]}, r_medium)
    await asyncio.sleep(0.5)

    # ═══════════════════════════════════════════════════════════
    # TEST 7: Multiple keywords — OR or AND?
    # ═══════════════════════════════════════════════════════════
    log("\n--- TEST 7: Multiple keywords — AND or OR? ---")

    r_a = await apollo({"q_organization_keyword_tags": ["IT consulting"], "organization_locations": ["United States"]})
    log(f"  'IT consulting' only: {r_a['total']}")
    await asyncio.sleep(0.5)

    r_b = await apollo({"q_organization_keyword_tags": ["software development"], "organization_locations": ["United States"]})
    log(f"  'software development' only: {r_b['total']}")
    await asyncio.sleep(0.5)

    r_ab = await apollo({"q_organization_keyword_tags": ["IT consulting", "software development"], "organization_locations": ["United States"]})
    log(f"  Both together: {r_ab['total']}")
    await asyncio.sleep(0.5)

    if r_a["total"] > 0 and r_b["total"] > 0:
        if r_ab["total"] > max(r_a["total"], r_b["total"]):
            log(f"  → KEYWORDS ARE OR ({r_ab['total']} > max({r_a['total']}, {r_b['total']}))")
        elif r_ab["total"] < min(r_a["total"], r_b["total"]):
            log(f"  → KEYWORDS ARE AND ({r_ab['total']} < min({r_a['total']}, {r_b['total']}))")
        else:
            log(f"  → Unclear ({r_ab['total']} vs {r_a['total']} + {r_b['total']})")

    # ═══════════════════════════════════════════════════════════
    # TEST 8: Extract real keyword vocabulary from results
    # ═══════════════════════════════════════════════════════════
    log("\n--- TEST 8: Real keyword vocabulary from Apollo ---")

    for name, kw, loc in [
        ("IT Miami", ["IT consulting"], ["Miami, Florida, United States"]),
        ("Fashion Italy", ["fashion"], ["Italy"]),
        ("Influencer UK", ["influencer marketing"], ["United Kingdom"]),
    ]:
        r = await apollo({"q_organization_keyword_tags": kw, "organization_locations": loc, "per_page": 25})
        if r["companies"]:
            from collections import Counter
            kw_counter = Counter()
            ind_counter = Counter()
            for c in r["companies"]:
                ind = c.get("industry")
                if ind:
                    ind_counter[ind] += 1
                tags = c.get("keywords") or c.get("keyword_tags") or []
                if isinstance(tags, str):
                    tags = [t.strip() for t in tags.split(",")]
                for t in tags:
                    if t and len(t) > 2:
                        kw_counter[t.lower()] += 1

            log(f"  {name} ({r['total']} total, {len(r['companies'])} sampled):")
            log(f"    Top industries: {dict(ind_counter.most_common(5))}")
            log(f"    Top keywords: {dict(kw_counter.most_common(10))}")
            record(f"8_vocab_{name}", {"kw": kw, "loc": loc}, r)
        else:
            log(f"  {name}: 0 results")
        await asyncio.sleep(0.5)

    # ═══════════════════════════════════════════════════════════
    # SUMMARY
    # ═══════════════════════════════════════════════════════════
    log(f"\n{'='*90}")
    log("SUMMARY")
    log(f"{'='*90}")
    for t in all_tests:
        err = f" ERROR:{t['error']}" if t.get("error") else ""
        log(f"  {t['name']:<50} → {t['total']:>8} companies{err}")

    # Save everything
    log_file = TMP_DIR / f"{ts}_apollo_filters_test.log"
    log_file.write_text("\n".join(lines))
    results_file = TMP_DIR / f"{ts}_apollo_filters_test.json"
    results_file.write_text(json.dumps({"ts": ts, "tests": all_tests}, indent=2, default=str))
    log(f"\nSaved: {log_file.name}, {results_file.name}")


if __name__ == "__main__":
    if not APOLLO_KEY:
        print("Set APOLLO_API_KEY")
        sys.exit(1)
    asyncio.run(main())
