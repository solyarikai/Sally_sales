#!/usr/bin/env python3
"""
Targets → Contacts pipeline: takes targets.json from enrichment pipeline,
finds decision-maker contacts via Apollo People Search API, enriches them
with email/LinkedIn, and outputs CSV ready for findymail_to_smartlead.py.

Usage:
    python targets_to_contacts.py                                    # all targets
    python targets_to_contacts.py --segments INFLUENCER_PLATFORMS     # one segment
    python targets_to_contacts.py --max-companies 100                # limit
    python targets_to_contacts.py --titles "CEO,CMO,VP Marketing"    # custom titles

Flow:
    targets.json → Apollo search_people (FREE, no credits) → enrich_person (credits)
    → CSV with Name, Email, Title, Company, Profile URL, Company Domain, Segment

Requires: APOLLO_API_KEY env var
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from pathlib import Path

import httpx

# ── Config ────────────────────────────────────────────────────────────────────
SOFIA_DIR = Path(__file__).parent.parent
REPO_DIR = SOFIA_DIR.parent
STATE_DIR = REPO_DIR / "state" / "onsocial"
TARGETS_FILE = STATE_DIR / "targets.json"
CONTACTS_CACHE = STATE_DIR / "contacts_cache.json"

APOLLO_API_KEY = os.environ.get("APOLLO_API_KEY", "")
APOLLO_BASE = "https://api.apollo.io/api/v1"

# ── CSV Naming Convention ─────────────────────────────────────────────────────
PROJECT_CODE = "OS"
CSV_OUTPUT_DIR = SOFIA_DIR / "output" / "OnSocial"
CSV_IMPORT_DIR = CSV_OUTPUT_DIR / "Import"
CSV_IMPORT_DIR.mkdir(parents=True, exist_ok=True)

def _date_tag() -> str:
    from datetime import datetime
    return datetime.now().strftime("%b %d")

# Default target titles (decision-makers for B2B SaaS / agency context)
DEFAULT_TITLES = [
    "CEO", "CTO", "CMO", "COO", "Founder", "Co-Founder",
    "VP Marketing", "VP Partnerships", "VP Growth", "VP Sales",
    "Head of Marketing", "Head of Partnerships", "Head of Growth",
    "Director of Marketing", "Director of Partnerships",
]

DEFAULT_SENIORITIES = ["owner", "founder", "c_suite", "vp", "head", "director"]

MAX_CONTACTS_PER_COMPANY = 3

# Legal suffixes for company name normalization
LEGAL_SUFFIXES = re.compile(
    r'\s*[,.]?\s*(GmbH|Ltd\.?|Limited|LLC|Inc\.?|Corp\.?|SAS|S\.A\.S\.?|'
    r'BV|B\.V\.|NV|N\.V\.|SRL|AB|AS|Oy|KG|AG|OÜ|Pvt\.?\s*Ltd\.?|Pte\.?\s*Ltd\.?|'
    r'S\.A\.|SA|SL|SLU|SpA|Srl|SARL|EIRL|SASU|S\.r\.l\.)\s*$',
    re.IGNORECASE,
)


def normalize_company(name: str) -> str:
    if not name:
        return name
    name = LEGAL_SUFFIXES.sub("", name).strip().rstrip(".,")
    if "-" in name and name == name.lower():
        name = name.replace("-", " ")
    if name == name.lower() and len(name) > 4:
        name = name.title()
    elif name == name.upper() and len(name) > 4:
        name = name.title()
    return name.strip()


def load_json(path: Path):
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data):
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── Apollo API ────────────────────────────────────────────────────────────────

def search_people(domain: str, titles: list[str], seniorities: list[str],
                  per_page: int = 25) -> list[dict]:
    """Search Apollo for people at a company domain. FREE — no credits consumed."""
    try:
        r = httpx.post(
            f"{APOLLO_BASE}/mixed_people/search",
            headers={"Content-Type": "application/json"},
            json={
                "api_key": APOLLO_API_KEY,
                "q_organization_domains": domain,
                "person_titles": titles,
                "person_seniorities": seniorities,
                "page": 1,
                "per_page": per_page,
            },
            timeout=30,
        )
        if r.status_code == 200:
            data = r.json()
            return data.get("people", [])
        elif r.status_code == 429:
            print(f"  Rate limit on search — waiting 60s...")
            time.sleep(60)
            return search_people(domain, titles, seniorities, per_page)
        else:
            print(f"  WARN search {domain}: {r.status_code}")
            return []
    except Exception as e:
        print(f"  ERROR search {domain}: {e}")
        return []


def enrich_person(person_id: str = None, linkedin_url: str = None,
                  first_name: str = None, last_name: str = None,
                  domain: str = None) -> dict:
    """Enrich a person to get email + full details. COSTS credits."""
    payload = {"api_key": APOLLO_API_KEY}
    if person_id:
        payload["id"] = person_id
    elif linkedin_url:
        payload["linkedin_url"] = linkedin_url
    elif first_name and last_name and domain:
        payload["first_name"] = first_name
        payload["last_name"] = last_name
        payload["domain"] = domain
    else:
        return {}

    try:
        r = httpx.post(
            f"{APOLLO_BASE}/people/match",
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        if r.status_code == 200:
            data = r.json()
            person = data.get("person", {})
            return person if person else {}
        elif r.status_code == 429:
            print(f"  Rate limit on enrich — waiting 60s...")
            time.sleep(60)
            return enrich_person(person_id, linkedin_url, first_name, last_name, domain)
        else:
            return {}
    except Exception as e:
        print(f"  ERROR enrich: {e}")
        return {}


# ── Main pipeline ─────────────────────────────────────────────────────────────

def run(targets: list[dict], titles: list[str], seniorities: list[str],
        max_companies: int, output_csv: Path, skip_enrich: bool = False):
    """Main pipeline: search people → enrich → CSV."""

    # Load contacts cache (to avoid re-processing)
    cache = load_json(CONTACTS_CACHE) or {}
    print(f"Contacts cache: {len(cache)} domains already processed")

    all_contacts = []
    new_processed = 0

    for i, target in enumerate(targets[:max_companies], 1):
        domain = target["domain"]
        segment = target.get("segment", "UNKNOWN")
        company_name = normalize_company(target.get("company_name", domain))

        if domain in cache:
            # Use cached contacts
            all_contacts.extend(cache[domain])
            continue

        print(f"[{i}/{min(max_companies, len(targets))}] {domain} ({segment})")

        # Step 1: Search people (FREE)
        people = search_people(domain, titles, seniorities)
        if not people:
            print(f"  No people found")
            cache[domain] = []
            new_processed += 1
            if new_processed % 50 == 0:
                save_json(CONTACTS_CACHE, cache)
            time.sleep(0.3)
            continue

        # Limit contacts per company
        people = people[:MAX_CONTACTS_PER_COMPANY]
        print(f"  Found {len(people)} people")

        contacts_for_domain = []

        for person in people:
            first_name = person.get("first_name", "")
            last_name = person.get("last_name", "")
            title = person.get("title", "")
            linkedin_url = person.get("linkedin_url", "")
            email = person.get("email", "")

            # Step 2: Enrich if needed (COSTS credits)
            if not skip_enrich and not email:
                enriched = enrich_person(
                    person_id=person.get("id"),
                    linkedin_url=linkedin_url,
                    first_name=first_name,
                    last_name=last_name,
                    domain=domain,
                )
                if enriched:
                    email = enriched.get("email", "")
                    linkedin_url = linkedin_url or enriched.get("linkedin_url", "")
                    first_name = enriched.get("first_name", first_name)
                    last_name = enriched.get("last_name", last_name)
                    title = enriched.get("title", title)
                time.sleep(0.5)

            contact = {
                "Name": f"{first_name} {last_name}".strip(),
                "Email": email or "",
                "Title": title,
                "Company": company_name,
                "Company Domain": domain,
                "Segment": segment,
                "Profile URL": linkedin_url or "",
                "Location": person.get("city", ""),
                "Country": target.get("country", ""),
                "Employees": target.get("employees", ""),
                "Signal Count": target.get("signal_count", 0),
            }
            contacts_for_domain.append(contact)
            all_contacts.append(contact)

            if email:
                print(f"    ✓ {first_name} {last_name} ({title}) → {email}")
            else:
                print(f"    ○ {first_name} {last_name} ({title}) — no email")

        cache[domain] = contacts_for_domain
        new_processed += 1

        if new_processed % 50 == 0:
            save_json(CONTACTS_CACHE, cache)

        time.sleep(0.3)  # Rate limiting

    # Save cache
    save_json(CONTACTS_CACHE, cache)

    # Write CSV
    if not all_contacts:
        print("\nNo contacts found.")
        return

    fieldnames = list(all_contacts[0].keys())
    with output_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_contacts)

    with_email = sum(1 for c in all_contacts if c.get("Email"))
    without_email = len(all_contacts) - with_email
    companies_hit = len(set(c["Company Domain"] for c in all_contacts))

    print(f"\n=== DONE ===")
    print(f"Companies processed:  {min(max_companies, len(targets))}")
    print(f"Companies with hits:  {companies_hit}")
    print(f"Total contacts:       {len(all_contacts)}")
    print(f"  With email:         {with_email}")
    print(f"  Without email:      {without_email} → use findymail_to_smartlead.py")
    print(f"Output: {output_csv}")

    # Also write a filtered CSV for Findymail (contacts with LinkedIn URL but no email)
    without_email_contacts = [c for c in all_contacts if not c.get("Email") and c.get("Profile URL")]
    if without_email_contacts:
        fm_csv = output_csv.parent / (output_csv.stem + " - for_findymail.csv")
        with fm_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(without_email_contacts)
        print(f"Findymail input: {fm_csv} ({len(without_email_contacts)} contacts)")


def main():
    parser = argparse.ArgumentParser(description="Targets → Contacts via Apollo API")
    parser.add_argument("--targets", type=str, default=str(TARGETS_FILE),
                        help="Path to targets.json (default: state/onsocial/targets.json)")
    parser.add_argument("--segments", type=str, default=None,
                        help="Comma-separated segments to process (default: all)")
    parser.add_argument("--max-companies", type=int, default=500,
                        help="Max companies to process (default: 500)")
    parser.add_argument("--titles", type=str, default=None,
                        help="Comma-separated job titles (default: CEO,CMO,VP,...)")
    parser.add_argument("--output", type=str, default=None,
                        help="Output CSV path (default: auto-derived)")
    parser.add_argument("--skip-enrich", action="store_true",
                        help="Skip email enrichment (search only, saves credits)")
    args = parser.parse_args()

    if not APOLLO_API_KEY:
        print("ERROR: APOLLO_API_KEY env var not set")
        sys.exit(1)

    targets_path = Path(args.targets)
    targets = load_json(targets_path)
    if not targets:
        print(f"ERROR: No targets found in {targets_path}")
        sys.exit(1)

    # Filter by segments
    if args.segments:
        segments = [s.strip() for s in args.segments.split(",")]
        targets = [t for t in targets if t.get("segment") in segments]
        print(f"Filtered to segments: {segments} → {len(targets)} targets")
    else:
        print(f"All segments: {len(targets)} targets")

    # Sort by signal_count descending (best targets first)
    targets.sort(key=lambda x: x.get("signal_count", 0), reverse=True)

    # Titles
    titles = [t.strip() for t in args.titles.split(",")] if args.titles else DEFAULT_TITLES

    # Output path
    if args.output:
        output_csv = Path(args.output)
    else:
        output_csv = STATE_DIR / "contacts_from_targets.csv"

    print(f"Titles: {titles[:5]}{'...' if len(titles) > 5 else ''}")
    print(f"Max companies: {args.max_companies}")
    print(f"Output: {output_csv}")
    print()

    run(targets, titles, DEFAULT_SENIORITIES, args.max_companies, output_csv,
        skip_enrich=args.skip_enrich)


if __name__ == "__main__":
    main()
