"""
Enrich IMAGENCY leads CSV with company HQ location via Apollo API.

Method: Apollo /mixed_companies/api_search (FREE, no credits).
For each unique company_name -> search -> take top match -> extract HQ country/city.

Usage:
    python3 enrich_imagency_company_hq.py \
        --input /path/to/leads.csv \
        --output /path/to/leads_enriched.csv \
        --cache /path/to/apollo_cache.json

Runs on Hetzner (needs APOLLO_API_KEY in env).
Requires: pip install requests
"""

import argparse
import csv
import json
import subprocess
import sys
import os
import time
from pathlib import Path

try:
    import requests
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests

APOLLO_API_URL = "https://api.apollo.io/v1"
RATE_LIMIT = 0.35  # seconds between calls


def search_company(name: str, api_key: str) -> dict | None:
    """Search Apollo for a company by name. Returns best match or None."""
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "X-Api-Key": api_key,
    }
    payload = {
        "q_organization_keyword_tags": [name],
        "page": 1,
        "per_page": 5,
    }

    try:
        resp = requests.post(
            f"{APOLLO_API_URL}/mixed_companies/api_search",
            json=payload,
            headers=headers,
            timeout=15,
        )
        if resp.status_code == 429:
            print(f"  Rate limited, waiting 30s...")
            time.sleep(30)
            return search_company(name, api_key)  # retry once

        if resp.status_code != 200:
            print(f"  API error {resp.status_code} for '{name}'")
            return None

        data = resp.json()
        orgs = data.get("organizations", [])
        if not orgs:
            return None

        # Find best match: prefer exact name match, then first result
        name_lower = name.lower().strip()
        for org in orgs:
            org_name = (org.get("name") or "").lower().strip()
            if org_name == name_lower:
                return org
        # Fallback: first result
        return orgs[0]

    except Exception as e:
        print(f"  Error for '{name}': {e}")
        return None


def extract_hq(org: dict) -> dict:
    """Extract HQ location fields from Apollo org response."""
    return {
        "hq_country": org.get("country") or "",
        "hq_city": org.get("city") or "",
        "hq_state": org.get("state") or "",
        "company_domain": org.get("primary_domain") or org.get("domain") or "",
        "company_linkedin": org.get("linkedin_url") or "",
        "company_industry": org.get("industry") or "",
        "company_employees": org.get("estimated_num_employees") or "",
        "apollo_name_matched": org.get("name") or "",
    }


def main():
    parser = argparse.ArgumentParser(description="Enrich leads with company HQ via Apollo")
    parser.add_argument("--input", required=True, help="Input CSV with leads")
    parser.add_argument("--output", required=True, help="Output enriched CSV")
    parser.add_argument("--cache", default="apollo_company_cache.json", help="Cache file for Apollo results")
    args = parser.parse_args()

    api_key = os.environ.get("APOLLO_API_KEY")
    if not api_key:
        print("ERROR: APOLLO_API_KEY not set in environment")
        sys.exit(1)

    # Load cache
    cache = {}
    cache_path = Path(args.cache)
    if cache_path.exists():
        with open(cache_path) as f:
            cache = json.load(f)
        print(f"Loaded {len(cache)} cached companies")

    # Read input CSV
    with open(args.input, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    print(f"Read {len(rows)} leads")

    # Extract unique company names
    companies = set()
    for row in rows:
        cn = row.get("company_name", "").strip()
        if cn:
            companies.add(cn)
    print(f"Unique companies: {len(companies)}")

    # Enrich missing companies
    to_enrich = [c for c in companies if c not in cache]
    print(f"To enrich via Apollo: {len(to_enrich)} (cached: {len(companies) - len(to_enrich)})")

    for i, name in enumerate(to_enrich):
        print(f"[{i+1}/{len(to_enrich)}] Searching: {name}")
        org = search_company(name, api_key)
        if org:
            cache[name] = extract_hq(org)
            print(f"  -> {cache[name]['hq_city']}, {cache[name]['hq_country']} ({cache[name]['apollo_name_matched']})")
        else:
            cache[name] = {
                "hq_country": "",
                "hq_city": "",
                "hq_state": "",
                "company_domain": "",
                "company_linkedin": "",
                "company_industry": "",
                "company_employees": "",
                "apollo_name_matched": "NOT_FOUND",
            }
            print(f"  -> NOT FOUND")

        # Save cache every 50 companies
        if (i + 1) % 50 == 0:
            with open(cache_path, "w") as f:
                json.dump(cache, f, indent=2, ensure_ascii=False)
            print(f"  [cache saved: {len(cache)} entries]")

        time.sleep(RATE_LIMIT)

    # Final cache save
    with open(cache_path, "w") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)
    print(f"\nCache saved: {len(cache)} entries -> {cache_path}")

    # Build enriched CSV
    extra_fields = ["hq_country", "hq_city", "hq_state", "company_domain",
                    "company_linkedin", "company_industry", "company_employees",
                    "apollo_name_matched"]
    out_fieldnames = list(fieldnames) + extra_fields

    matched = 0
    not_found = 0

    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=out_fieldnames)
        writer.writeheader()
        for row in rows:
            cn = row.get("company_name", "").strip()
            hq = cache.get(cn, {})
            for field in extra_fields:
                row[field] = hq.get(field, "")
            writer.writerow(row)
            if hq.get("apollo_name_matched") and hq["apollo_name_matched"] != "NOT_FOUND":
                matched += 1
            else:
                not_found += 1

    print(f"\n=== RESULTS ===")
    print(f"Total leads:  {len(rows)}")
    print(f"Matched:      {matched} ({matched*100//len(rows)}%)")
    print(f"Not found:    {not_found}")
    print(f"Output:       {args.output}")

    # Print country distribution
    print(f"\n=== HQ COUNTRY DISTRIBUTION ===")
    countries = {}
    for row in rows:
        cn = row.get("company_name", "").strip()
        hq = cache.get(cn, {})
        country = hq.get("hq_country", "UNKNOWN") or "UNKNOWN"
        countries[country] = countries.get(country, 0) + 1
    for country, count in sorted(countries.items(), key=lambda x: -x[1])[:25]:
        print(f"  {count:>5}  {country}")


if __name__ == "__main__":
    main()
