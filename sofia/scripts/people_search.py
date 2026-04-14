#!/usr/bin/env python3.11
"""
People search via Exa: company domain → LinkedIn profiles of decision-makers.

For each company in the targets CSV, searches Exa for LinkedIn profiles
of C-suite / VP / Director / Founder.

Output: Apollo-format CSV ready for `pipeline.py people --csv`.

Usage:
    python3.11 sofia/scripts/people_search.py \
        --csv sofia/output/.../OS_Targets_AFFILIATE_PERFORMANCE_2026-04-13.csv \
        --segment affperf \
        --out sofia/input/OS_People_AFFPERF_2026-04-14.csv

    # All 3 segments:
    for seg in AFFPERF IMAGENCY INFPLAT; do
      python3.11 sofia/scripts/people_search.py \
        --csv "sofia/output/OnSocial/pipeline/affperf_2026-04-13/_master/OS_Targets_${seg}_2026-04-13.csv" \
        --segment $(echo $seg | tr '[:upper:]' '[:lower:]') \
        --out sofia/input/OS_People_${seg}_2026-04-14.csv &
    done
    wait
"""

import argparse
import csv
import json
import os
import re
import time
from pathlib import Path

import httpx

EXA_API_KEY = os.environ.get("EXA_API_KEY", "197fc32a-3563-4e29-bdb1-5f5a796034c9")
EXA_BASE = "https://api.exa.ai"
EXA_HEADERS = {"x-api-key": EXA_API_KEY, "Content-Type": "application/json"}

MAX_PER_DOMAIN = 6
RATE_LIMIT_SLEEP = 0.15  # ~6 req/s


def exa_search(query: str, num_results: int = 6) -> list[dict]:
    """Search Exa for LinkedIn profiles, return list of {url, title, text}."""
    try:
        r = httpx.post(
            f"{EXA_BASE}/search",
            headers=EXA_HEADERS,
            json={
                "query": query,
                "numResults": num_results,
                "type": "neural",
                "category": "people",
                "includeDomains": ["linkedin.com"],
                "contents": {"text": {"maxCharacters": 300}},
            },
            timeout=20,
        )
        r.raise_for_status()
        return r.json().get("results", [])
    except Exception:
        return []


def parse_linkedin_person(result: dict) -> dict | None:
    """Extract person info from an Exa LinkedIn result."""
    url = result.get("url", "")
    # Only /in/ profiles, not /company/ or /posts/
    if "linkedin.com/in/" not in url:
        return None

    # Normalize URL: strip query params
    match = re.match(r"(https://[a-z.]*linkedin\.com/in/[^/?#]+)", url)
    if not match:
        return None
    linkedin_url = match.group(1)

    # Parse name + title from result title
    # Common format: "Name - Title at Company | LinkedIn"
    title_raw = result.get("title", "")
    name, job_title = "", ""
    m = re.match(r"^([^|–\-]+?)[\s]*[-–|][\s]*(.+?)(?:\s*\|\s*LinkedIn)?$", title_raw)
    if m:
        name = m.group(1).strip()
        job_title = m.group(2).strip()
        # Remove "at CompanyName" suffix from job title
        job_title = re.sub(r"\s+(?:at|@)\s+.+$", "", job_title, flags=re.IGNORECASE)
    else:
        name = title_raw.replace("| LinkedIn", "").strip()

    parts = name.split()
    first_name = parts[0] if parts else ""
    last_name = " ".join(parts[1:]) if len(parts) > 1 else ""

    # Skip obvious non-persons (company pages, job listings)
    skip_words = ["jobs", "company", "careers", "group", "llc", "ltd", "inc", "corp"]
    if any(w in name.lower() for w in skip_words):
        return None
    if not first_name or len(first_name) < 2:
        return None

    return {
        "first_name": first_name,
        "last_name": last_name,
        "title": job_title,
        "linkedin_url": linkedin_url,
    }


def read_companies(csv_path: str) -> list[dict]:
    """Read unique companies from targets CSV."""
    seen = set()
    companies = []
    with open(csv_path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            domain = row.get("domain", "").strip().lower()
            name = row.get("company_name", "").strip()
            if not domain or domain in seen:
                continue
            seen.add(domain)
            companies.append({"domain": domain, "company_name": name or domain})
    return companies


def run(args):
    base = args.csv.split("/")[-1]
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Load checkpoint if exists (resume support)
    checkpoint_path = out_path.with_suffix(".checkpoint.json")
    done_domains: set[str] = set()
    all_people: list[dict] = []
    if checkpoint_path.exists():
        with open(checkpoint_path) as f:
            ckpt = json.load(f)
            done_domains = set(ckpt.get("done", []))
            all_people = ckpt.get("people", [])
        print(
            f"  Resuming: {len(done_domains)} domains done, {len(all_people)} people so far"
        )

    companies = read_companies(args.csv)
    remaining = [c for c in companies if c["domain"] not in done_domains]

    print(f"\n  Segment:    {args.segment.upper()}")
    print(f"  Companies:  {len(companies)} total, {len(remaining)} remaining")
    print(f"  Max/domain: {args.max_per_domain}")
    print(f"  Output:     {out_path}\n")

    segment_name = args.segment.upper()
    # Map slug to full segment name
    seg_map = {
        "affperf": "AFFILIATE_PERFORMANCE",
        "imagency": "IM_FIRST_AGENCIES",
        "infplat": "INFLUENCER_PLATFORMS",
        "soccom": "SOCIAL_COMMERCE",
    }
    segment_full = seg_map.get(args.segment.lower(), segment_name)

    for i, company in enumerate(remaining):
        domain = company["domain"]
        cname = company["company_name"]

        # Exa query: find decision-makers at this company on LinkedIn
        query = (
            f"CEO OR founder OR CTO OR CMO OR VP OR director OR head "
            f'"{cname}" linkedin profile'
        )
        results = exa_search(query, num_results=args.max_per_domain + 2)

        added = 0
        seen_li = set()
        for res in results:
            if added >= args.max_per_domain:
                break
            person = parse_linkedin_person(res)
            if not person:
                continue
            if person["linkedin_url"] in seen_li:
                continue
            seen_li.add(person["linkedin_url"])
            all_people.append(
                {
                    **person,
                    "domain": domain,
                    "company_name": cname,
                    "segment": segment_full,
                }
            )
            added += 1

        done_domains.add(domain)

        # Progress + checkpoint every 50
        if (i + 1) % 50 == 0 or (i + 1) == len(remaining):
            total = len(done_domains) + len(
                [
                    c
                    for c in companies
                    if c["domain"] in done_domains and c not in remaining
                ]
            )
            print(
                f"  [{i + 1}/{len(remaining)}] {domain} → {added} people | total: {len(all_people)}"
            )
            with open(checkpoint_path, "w") as f:
                json.dump({"done": list(done_domains), "people": all_people}, f)
        elif (i + 1) % 10 == 0:
            print(
                f"  [{i + 1}/{len(remaining)}] {domain} → {added} people | total: {len(all_people)}"
            )

        time.sleep(RATE_LIMIT_SLEEP)

    # Write final CSV
    fieldnames = [
        "First Name",
        "Last Name",
        "Title",
        "Company",
        "Website",
        "Person Linkedin Url",
        "segment",
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
                    "segment": p["segment"],
                }
            )

    with_li = sum(1 for p in all_people if p["linkedin_url"])
    print(f"\n  ✓ Done: {len(all_people)} people → {out_path}")
    print(f"    With LinkedIn: {with_li} | Without: {len(all_people) - with_li}")

    # Cleanup checkpoint
    if checkpoint_path.exists():
        checkpoint_path.unlink()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    parser.add_argument("--segment", required=True)
    parser.add_argument("--max-per-domain", type=int, default=MAX_PER_DOMAIN)
    parser.add_argument("--out", required=True)
    run(parser.parse_args())
