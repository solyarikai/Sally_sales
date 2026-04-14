#!/usr/bin/env python3.11
"""
People search pipeline:
1. Apollo mixed_people/api_search — free, no email credits, max N per domain
2. Exa web search — find LinkedIn URLs
3. Output Apollo-format CSV → ready for pipeline.py people

Usage:
    python3.11 sofia/scripts/people_search.py \
        --csv sofia/output/OnSocial/pipeline/affperf_2026-04-13/_master/OS_Targets_AFFILIATE_PERFORMANCE_2026-04-13.csv \
        --segment affperf \
        --max-per-domain 6 \
        --out sofia/input/OS_People_AFFPERF_2026-04-14.csv
"""

import argparse
import csv
import os
import re
import time
from collections import defaultdict
from pathlib import Path

import httpx

APOLLO_API_KEY = os.environ.get("APOLLO_API_KEY", "JmKefOqG2Wx_wPKGcoVqCw")
EXA_API_KEY = os.environ.get("EXA_API_KEY", "197fc32a-3563-4e29-bdb1-5f5a796034c9")

SENIORITIES = ["c_suite", "vp", "director", "head", "founder", "owner", "partner"]

# Apollo API
APOLLO_BASE = "https://api.apollo.io/api/v1"
APOLLO_HEADERS = {
    "Content-Type": "application/json",
    "Cache-Control": "no-cache",
    "x-api-key": APOLLO_API_KEY,
}

# Exa API
EXA_BASE = "https://api.exa.ai"
EXA_HEADERS = {
    "x-api-key": EXA_API_KEY,
    "Content-Type": "application/json",
}


def apollo_search_page(domains: list[str], page: int, per_page: int = 25) -> dict:
    payload = {
        "organization_domains": domains,
        "person_seniorities": SENIORITIES,
        "page": page,
        "per_page": per_page,
    }
    r = httpx.post(
        f"{APOLLO_BASE}/mixed_people/api_search",
        headers=APOLLO_HEADERS,
        json=payload,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def exa_find_linkedin(first_name: str, company: str) -> str:
    """Search Exa for LinkedIn profile URL."""
    query = f"{first_name} {company} site:linkedin.com/in"
    try:
        r = httpx.post(
            f"{EXA_BASE}/search",
            headers=EXA_HEADERS,
            json={
                "query": query,
                "numResults": 1,
                "type": "auto",
                "includeDomains": ["linkedin.com"],
            },
            timeout=15,
        )
        r.raise_for_status()
        results = r.json().get("results", [])
        for res in results:
            url = res.get("url", "")
            if "/in/" in url:
                # Clean up URL
                match = re.match(r"(https://[a-z.]*linkedin\.com/in/[^/?]+)", url)
                if match:
                    return match.group(1)
    except Exception:
        pass
    return ""


def read_domains(csv_path: str) -> list[str]:
    domains = []
    with open(csv_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            d = row.get("domain", "").strip().lower()
            if d and d not in domains:
                domains.append(d)
    return domains


def run(args):
    print(f"\n  Segment:      {args.segment.upper()}")
    print(f"  Input CSV:    {args.csv}")
    print(f"  Max/domain:   {args.max_per_domain}")
    print(f"  Output:       {args.out}")

    # 1. Read domains
    domains = read_domains(args.csv)
    print(f"\n  Domains loaded: {len(domains)}")

    # 2. Apollo search — batch 1000 at a time, paginate
    per_domain_count: dict[str, int] = defaultdict(int)
    all_people = []

    batch_size = 1000
    domain_batches = [
        domains[i : i + batch_size] for i in range(0, len(domains), batch_size)
    ]

    for batch_idx, batch in enumerate(domain_batches):
        print(
            f"\n  Apollo batch {batch_idx + 1}/{len(domain_batches)} ({len(batch)} domains)..."
        )
        page = 1
        while True:
            try:
                data = apollo_search_page(batch, page=page, per_page=100)
            except Exception as e:
                print(f"    ⚠ Apollo error page {page}: {e}")
                break

            people = data.get("people", [])
            total = data.get("total_entries", 0)
            if page == 1:
                print(f"    Total in Apollo: {total}")

            added = 0
            for p in people:
                org = p.get("organization") or {}
                domain = (org.get("primary_domain") or "").lower().strip()
                if not domain:
                    continue
                if per_domain_count[domain] >= args.max_per_domain:
                    continue
                per_domain_count[domain] += 1
                all_people.append(
                    {
                        "first_name": p.get("first_name", ""),
                        "last_name": "",  # obfuscated, skip
                        "title": p.get("title", ""),
                        "company_name": org.get("name", ""),
                        "domain": domain,
                        "segment": args.segment.upper(),
                        "linkedin_url": "",  # will enrich via Exa
                        "apollo_id": p.get("id", ""),
                        "has_email": p.get("has_email", False),
                    }
                )
                added += 1

            print(f"    Page {page}: {len(people)} fetched, {added} kept")

            # Check if all domains at max capacity or no more pages
            total_fetched = page * 100
            if total_fetched >= total or len(people) < 100:
                break

            # Check if we still have domains that need people
            domains_needing = sum(
                1 for d in batch if per_domain_count[d] < args.max_per_domain
            )
            if domains_needing == 0:
                print("    All domains at max capacity, stopping")
                break

            page += 1
            time.sleep(0.3)  # rate limit

    print(f"\n  Total people collected: {len(all_people)}")

    # 3. Exa LinkedIn enrichment
    print(f"\n  Enriching LinkedIn via Exa ({len(all_people)} people)...")
    found_li = 0
    for i, p in enumerate(all_people):
        if not p["first_name"] or not p["company_name"]:
            continue
        li = exa_find_linkedin(p["first_name"], p["company_name"])
        if li:
            p["linkedin_url"] = li
            found_li += 1
        if (i + 1) % 50 == 0:
            print(f"    {i + 1}/{len(all_people)} done, {found_li} LinkedIn found")
        time.sleep(0.1)  # rate limit

    print(f"  LinkedIn found: {found_li}/{len(all_people)}")

    # 4. Save output CSV (Apollo format for pipeline.py people)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "First Name",
        "Last Name",
        "Title",
        "Company",
        "Website",
        "Person Linkedin Url",
        "Seniority",
        "segment",
        "apollo_id",
    ]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for p in all_people:
            writer.writerow(
                {
                    "First Name": p["first_name"],
                    "Last Name": p["last_name"],
                    "Title": p["title"],
                    "Company": p["company_name"],
                    "Website": p["domain"],
                    "Person Linkedin Url": p["linkedin_url"],
                    "Seniority": "",
                    "segment": p["segment"],
                    "apollo_id": p["apollo_id"],
                }
            )

    print(f"\n  ✓ Saved {len(all_people)} contacts → {out_path}")
    with_li = sum(1 for p in all_people if p["linkedin_url"])
    print(f"    With LinkedIn: {with_li}")
    print(f"    Without LinkedIn: {len(all_people) - with_li}")
    print("\n  Next step:")
    print(f"    scp {out_path} hetzner:~/magnum-opus-project/repo/sofia/input/")
    print(
        "    ssh hetzner 'cd ~/magnum-opus-project/repo && set -a && source .env && set +a && \\"
    )
    print("      python3 -u sofia/scripts/bace/pipeline.py people \\")
    print(f"        --csv sofia/input/{out_path.name} \\")
    print(f"        --project-id 42 --segment {args.segment} --auto-approve'")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="People search: Apollo → Exa → CSV")
    parser.add_argument(
        "--csv", required=True, help="Input targets CSV with domain column"
    )
    parser.add_argument(
        "--segment", required=True, help="Segment slug (affperf/imagency/infplat)"
    )
    parser.add_argument("--max-per-domain", type=int, default=6)
    parser.add_argument("--out", required=True, help="Output CSV path")
    args = parser.parse_args()
    run(args)
