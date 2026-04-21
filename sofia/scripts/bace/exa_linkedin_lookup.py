#!/usr/bin/env python3
"""
Exa LinkedIn lookup for Apollo people CSV.
Reads existing apollo_people_*.csv, adds LinkedIn URLs via Exa, writes enriched CSV.

Usage:
    python3 exa_linkedin_lookup.py <input.csv> [output.csv]
"""

import csv
import os
import sys
import time

import httpx

EXA_BASE = "https://api.exa.ai"
_EXA_KEYS = [
    os.environ.get("EXA_API_KEY", "39f2648c-681a-460f-ac5b-bd04d8c468a4"),
    "197fc32a-3563-4e29-bdb1-5f5a796034c9",
    "39f2648c-681a-460f-ac5b-bd04d8c468a4",
    "a4f6a3c4-5000-4d55-8a06-0f345487e27c",
]
_exa_key_idx = 0


def exa_find_linkedin(
    first: str, last: str, title: str, company: str
) -> tuple[str, float]:
    global _exa_key_idx
    query = f"{first} {last} {title} {company} site:linkedin.com/in"
    for _ in range(len(_EXA_KEYS)):
        key = _EXA_KEYS[_exa_key_idx]
        try:
            r = httpx.post(
                f"{EXA_BASE}/search",
                headers={"x-api-key": key, "Content-Type": "application/json"},
                json={
                    "query": query,
                    "numResults": 1,
                    "type": "neural",
                    "includeDomains": ["linkedin.com"],
                },
                timeout=15,
            )
            if r.status_code == 402:
                print(f"  ⚠ Exa key [{_exa_key_idx}] exhausted → rotating")
                _exa_key_idx = (_exa_key_idx + 1) % len(_EXA_KEYS)
                continue
            if r.status_code != 200:
                return "", 0.0
            data = r.json()
            results = data.get("results", [])
            cost = data.get("costDollars", {}).get("total", 0.0)
            if results:
                url = results[0].get("url", "")
                if "/in/" in url:
                    return url, cost
            return "", cost
        except Exception as e:
            print(f"  ✗ Exa error: {e}")
            return "", 0.0
    print("  ✗ All Exa keys exhausted")
    return "", 0.0


def main():
    if len(sys.argv) < 2:
        print("Usage: exa_linkedin_lookup.py <input.csv> [output.csv]")
        sys.exit(1)

    in_path = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) > 2 else in_path.replace(".csv", "_exa.csv")

    rows = []
    with open(in_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames or []

    if "Person Linkedin Url" not in fieldnames:
        fieldnames = list(fieldnames) + ["Person Linkedin Url"]

    total = len(rows)
    found = 0
    total_cost = 0.0

    print(f"Exa LinkedIn lookup: {total} people from {in_path}")
    print(f"Output → {out_path}\n")

    for i, row in enumerate(rows, 1):
        # Skip if already has LinkedIn
        if row.get("Person Linkedin Url"):
            found += 1
            if i % 20 == 0 or i == total:
                print(f"  {i}/{total} | found: {found} | cost: ${total_cost:.3f}")
            continue

        first = row.get("First Name", "")
        last = row.get("Last Name", "")
        title = row.get("Title", "")
        company = row.get("Company", "") or row.get("Website", "")

        li_url, cost = exa_find_linkedin(first, last, title, company)
        total_cost += cost
        row["Person Linkedin Url"] = li_url
        if li_url:
            found += 1

        if i % 20 == 0 or i == total:
            print(f"  {i}/{total} | found: {found} | cost: ${total_cost:.3f}")

        time.sleep(0.15)

    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    print(
        f"\n✓ Done: {found}/{total} LinkedIn URLs found | Total cost: ${total_cost:.3f}"
    )
    print(f"✓ Saved → {out_path}")


if __name__ == "__main__":
    main()
