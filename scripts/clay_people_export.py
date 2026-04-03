"""
Clay People Search — extract people at gaming skin/item companies.
Uses Clay internal API directly (session cookie auth, 0 credits).

Combines company lists from:
1. Team's xlsx (87 companies)
2. Clay TAM export (871 companies)
3. Yandex/Google search results (DB project 48)

Cross-matches people with known company domains.
"""
import json
import os
import sys
import time
import openpyxl
import httpx
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime

SESSION_COOKIE = "s%3AsydgrI74YLdGMrU8LWzQSmCv-IrJgDYg.FYCecoCtfmRICI19MVyPsTXRxlfUAfoeKSLns5ofeGw"
WORKSPACE_ID = "889252"
SEARCH_LIMIT = 50  # Clay preview API max (for full results use Puppeteer UI flow)

HEADERS = {
    "Cookie": f"claysession={SESSION_COOKIE}",
    "Accept": "application/json",
    "Content-Type": "application/json",
}

BASE_DIR = Path(__file__).parent
EXPORTS_DIR = BASE_DIR / "clay" / "exports"


def load_known_domains():
    """Load all known gaming ICP domains from xlsx + Clay TAM."""
    domains = {}  # domain -> {name, source, ...}

    # 1. Team xlsx
    xlsx_path = BASE_DIR.parent / "tasks" / "inxy" / "skin_sites_all.xlsx"
    if xlsx_path.exists():
        wb = openpyxl.load_workbook(str(xlsx_path), read_only=True)
        ws = wb["Все сайты (87)"]
        for row in list(ws.iter_rows(values_only=True))[1:]:
            name, url, game, typ, notes, email, priority = row
            if url:
                domain = urlparse(url).netloc or url.replace("https://", "").replace("http://", "").split("/")[0]
                domain = domain.lower().strip().rstrip("/")
                if domain.startswith("www."):
                    domain = domain[4:]
                domains[domain] = {
                    "name": name, "source": "team_xlsx", "game": game,
                    "type": typ, "priority": priority,
                }
        print(f"  xlsx: {len(domains)} domains")

    # 2. Data pipeline (Yandex + Google + Apollo) — already filtered for gaming ICP
    pipeline_csv = BASE_DIR / "clay" / "inxy_gaming_companies.csv"
    if pipeline_csv.exists():
        added = 0
        with open(pipeline_csv) as f:
            for line in f:
                d = line.strip().lower()
                if d and d != "website" and "." in d:
                    if d.startswith("www."):
                        d = d[4:]
                    if d not in domains:
                        domains[d] = {"name": "", "source": "data_pipeline"}
                        added += 1
        print(f"  Pipeline CSV: +{added} new domains (total: {len(domains)})")

    # 3. Clay TAM (has noise — only use as supplementary)
    clay_file = EXPORTS_DIR / "tam_companies.json"
    if clay_file.exists():
        companies = json.loads(clay_file.read_text())
        added = 0
        for c in companies:
            d = c.get("Domain", "") or ""
            if d:
                d = d.lower().strip().rstrip("/")
                if d.startswith("www."):
                    d = d[4:]
                if d not in domains:
                    domains[d] = {
                        "name": c.get("Name", ""),
                        "source": "clay_tam",
                        "industry": c.get("Primary Industry", ""),
                    }
                    added += 1
        print(f"  Clay TAM: +{added} new domains (total: {len(domains)})")

    return domains


def search_people(client, filters, limit=SEARCH_LIMIT):
    """Run Clay People search. Returns (people_list, total_count)."""
    payload = {
        "workspaceId": WORKSPACE_ID,
        "enrichmentType": "find-lists-of-people-with-mixrank-source-preview",
        "options": {"sync": True, "returnTaskId": True, "returnActionMetadata": True},
        "inputs": {**filters, "limit": limit, "result_count": True},
    }

    resp = client.post(
        "https://api.clay.com/v3/actions/run-enrichment",
        json=payload,
        headers=HEADERS,
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()

    result = data.get("result") or {}
    people = result.get("people", [])
    count = result.get("peopleCount", len(people))

    # Check for errors
    meta = data.get("metadata", {})
    status = meta.get("status", "")
    if status and "ERROR" in status:
        print(f"  ERROR: {meta.get('message', status)}")
        return [], 0

    # Check credits
    upfront = meta.get("upfrontCreditUsage", {})
    cost = upfront.get("totalCost", 0)
    if cost > 0:
        print(f"  WARNING: {cost} credits used!")

    return people, count


def main():
    print("=== Clay People Export — Gaming Skins ICP ===\n")

    # Check credits before
    print("[1] Checking credits...")
    with httpx.Client() as client:
        resp = client.get(
            f"https://api.clay.com/v3/subscriptions/{WORKSPACE_ID}",
            headers=HEADERS, timeout=15,
        )
        credits_before = resp.json().get("creditBalances", {})
        print(f"  Credits before: {json.dumps(credits_before)}")

    # Load known domains
    print("\n[2] Loading known company domains...")
    known_domains = load_known_domains()
    print(f"  Total known domains: {len(known_domains)}")

    # People search with gaming ICP filters
    print("\n[3] Searching Clay for people at gaming companies...")

    # Search strategy: multiple focused queries to maximize relevant results
    search_configs = [
        {
            "label": "Gaming skins/marketplace (decision makers)",
            "filters": {
                "company_industries": ["Online gaming", "Computer games"],
                "company_description_keywords": ["skins", "CS2", "CSGO", "Dota2", "gaming marketplace", "virtual items", "loot boxes", "skin trading"],
                "job_title_keywords": ["CEO", "Founder", "Co-Founder", "CTO", "CFO", "COO", "VP", "Head of", "Director", "Chief", "Managing Director", "President", "Owner"],
            },
        },
        {
            "label": "Gaming skins/marketplace (all roles)",
            "filters": {
                "company_industries": ["Online gaming", "Computer games"],
                "company_description_keywords": ["skins", "CS2", "CSGO", "Dota2", "gaming marketplace", "virtual items", "loot boxes", "skin trading"],
            },
        },
        {
            "label": "E-commerce gaming (decision makers)",
            "filters": {
                "company_industries": ["E-commerce"],
                "company_description_keywords": ["gaming", "skins", "CS2", "CSGO", "esports", "virtual items", "game items"],
                "job_title_keywords": ["CEO", "Founder", "Co-Founder", "CTO", "CFO", "COO", "VP", "Head of", "Director", "Chief", "Managing Director"],
            },
        },
    ]

    all_people = {}  # profile_id -> person data (dedup)

    with httpx.Client() as client:
        for config in search_configs:
            label = config["label"]
            print(f"\n  Search: {label}")
            people, total_count = search_people(client, config["filters"], limit=SEARCH_LIMIT)
            print(f"    Total available: {total_count}, fetched: {len(people)}")

            new = 0
            for p in people:
                pid = p.get("profile_id")
                if pid and pid not in all_people:
                    all_people[pid] = p
                    new += 1
            print(f"    New unique: {new} (total unique: {len(all_people)})")

            time.sleep(2)  # Be nice

    print(f"\n  Total unique people: {len(all_people)}")

    # Match against known domains
    print("\n[4] Matching people against known company domains...")
    matched = []
    unmatched = []

    for person in all_people.values():
        domain = person.get("domain", "")
        if domain:
            domain = domain.lower().strip()
            if domain.startswith("www."):
                domain = domain[4:]

        company_info = known_domains.get(domain, {})
        person_out = {
            "first_name": person.get("first_name", ""),
            "last_name": person.get("last_name", ""),
            "full_name": person.get("name", ""),
            "title": person.get("latest_experience_title", ""),
            "company": person.get("latest_experience_company", ""),
            "domain": domain,
            "linkedin_url": person.get("url", ""),
            "location": person.get("location_name", ""),
            "start_date": person.get("latest_experience_start_date", ""),
            "source_match": company_info.get("source", "clay_people_search"),
            "company_game": company_info.get("game", ""),
            "company_type": company_info.get("type", ""),
            "company_priority": company_info.get("priority", ""),
        }

        if domain in known_domains:
            matched.append(person_out)
        else:
            unmatched.append(person_out)

    print(f"  Matched (in known companies): {len(matched)}")
    print(f"  Unmatched (new gaming companies): {len(unmatched)}")

    # Check credits after
    print("\n[5] Checking credits after...")
    with httpx.Client() as client:
        resp = client.get(
            f"https://api.clay.com/v3/subscriptions/{WORKSPACE_ID}",
            headers=HEADERS, timeout=15,
        )
        credits_after = resp.json().get("creditBalances", {})
        print(f"  Credits after: {json.dumps(credits_after)}")

        basic_before = credits_before.get("basic", 0)
        basic_after = credits_after.get("basic", 0)
        spent = basic_before - basic_after
        print(f"  Credits spent: {spent}")
        if spent > 0:
            print("  WARNING: Credits were spent!")

    # Save results
    print("\n[6] Saving results...")
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # All people (matched first, then unmatched)
    all_export = matched + unmatched
    (EXPORTS_DIR / "people_all.json").write_text(json.dumps(all_export, indent=2, ensure_ascii=False))
    (EXPORTS_DIR / "people_matched.json").write_text(json.dumps(matched, indent=2, ensure_ascii=False))
    (EXPORTS_DIR / "people_unmatched.json").write_text(json.dumps(unmatched, indent=2, ensure_ascii=False))
    print(f"  Saved {len(all_export)} total ({len(matched)} matched, {len(unmatched)} unmatched)")

    # Save metadata
    (EXPORTS_DIR / "people_meta.json").write_text(json.dumps({
        "timestamp": datetime.now().isoformat(),
        "total_people": len(all_export),
        "matched": len(matched),
        "unmatched": len(unmatched),
        "known_domains": len(known_domains),
        "credits_before": credits_before,
        "credits_after": credits_after,
        "credits_spent": spent,
        "searches": [c["label"] for c in search_configs],
    }, indent=2))

    # Summary stats
    print("\n=== Summary ===")
    print(f"Total people found: {len(all_export)}")
    print(f"  At known ICP companies: {len(matched)}")
    print(f"  At new gaming companies: {len(unmatched)}")
    print(f"Credits spent: {spent}")

    # Top companies by people count
    company_counts = {}
    for p in all_export:
        company_counts[p["company"]] = company_counts.get(p["company"], 0) + 1
    print(f"\nTop companies by people:")
    for company, count in sorted(company_counts.items(), key=lambda x: -x[1])[:15]:
        print(f"  {company}: {count}")


if __name__ == "__main__":
    main()
