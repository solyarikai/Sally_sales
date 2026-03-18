"""
Flinter / Werlabs-like Company Search — Apollo + Clay Pipeline
================================================================
Find companies similar to Werlabs.se (DTC blood testing, preventive health checks)
across 18 target countries, total funding ≤ $20M.

Countries: Germany, Australia, Canada, Singapore, Sweden, Netherlands, Belgium,
Italy, Spain, Norway, Ireland, Switzerland, Czech Republic, Austria, Denmark,
Finland, France, New Zealand.

Flow:
  Part 1: Apollo Organization Search (keyword × country matrix)
  Part 2: Post-filter by funding ≤ $20M from search results
  Part 3: Apollo Organization Enrichment for missing funding data
  Part 4: Clay TAM export for additional coverage
  Part 5: Merge, deduplicate, export to JSON + CSV

Usage:
  cd magnum-opus && python scripts/flinter_werlabs_search.py
"""
import asyncio
import csv
import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("flinter_werlabs")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# ── Config ─────────────────────────────────────────────────────────────────

# Read API key from .env.dev
_ENV_FILE = os.path.join(os.path.dirname(__file__), '..', 'backend', '.env.dev')
APOLLO_API_KEY = ""
if os.path.exists(_ENV_FILE):
    for line in open(_ENV_FILE):
        if line.startswith("APOLLO_API_KEY="):
            APOLLO_API_KEY = line.split("=", 1)[1].strip()
            break
# Allow override from environment
APOLLO_API_KEY = os.environ.get("APOLLO_API_KEY", APOLLO_API_KEY)

APOLLO_BASE_URL = "https://api.apollo.io/api/v1"

COUNTRIES = [
    "Germany", "Australia", "Canada", "Singapore", "Sweden",
    "Netherlands", "Belgium", "Italy", "Spain", "Norway",
    "Ireland", "Switzerland", "Czech Republic", "Austria",
    "Denmark", "Finland", "France", "New Zealand",
]

# Keywords to find Werlabs-like companies (DTC blood testing / preventive health)
KEYWORDS_TIER1 = [
    ["blood testing"],
    ["blood test"],
    ["health check"],
    ["health screening"],
    ["preventive health"],
    ["lab testing"],
    ["diagnostic testing"],
    ["health diagnostics"],
]

KEYWORDS_TIER2 = [
    ["clinical laboratory"],
    ["medical testing"],
    ["biomarker"],
    ["wellness testing"],
    ["at-home testing"],
    ["home health test"],
    ["self testing health"],
]

SIZE_RANGES = ["1,10", "11,50", "51,200", "201,500"]
MAX_FUNDING_USD = 20_000_000

OUT_DIR = os.path.join(os.path.dirname(__file__), "flinter_output")

# ── Standalone Apollo client (no backend dependencies) ─────────────────────

_last_call_time = 0.0
_credits_used = 0


async def apollo_api_call(method: str, endpoint: str, json_data: dict = None) -> Optional[dict]:
    """Rate-limited Apollo API call with retry on 429."""
    global _last_call_time
    MAX_RETRIES = 3
    backoff = [30, 60, 120]

    for attempt in range(MAX_RETRIES + 1):
        now = time.monotonic()
        elapsed = now - _last_call_time
        if elapsed < 0.3:
            await asyncio.sleep(0.3 - elapsed)
        _last_call_time = time.monotonic()

        headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "X-Api-Key": APOLLO_API_KEY,
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                if method == "POST":
                    resp = await client.post(f"{APOLLO_BASE_URL}{endpoint}", json=json_data, headers=headers)
                else:
                    resp = await client.get(f"{APOLLO_BASE_URL}{endpoint}", headers=headers)

                if resp.status_code == 429:
                    if attempt < MAX_RETRIES:
                        wait = backoff[attempt]
                        logger.warning(f"Apollo 429 on {endpoint}, retry {attempt+1}/{MAX_RETRIES}, waiting {wait}s")
                        await asyncio.sleep(wait)
                        continue
                    else:
                        logger.error(f"Apollo 429 exhausted retries on {endpoint}")
                        return None
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Apollo {endpoint}: {e.response.status_code} - {e.response.text[:200]}")
            return None
        except Exception as e:
            logger.error(f"Apollo {endpoint} failed: {e}")
            return None
    return None


async def search_organizations(
    keyword_tags: List[str],
    locations: Optional[List[str]] = None,
    num_employees_ranges: Optional[List[str]] = None,
    page: int = 1,
    per_page: int = 100,
) -> Optional[Dict[str, Any]]:
    payload: Dict[str, Any] = {
        "q_organization_keyword_tags": keyword_tags,
        "page": page,
        "per_page": min(per_page, 100),
    }
    if locations:
        payload["organization_locations"] = locations
    if num_employees_ranges:
        payload["organization_num_employees_ranges"] = num_employees_ranges
    return await apollo_api_call("POST", "/mixed_companies/search", payload)


async def search_organizations_all_pages(
    keyword_tags: List[str],
    locations: Optional[List[str]] = None,
    num_employees_ranges: Optional[List[str]] = None,
    max_pages: int = 10,
) -> List[Dict[str, Any]]:
    all_orgs: List[Dict[str, Any]] = []
    for page in range(1, max_pages + 1):
        data = await search_organizations(keyword_tags, locations, num_employees_ranges, page)
        if not data:
            break
        orgs = data.get("organizations", [])
        all_orgs.extend(orgs)
        total_pages = data.get("pagination", {}).get("total_pages", 1)
        if page >= total_pages:
            break
    return all_orgs


async def enrich_organization(domain: str) -> Optional[Dict[str, Any]]:
    global _credits_used
    data = await apollo_api_call("POST", "/organizations/enrich", {"domain": domain})
    if data and data.get("organization"):
        _credits_used += 1
    return data.get("organization") if data else None


# ── Helpers ────────────────────────────────────────────────────────────────

def extract_domain(org: Dict[str, Any]) -> Optional[str]:
    domain = org.get("primary_domain") or ""
    if not domain:
        url = org.get("website_url") or ""
        url = url.strip().lower()
        for prefix in ("https://", "http://", "www."):
            if url.startswith(prefix):
                url = url[len(prefix):]
        domain = url.split("/")[0].split("?")[0].split("#")[0]
    domain = domain.lower().strip()
    return domain if domain and "." in domain else None


def parse_funding(org: Dict[str, Any]) -> Optional[float]:
    tf = org.get("total_funding")
    if tf is not None and isinstance(tf, (int, float)) and tf > 0:
        return float(tf)

    lf = org.get("latest_funding_amount")
    if lf is not None and isinstance(lf, (int, float)) and lf > 0:
        return float(lf)

    tfp = org.get("total_funding_printed")
    if tfp and isinstance(tfp, str):
        try:
            clean = tfp.replace("$", "").replace(",", "").strip().upper()
            multiplier = 1
            if clean.endswith("B"):
                multiplier = 1_000_000_000
                clean = clean[:-1]
            elif clean.endswith("M"):
                multiplier = 1_000_000
                clean = clean[:-1]
            elif clean.endswith("K"):
                multiplier = 1_000
                clean = clean[:-1]
            return float(clean) * multiplier
        except (ValueError, TypeError):
            pass
    return None


# ══════════════════════════════════════════════════════════════════════════
# Part 1: Apollo Organization Search
# ══════════════════════════════════════════════════════════════════════════
async def part1_apollo_org_search() -> Dict[str, Any]:
    logger.info("=" * 60)
    logger.info("PART 1: Apollo Organization Search")
    logger.info(f"Countries: {len(COUNTRIES)}")
    logger.info(f"Keyword sets: {len(KEYWORDS_TIER1) + len(KEYWORDS_TIER2)}")
    logger.info("=" * 60)

    if not APOLLO_API_KEY:
        logger.error("Apollo API key not configured!")
        return {"orgs_by_domain": {}, "stats": {}}

    orgs_by_domain: Dict[str, Dict[str, Any]] = {}
    combo_stats: Dict[str, Dict[str, int]] = {}
    consecutive_failures = 0

    all_keywords = KEYWORDS_TIER1 + KEYWORDS_TIER2

    for keyword_tags in all_keywords:
        for country in COUNTRIES:
            combo_key = f"{keyword_tags[0]}|{country}"
            logger.info(f"  Searching: {combo_key}")

            orgs = await search_organizations_all_pages(
                keyword_tags=keyword_tags,
                locations=[country],
                num_employees_ranges=SIZE_RANGES,
                max_pages=10,
            )

            if not orgs:
                consecutive_failures += 1
                if consecutive_failures >= 5:
                    logger.warning("5 consecutive empty — possible credit exhaustion, stopping")
                    return {"orgs_by_domain": orgs_by_domain, "stats": combo_stats, "early_stop": True}
                combo_stats[combo_key] = {"orgs_returned": 0, "new": 0}
                continue
            else:
                consecutive_failures = 0

            new_count = 0
            for org in orgs:
                domain = extract_domain(org)
                if not domain:
                    continue
                if domain not in orgs_by_domain:
                    new_count += 1
                    orgs_by_domain[domain] = {
                        "domain": domain,
                        "name": org.get("name", ""),
                        "website_url": org.get("website_url", ""),
                        "linkedin_url": org.get("linkedin_url", ""),
                        "industry": org.get("industry", ""),
                        "keywords": org.get("keywords", []),
                        "country": org.get("country", ""),
                        "city": org.get("city", ""),
                        "state": org.get("state", ""),
                        "estimated_num_employees": org.get("estimated_num_employees"),
                        "total_funding": org.get("total_funding"),
                        "total_funding_printed": org.get("total_funding_printed"),
                        "latest_funding_amount": org.get("latest_funding_amount"),
                        "latest_funding_stage": org.get("latest_funding_stage"),
                        "latest_funding_round_date": org.get("latest_funding_round_date"),
                        "founded_year": org.get("founded_year"),
                        "short_description": org.get("short_description", ""),
                        "annual_revenue": org.get("annual_revenue"),
                        "annual_revenue_printed": org.get("annual_revenue_printed"),
                        "primary_phone": org.get("primary_phone", {}).get("number") if org.get("primary_phone") else None,
                        "logo_url": org.get("logo_url", ""),
                        "search_keyword": keyword_tags[0],
                        "search_country": country,
                        "_raw_keys": list(org.keys()),
                    }

            combo_stats[combo_key] = {"orgs_returned": len(orgs), "new": new_count}
            logger.info(f"    -> {len(orgs)} orgs, {new_count} new (total: {len(orgs_by_domain)})")

    logger.info(f"\nApollo search complete: {len(orgs_by_domain)} unique domains")
    return {"orgs_by_domain": orgs_by_domain, "stats": combo_stats}


# ══════════════════════════════════════════════════════════════════════════
# Part 2: Filter by funding
# ══════════════════════════════════════════════════════════════════════════
def part2_filter_funding(orgs_by_domain: Dict[str, Dict]) -> Dict[str, Any]:
    logger.info("=" * 60)
    logger.info("PART 2: Filtering by funding <= $20M")
    logger.info("=" * 60)

    within_cap = {}
    over_cap = {}
    unknown_funding = {}

    for domain, org in orgs_by_domain.items():
        funding = parse_funding(org)
        if funding is not None:
            org["_parsed_funding"] = funding
            if funding <= MAX_FUNDING_USD:
                within_cap[domain] = org
            else:
                over_cap[domain] = org
        else:
            org["_parsed_funding"] = None
            unknown_funding[domain] = org

    logger.info(f"  Within cap (<=$20M): {len(within_cap)}")
    logger.info(f"  Over cap (>$20M): {len(over_cap)}")
    logger.info(f"  Unknown funding: {len(unknown_funding)}")

    return {"within_cap": within_cap, "over_cap": over_cap, "unknown_funding": unknown_funding}


# ══════════════════════════════════════════════════════════════════════════
# Part 3: Enrich unknown-funding orgs
# ══════════════════════════════════════════════════════════════════════════
async def part3_enrich_unknown(unknown_domains: Dict[str, Dict]) -> Dict[str, Any]:
    logger.info("=" * 60)
    logger.info(f"PART 3: Enriching {len(unknown_domains)} orgs with unknown funding")
    logger.info("=" * 60)

    if len(unknown_domains) > 500:
        logger.warning(f"  Too many unknowns ({len(unknown_domains)}) — skipping enrichment to save credits")
        return {"enriched": 0, "within_cap": {}, "over_cap": {}, "still_unknown": unknown_domains}

    if not APOLLO_API_KEY:
        return {"enriched": 0, "within_cap": {}, "over_cap": {}, "still_unknown": unknown_domains}

    within_cap = {}
    over_cap = {}
    still_unknown = {}
    enriched = 0

    domains_list = list(unknown_domains.keys())
    for i, domain in enumerate(domains_list):
        org_data = unknown_domains[domain]
        enriched_org = await enrich_organization(domain)
        if not enriched_org:
            still_unknown[domain] = org_data
            continue

        enriched += 1
        for key in ("total_funding", "total_funding_printed", "latest_funding_amount",
                     "latest_funding_stage", "annual_revenue", "annual_revenue_printed"):
            org_data[key] = enriched_org.get(key)
        org_data["founded_year"] = org_data.get("founded_year") or enriched_org.get("founded_year")
        org_data["short_description"] = org_data.get("short_description") or enriched_org.get("short_description", "")

        funding = parse_funding(org_data)
        org_data["_parsed_funding"] = funding

        if funding is not None:
            if funding <= MAX_FUNDING_USD:
                within_cap[domain] = org_data
            else:
                over_cap[domain] = org_data
        else:
            still_unknown[domain] = org_data

        if (i + 1) % 50 == 0:
            logger.info(f"  Enriched {i+1}/{len(domains_list)}")

    logger.info(f"  Done: enriched={enriched}, within_cap={len(within_cap)}, over={len(over_cap)}, unknown={len(still_unknown)}")
    return {"enriched": enriched, "within_cap": within_cap, "over_cap": over_cap, "still_unknown": still_unknown}


# ══════════════════════════════════════════════════════════════════════════
# Part 4: Clay TAM Export (via Puppeteer — skipped if not available)
# ══════════════════════════════════════════════════════════════════════════
async def part4_clay_tam_export() -> List[Dict[str, Any]]:
    """Prepare Clay filters for manual or automated TAM export."""
    logger.info("=" * 60)
    logger.info("PART 4: Clay TAM Export")
    logger.info("=" * 60)

    clay_filters = {
        "industries": [
            "Hospital & Health Care",
            "Health, Wellness and Fitness",
            "Medical Devices",
            "Biotechnology",
            "Medical Practice",
        ],
        "industries_exclude": [
            "Pharmaceuticals",
            "Veterinary",
            "Insurance",
            "Staffing and Recruiting",
            "Hospitals and Health Care",  # too broad — big hospitals
        ],
        "description_keywords": [
            "blood test",
            "blood testing",
            "health check",
            "health screening",
            "preventive health",
            "biomarker",
            "at-home test",
            "home test kit",
            "lab test",
            "diagnostic test",
            "wellness test",
            "health assessment",
        ],
        "description_keywords_exclude": [
            "veterinary",
            "animal",
            "clinical trial",
            "CRO",
            "pharmaceutical manufacturing",
            "drug development",
        ],
        "country_names": COUNTRIES,
        "sizes": ["1-10", "11-50", "51-200", "201-500"],
        "types": ["Privately held"],
    }

    # Save Clay filters for manual use
    os.makedirs(OUT_DIR, exist_ok=True)
    filters_path = os.path.join(OUT_DIR, "clay_filters.json")
    with open(filters_path, "w") as f:
        json.dump(clay_filters, f, indent=2)
    logger.info(f"  Clay filters saved to {filters_path}")
    logger.info("  To run Clay TAM: use these filters in Clay UI or via clay_tam_export.js")

    # Try Puppeteer automation
    clay_script = os.path.join(os.path.dirname(__file__), "clay", "clay_tam_export.js")
    clay_exports = os.path.join(os.path.dirname(__file__), "clay", "exports")

    if not os.path.exists(clay_script):
        logger.info("  Clay Puppeteer script not found — skipping automated export")
        return []

    # Write filters for the script
    os.makedirs(clay_exports, exist_ok=True)
    input_filters = os.path.join(clay_exports, "filters_input.json")
    with open(input_filters, "w") as f:
        json.dump(clay_filters, f, indent=2)

    icp_text = (
        "Direct-to-consumer health testing companies like Werlabs.se. "
        "Blood tests, health checks, health screenings, biomarker testing for consumers (B2C). "
        "Countries: " + ", ".join(COUNTRIES) + ". "
        "Exclude: hospitals, CROs, pharma, veterinary, B2B-only lab equipment."
    )

    cmd = ["node", clay_script, "--headless", "--auto", icp_text]
    logger.info(f"  Running Clay Puppeteer...")

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=os.path.join(os.path.dirname(__file__), "clay"),
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=600)

        if proc.returncode != 0:
            logger.warning(f"  Clay script exited {proc.returncode}: {stderr.decode()[-300:]}")

        # Read results
        companies_file = os.path.join(clay_exports, "tam_companies.json")
        if os.path.exists(companies_file):
            companies = json.loads(open(companies_file).read())
            logger.info(f"  Clay: {len(companies)} companies found")
            return companies
        else:
            logger.info("  Clay: no output file found")
            return []
    except asyncio.TimeoutError:
        logger.warning("  Clay script timed out after 10 min")
        return []
    except FileNotFoundError:
        logger.warning("  Node.js not found — skipping Clay")
        return []


# ══════════════════════════════════════════════════════════════════════════
# Part 5: Merge & Export
# ══════════════════════════════════════════════════════════════════════════
def part5_merge_and_export(
    apollo_within_cap: Dict[str, Dict],
    apollo_unknown: Dict[str, Dict],
    clay_companies: List[Dict],
) -> int:
    logger.info("=" * 60)
    logger.info("PART 5: Merge & Export")
    logger.info("=" * 60)

    os.makedirs(OUT_DIR, exist_ok=True)

    all_results: Dict[str, Dict] = {}
    for domain, org in apollo_within_cap.items():
        org["_source"] = "apollo_confirmed"
        all_results[domain] = org

    for domain, org in apollo_unknown.items():
        if domain not in all_results:
            org["_source"] = "apollo_funding_unknown"
            all_results[domain] = org

    clay_added = 0
    for company in clay_companies:
        domain = (company.get("Domain") or company.get("domain") or "").strip().lower().replace("www.", "").rstrip("/")
        if domain and domain not in all_results:
            all_results[domain] = {
                "domain": domain,
                "name": company.get("Name") or company.get("name") or "",
                "website_url": f"https://{domain}",
                "linkedin_url": company.get("LinkedIn URL") or company.get("linkedin_url") or "",
                "industry": company.get("Primary Industry") or company.get("industry") or "",
                "country": company.get("Country") or company.get("country") or "",
                "city": company.get("Location") or company.get("location") or "",
                "estimated_num_employees": company.get("Size") or company.get("size") or "",
                "short_description": company.get("Description") or company.get("description") or "",
                "_source": "clay",
                "_parsed_funding": None,
            }
            clay_added += 1

    logger.info(f"  Apollo confirmed <=$20M: {len(apollo_within_cap)}")
    logger.info(f"  Apollo funding unknown: {len(apollo_unknown)}")
    logger.info(f"  Clay additions: {clay_added}")
    logger.info(f"  Total unique: {len(all_results)}")

    sorted_results = sorted(
        all_results.values(),
        key=lambda x: (0 if x.get("_source") == "apollo_confirmed" else 1, x.get("country", ""), x.get("name", "")),
    )

    # JSON
    json_path = os.path.join(OUT_DIR, "flinter_werlabs_companies.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(sorted_results, f, indent=2, ensure_ascii=False, default=str)
    logger.info(f"  JSON: {json_path}")

    # CSV
    csv_path = os.path.join(OUT_DIR, "flinter_werlabs_companies.csv")
    csv_columns = [
        "domain", "name", "website_url", "linkedin_url", "industry",
        "country", "city", "estimated_num_employees", "short_description",
        "total_funding", "total_funding_printed", "latest_funding_stage",
        "founded_year", "annual_revenue_printed", "_source", "_parsed_funding",
        "search_keyword",
    ]
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_columns, extrasaction="ignore")
        writer.writeheader()
        for row in sorted_results:
            writer.writerow(row)
    logger.info(f"  CSV: {csv_path}")

    # Country breakdown
    by_country: Dict[str, int] = {}
    for org in sorted_results:
        c = org.get("country") or org.get("search_country") or "Unknown"
        by_country[c] = by_country.get(c, 0) + 1

    logger.info("\n  By country:")
    for country, count in sorted(by_country.items(), key=lambda x: -x[1]):
        logger.info(f"    {country}: {count}")

    return len(all_results)


# ══════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════
async def main():
    logger.info("=" * 60)
    logger.info("FLINTER / WERLABS-LIKE COMPANY SEARCH")
    logger.info(f"Started: {datetime.utcnow().isoformat()}")
    logger.info(f"Target: DTC blood testing / health checks")
    logger.info(f"Countries: {len(COUNTRIES)}")
    logger.info(f"Max funding: ${MAX_FUNDING_USD:,.0f}")
    logger.info("=" * 60)

    # Part 1
    apollo_result = await part1_apollo_org_search()
    orgs_by_domain = apollo_result.get("orgs_by_domain", {})

    # Save intermediate
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "apollo_raw_results.json"), "w", encoding="utf-8") as f:
        json.dump(list(orgs_by_domain.values()), f, indent=2, ensure_ascii=False, default=str)
    logger.info(f"Apollo raw: {len(orgs_by_domain)} saved to {OUT_DIR}/apollo_raw_results.json")

    # Part 2
    funding_result = part2_filter_funding(orgs_by_domain)

    # Part 3
    unknown = funding_result["unknown_funding"]
    enrich_result = {}
    if unknown:
        enrich_result = await part3_enrich_unknown(unknown)
        funding_result["within_cap"].update(enrich_result.get("within_cap", {}))
        funding_result["over_cap"].update(enrich_result.get("over_cap", {}))
        unknown = enrich_result.get("still_unknown", unknown)

    # Part 4
    clay_companies = []
    try:
        clay_companies = await part4_clay_tam_export()
    except Exception as e:
        logger.warning(f"Clay TAM skipped: {e}")

    # Part 5
    total = part5_merge_and_export(
        apollo_within_cap=funding_result["within_cap"],
        apollo_unknown=unknown,
        clay_companies=clay_companies,
    )

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    logger.info(f"  Apollo raw: {len(orgs_by_domain)}")
    logger.info(f"  Funding <=$20M: {len(funding_result['within_cap'])}")
    logger.info(f"  Funding >$20M (excluded): {len(funding_result['over_cap'])}")
    logger.info(f"  Funding unknown: {len(unknown)}")
    logger.info(f"  Clay: {len(clay_companies)}")
    logger.info(f"  Total exported: {total}")
    logger.info(f"  Output: {OUT_DIR}/")
    logger.info(f"Finished: {datetime.utcnow().isoformat()}")


if __name__ == "__main__":
    asyncio.run(main())
