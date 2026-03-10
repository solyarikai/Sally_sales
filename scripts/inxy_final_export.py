"""
Inxy Final Export — max 5 contacts per office per company.
Merges Clay people + DB extracted_contacts, filters to gaming ICP only.
Exports to Google Sheet.
"""
import asyncio
import json
import re
import os
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, "/app")

SHEET_ID = "15jXVpCeOQ4jlnbFKyfgvpxuRWi-44RdIzpuzNUc8mE0"
MAX_PER_OFFICE = 5

# Decision-maker title keywords (for prioritization)
DM_KEYWORDS = [
    "ceo", "cto", "cfo", "coo", "cmo", "cpo", "cro", "cio",
    "founder", "co-founder", "cofounder",
    "owner", "partner",
    "president", "vp", "vice president",
    "director", "head of", "head",
    "general manager", "managing director",
    "chief",
]


def is_decision_maker(title: str) -> bool:
    if not title:
        return False
    t = title.lower()
    return any(kw in t for kw in DM_KEYWORDS)


def normalize_location(loc: str) -> str:
    """Normalize location to city-level grouping, merging variants."""
    if not loc:
        return "Unknown"

    loc_lower = loc.lower().strip()

    # Direct mapping for known patterns
    city_map = {
        # Netherlands / Amsterdam
        "nederland": "Amsterdam, NL",
        "netherlands": "Amsterdam, NL",
        "amsterdam": "Amsterdam, NL",
        "north holland": "Amsterdam, NL",
        "noord-holland": "Amsterdam, NL",
        # Cyprus / Limassol
        "limassol": "Limassol, CY",
        "cyprus": "Limassol, CY",
        # Serbia / Belgrade
        "belgrade": "Belgrade, RS",
        "serbia": "Belgrade, RS",
        # Armenia / Yerevan
        "yerevan": "Yerevan, AM",
        "armenia": "Yerevan, AM",
        # Georgia / Tbilisi
        "tbilisi": "Tbilisi, GE",
        "georgia": "Tbilisi, GE",
        # Russia / Moscow
        "москва": "Moscow, RU",
        "россия": "Russia",
        "russia": "Russia",
        "moscow": "Moscow, RU",
        # Malta
        "malta": "Malta",
        # Minsk
        "minsk": "Minsk, BY",
        "belarus": "Minsk, BY",
        # Jakarta / Indonesia
        "jakarta": "Jakarta, ID",
        "indonesia": "Jakarta, ID",
        # Bogota / Colombia
        "bogota": "Bogota, CO",
        "bogotá": "Bogota, CO",
        "colombia": "Colombia",
        # São Paulo / Brazil
        "são paulo": "São Paulo, BR",
        "sao paulo": "São Paulo, BR",
        "brazil": "Brazil",
        # Tallinn / Estonia
        "tallinn": "Tallinn, EE",
        "estonia": "Tallinn, EE",
        # Warsaw / Poland
        "warsaw": "Warsaw, PL",
        "poland": "Warsaw, PL",
        # UK
        "united kingdom": "UK",
        "england": "UK",
        # Philippines
        "philippines": "Philippines",
        "metro manila": "Manila, PH",
        # Portugal
        "portugal": "Portugal",
        # Bulgaria / Sofia
        "sofia": "Sofia, BG",
        "bulgaria": "Sofia, BG",
        # Italy / Rome
        "rome": "Rome, IT",
        "italy": "Italy",
        # France
        "lyon": "Lyon, FR",
        "paris": "Paris, FR",
        "france": "France",
        # India
        "mumbai": "Mumbai, IN",
        "bengaluru": "Bengaluru, IN",
        "bangalore": "Bengaluru, IN",
        "india": "India",
        # Australia
        "australia": "Australia",
        # US
        "united states": "USA",
        # South Africa
        "johannesburg": "Johannesburg, ZA",
        "south africa": "South Africa",
        # Ukraine
        "ukraine": "Ukraine",
        "kyiv": "Kyiv, UA",
        # Hong Kong
        "hong kong": "Hong Kong",
        # Germany
        "germany": "Germany",
        # Sweden
        "sweden": "Sweden",
        # Kenya
        "kenya": "Kenya",
        # Ghana
        "accra": "Accra, GH",
        # Peru
        "peru": "Peru",
    }

    # Check each part of the location string against our map
    parts = [p.strip() for p in loc.split(",")]
    for part in parts:
        part_lower = part.strip().lower()
        for pattern, normalized in city_map.items():
            if pattern in part_lower:
                return normalized

    # Fallback: return first part cleaned up
    return parts[0].strip()


def normalize_company(name: str) -> str:
    """Normalize company name for grouping."""
    if not name:
        return ""
    # Group MY.GAMES variants
    if re.search(r"my\.?games", name, re.IGNORECASE):
        return "MY.GAMES"
    # Group itemku variants
    if re.search(r"itemku|five\s*jack|fivejack", name, re.IGNORECASE):
        return "itemku"
    # Group Sportcast variants
    if re.search(r"sportcast", name, re.IGNORECASE):
        return "SportCast"
    return name


async def main():
    # 1. Load Clay people
    clay_path = Path("/scripts/clay/exports/people_gaming_final.json")
    if not clay_path.exists():
        clay_path = Path("/home/leadokol/magnum-opus-project/repo/scripts/clay/exports/people_gaming_final.json")

    clay_people = []
    if clay_path.exists():
        with open(clay_path) as f:
            clay_people = json.load(f)
        print(f"Loaded {len(clay_people)} Clay people")
    else:
        print("WARNING: Clay people file not found")

    # 2. Load DB contacts
    from app.db import async_session_maker
    from sqlalchemy import text

    db_contacts = []
    gaming_domains = set()

    async with async_session_maker() as session:
        # Get all gaming-relevant domains
        r = await session.execute(text("""
            SELECT dc.domain, dc.name, dc.matched_segment, dc.reasoning
            FROM discovered_companies dc
            WHERE dc.project_id = 48 AND dc.is_target = true
              AND (dc.matched_segment IN ('team_confirmed', 'gaming', 'gaming_top_up', 'not_target')
                   OR dc.reasoning LIKE '%RECLASSIFIED%'
                   OR dc.reasoning LIKE '%gaming%'
                   OR dc.reasoning LIKE '%skin%'
                   OR dc.reasoning LIKE '%digital gaming%')
        """))
        for row in r.all():
            gaming_domains.add(row[0].lower())

        print(f"Gaming domains from DB: {len(gaming_domains)}")

        # Get DB extracted contacts at gaming companies
        r = await session.execute(text("""
            SELECT ec.first_name, ec.last_name, ec.email, ec.phone,
                   ec.job_title, ec.linkedin_url, ec.source,
                   dc.domain, dc.name
            FROM extracted_contacts ec
            JOIN discovered_companies dc ON ec.discovered_company_id = dc.id
            WHERE dc.project_id = 48 AND dc.is_target = true
              AND (dc.matched_segment IN ('team_confirmed', 'gaming', 'gaming_top_up', 'not_target')
                   OR dc.reasoning LIKE '%RECLASSIFIED%'
                   OR dc.reasoning LIKE '%gaming%'
                   OR dc.reasoning LIKE '%skin%'
                   OR dc.reasoning LIKE '%digital gaming%')
        """))
        for row in r.all():
            db_contacts.append({
                "first_name": row[0] or "",
                "last_name": row[1] or "",
                "full_name": f"{row[0] or ''} {row[1] or ''}".strip(),
                "email": row[2] or "",
                "phone": row[3] or "",
                "title": row[4] or "",
                "linkedin": row[5] or "",
                "source": f"db_{row[6] or 'unknown'}",
                "domain": row[7] or "",
                "company": row[8] or row[7] or "",
                "location": "",
            })

        print(f"DB contacts at gaming companies: {len(db_contacts)}")

    # 3. Merge all contacts
    all_contacts = []
    seen_keys = set()

    def contact_key(c):
        """Dedup key: linkedin > email > name+company."""
        if c.get("linkedin"):
            return f"li:{c['linkedin'].lower().rstrip('/')}"
        if c.get("email"):
            return f"em:{c['email'].lower()}"
        name = c.get("full_name", "").strip().lower()
        comp = normalize_company(c.get("company", "")).lower()
        if name and comp:
            return f"nc:{name}@{comp}"
        return None

    # Add Clay people first (they have location data)
    for p in clay_people:
        domain = (p.get("domain") or "").lower()
        # Filter to gaming domains
        if domain and domain not in gaming_domains:
            # Check if it's a known gaming domain by keyword
            gaming_kws = ["skin", "csgo", "cs2", "dota", "game", "loot", "case",
                          "roll", "trade", "buff", "steam", "rust", "clash", "item",
                          "bet", "drop", "swap", "howl", "plunder", "hell", "farm",
                          "key-drop", "datdrop", "chicken", "thunder", "rain",
                          "roobet", "duelbits", "gamdom", "stake"]
            if not any(kw in domain for kw in gaming_kws):
                continue

        key = contact_key(p)
        if key and key in seen_keys:
            continue
        if key:
            seen_keys.add(key)

        all_contacts.append({
            "full_name": p.get("full_name", ""),
            "first_name": p.get("first_name", ""),
            "last_name": p.get("last_name", ""),
            "title": p.get("title", ""),
            "email": "",
            "phone": "",
            "company": normalize_company(p.get("company", "")),
            "domain": p.get("domain", ""),
            "linkedin": p.get("linkedin", ""),
            "location": p.get("location", ""),
            "source": "clay",
        })

    # Add DB contacts (they have emails)
    for c in db_contacts:
        key = contact_key(c)
        if key and key in seen_keys:
            # If already from Clay, merge email into existing
            for existing in all_contacts:
                if contact_key(existing) == key:
                    if c.get("email") and not existing.get("email"):
                        existing["email"] = c["email"]
                    if c.get("phone") and not existing.get("phone"):
                        existing["phone"] = c["phone"]
                    break
            continue
        if key:
            seen_keys.add(key)

        c["company"] = normalize_company(c["company"])
        all_contacts.append(c)

    print(f"Total merged contacts: {len(all_contacts)}")

    # 4. Group by company + normalized location, take max 5 per office
    # Prioritize: decision-makers first, then by having email, then by having linkedin
    groups = defaultdict(list)
    for c in all_contacts:
        company = normalize_company(c.get("company", ""))
        location = normalize_location(c.get("location", ""))
        groups[(company, location)].append(c)

    final_contacts = []
    company_stats = defaultdict(lambda: {"total": 0, "selected": 0, "offices": 0})

    for (company, location), people in sorted(groups.items()):
        # Sort: decision-makers first, then email, then linkedin
        people.sort(key=lambda p: (
            not is_decision_maker(p.get("title", "")),
            not bool(p.get("email")),
            not bool(p.get("linkedin")),
        ))

        selected = people[:MAX_PER_OFFICE]
        final_contacts.extend(selected)

        company_stats[company]["total"] += len(people)
        company_stats[company]["selected"] += len(selected)
        company_stats[company]["offices"] += 1

    print(f"\nFinal contacts after max {MAX_PER_OFFICE}/office: {len(final_contacts)}")
    print(f"Companies: {len(company_stats)}")
    print(f"\nCompany breakdown:")
    for company, stats in sorted(company_stats.items(), key=lambda x: -x[1]["selected"]):
        print(f"  {company:40s} {stats['selected']:3d} selected / {stats['total']:3d} total / {stats['offices']} offices")

    # 5. Also add gaming companies with 0 contacts (for awareness)
    companies_with_contacts = {normalize_company(c["company"]).lower() for c in final_contacts}
    no_contact_domains = []
    for d in sorted(gaming_domains):
        # Check if any contact has this domain
        if not any(c.get("domain", "").lower() == d for c in final_contacts):
            no_contact_domains.append(d)

    print(f"\nGaming domains with 0 contacts: {len(no_contact_domains)}")

    # 6. Export to Google Sheet
    from app.services.google_sheets_service import google_sheets_service

    headers = [
        "Full Name", "First Name", "Last Name", "Job Title",
        "Email", "Phone", "Company", "Domain", "LinkedIn",
        "Location", "Source", "Decision Maker"
    ]

    # Sort final contacts: by company, then DM first, then by name
    final_contacts.sort(key=lambda c: (
        c.get("company", "").lower(),
        not is_decision_maker(c.get("title", "")),
        c.get("full_name", "").lower(),
    ))

    rows = []
    for c in final_contacts:
        rows.append([
            c.get("full_name", ""),
            c.get("first_name", ""),
            c.get("last_name", ""),
            c.get("title", ""),
            c.get("email", ""),
            c.get("phone", ""),
            c.get("company", ""),
            c.get("domain", ""),
            c.get("linkedin", ""),
            c.get("location", ""),
            c.get("source", ""),
            "Yes" if is_decision_maker(c.get("title", "")) else "",
        ])

    # Summary tab
    summary_headers = ["Company", "Domain", "Selected", "Total Available", "Offices", "Decision Makers"]
    summary_rows = []
    for company, stats in sorted(company_stats.items(), key=lambda x: -x[1]["selected"]):
        dm_count = sum(1 for c in final_contacts
                       if normalize_company(c.get("company", "")) == company
                       and is_decision_maker(c.get("title", "")))
        # Find primary domain
        domains = set(c.get("domain", "") for c in final_contacts
                      if normalize_company(c.get("company", "")) == company)
        summary_rows.append([
            company,
            ", ".join(sorted(domains)),
            stats["selected"],
            stats["total"],
            stats["offices"],
            dm_count,
        ])

    # Companies with no contacts tab
    no_contact_headers = ["Domain", "Status"]
    no_contact_rows = [[d, "No contacts found"] for d in no_contact_domains]

    # Write to sheets — create on Shared Drive where service account has access
    service = google_sheets_service
    service._initialize()
    import gspread
    gc = gspread.authorize(service.credentials)

    # Create new sheet on Shared Drive
    shared_drive_id = os.environ.get("SHARED_DRIVE_ID", "0AEvTjlJFlWnZUk9PVA")
    spreadsheet = gc.create("Inxy Gaming — 521 Contacts (max 5 per office)", folder_id=shared_drive_id)
    print(f"Created: https://docs.google.com/spreadsheets/d/{spreadsheet.id}")

    # Clear and write Contacts tab
    dm_count = sum(1 for c in final_contacts if is_decision_maker(c.get("title", "")))
    print(f"\nWriting to Google Sheet {SHEET_ID}...")
    print(f"  Contacts: {len(final_contacts)} ({dm_count} decision-makers)")

    # Get or create worksheets
    existing_sheets = [ws.title for ws in spreadsheet.worksheets()]

    # Contacts sheet
    if "Contacts" in existing_sheets:
        ws = spreadsheet.worksheet("Contacts")
        ws.clear()
    else:
        ws = spreadsheet.add_worksheet("Contacts", rows=len(rows) + 1, cols=len(headers))
    ws.update(range_name="A1", values=[headers] + rows)

    # Summary sheet
    if "Summary" in existing_sheets:
        ws2 = spreadsheet.worksheet("Summary")
        ws2.clear()
    else:
        ws2 = spreadsheet.add_worksheet("Summary", rows=len(summary_rows) + 5, cols=len(summary_headers))

    totals_row = [
        "TOTAL",
        "",
        sum(s["selected"] for s in company_stats.values()),
        sum(s["total"] for s in company_stats.values()),
        sum(s["offices"] for s in company_stats.values()),
        dm_count,
    ]
    ws2.update(range_name="A1", values=[summary_headers] + summary_rows + [totals_row])

    # No contacts sheet
    if "No Contacts" in existing_sheets:
        ws3 = spreadsheet.worksheet("No Contacts")
        ws3.clear()
    else:
        ws3 = spreadsheet.add_worksheet("No Contacts", rows=len(no_contact_rows) + 1, cols=2)
    ws3.update(range_name="A1", values=[no_contact_headers] + no_contact_rows)

    # Remove default Sheet1 if exists
    if "Sheet1" in existing_sheets:
        try:
            spreadsheet.del_worksheet(spreadsheet.worksheet("Sheet1"))
        except Exception:
            pass

    print(f"\nDone! Sheet: https://docs.google.com/spreadsheets/d/{SHEET_ID}")
    print(f"  Contacts tab: {len(final_contacts)} people ({dm_count} DMs)")
    print(f"  Summary tab: {len(summary_rows)} companies")
    print(f"  No Contacts tab: {len(no_contact_rows)} domains without contacts")


if __name__ == "__main__":
    asyncio.run(main())
