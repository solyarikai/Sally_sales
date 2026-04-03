"""
Export Clay TAM companies to Google Sheets with debug info tab.
Run on Hetzner where google-credentials.json exists.
"""
import json
import os
import sys
from pathlib import Path
from datetime import datetime

# Add backend to path for config
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

import gspread
from google.oauth2.service_account import Credentials


def main():
    # Find credentials
    creds_file = None
    for p in [
        "/app/google-credentials.json",
        str(Path(__file__).parent.parent / "google-credentials.json"),
    ]:
        if os.path.exists(p):
            creds_file = p
            break
    if not creds_file:
        print("ERROR: google-credentials.json not found")
        sys.exit(1)

    # Load data
    exports_dir = Path(__file__).parent / "clay" / "exports"
    companies = json.loads((exports_dir / "tam_companies.json").read_text())
    results_meta = json.loads((exports_dir / "tam_results.json").read_text())

    print(f"Loaded {len(companies)} companies")

    # Auth
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(creds_file, scopes=scopes)
    gc = gspread.authorize(creds)

    # Create spreadsheet
    title = f"Clay TAM Export — Inxy Gaming ({len(companies)} companies)"
    sh = gc.create(title)
    sh.share("", perm_type="anyone", role="reader")
    print(f"Created sheet: {sh.url}")

    # === Main tab: Companies ===
    ws = sh.sheet1
    ws.update_title("Companies")

    columns = ["Name", "Domain", "Description", "Primary Industry", "Size", "Type", "Location", "Country", "LinkedIn URL"]
    rows = [columns]
    for c in companies:
        domain = c.get("Domain", c.get("Find companies", ""))
        row = [
            str(c.get("Name", ""))[:500],
            str(domain)[:200],
            str(c.get("Description", ""))[:500],
            str(c.get("Primary Industry", "")),
            str(c.get("Size", "")),
            str(c.get("Type", "")),
            str(c.get("Location", "")),
            str(c.get("Country", "")),
            str(c.get("LinkedIn URL", "")),
        ]
        rows.append(row)

    # Write in batches
    batch_size = 500
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        ws.update(range_name=f"A{i + 1}", values=batch)
        print(f"  Wrote rows {i + 1}-{i + len(batch)}")

    # Format header
    ws.format("A1:I1", {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.95}})

    # === Debug tab ===
    debug_ws = sh.add_worksheet(title="Debug Info", rows=50, cols=4)

    credits_before = results_meta.get("creditsBefore", {}).get("basic", "?")
    credits_after = results_meta.get("creditsAfter", {}).get("basic", "?")
    credits_spent = (credits_before - credits_after) if isinstance(credits_before, int) and isinstance(credits_after, int) else "?"
    table_url = results_meta.get("tableUrl", "N/A")

    # Count stats
    with_domain = sum(1 for c in companies if c.get("Domain") or c.get("Find companies"))
    with_linkedin = sum(1 for c in companies if c.get("LinkedIn URL"))
    countries = {}
    for c in companies:
        country = c.get("Country", "Unknown")
        countries[country] = countries.get(country, 0) + 1
    industries = {}
    for c in companies:
        ind = c.get("Primary Industry", "Unknown")
        industries[ind] = industries.get(ind, 0) + 1

    debug_rows = [
        ["Parameter", "Value"],
        ["Export Date", datetime.now().strftime("%Y-%m-%d %H:%M")],
        ["Total Companies", str(len(companies))],
        ["With Domain", str(with_domain)],
        ["With LinkedIn URL", str(with_linkedin)],
        ["Credits Before", str(credits_before)],
        ["Credits After", str(credits_after)],
        ["Credits Spent", str(credits_spent)],
        ["Clay Table URL", table_url],
        [""],
        ["ICP Used", results_meta.get("icp", "N/A")],
        [""],
        ["Filters Applied", ""],
    ]

    filters = results_meta.get("filters", {})
    for k, v in filters.items():
        debug_rows.append([f"  {k}", json.dumps(v) if isinstance(v, list) else str(v)])

    debug_rows.append([""])
    debug_rows.append(["Top Countries", "Count"])
    for country, count in sorted(countries.items(), key=lambda x: -x[1])[:20]:
        debug_rows.append([f"  {country}", str(count)])

    debug_rows.append([""])
    debug_rows.append(["Top Industries", "Count"])
    for ind, count in sorted(industries.items(), key=lambda x: -x[1])[:20]:
        debug_rows.append([f"  {ind}", str(count)])

    debug_ws.update(range_name="A1", values=debug_rows)
    debug_ws.format("A1:B1", {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.95, "green": 0.9, "blue": 0.9}})

    print(f"\nDone! Sheet URL: {sh.url}")
    print(f"Clay Table URL: {table_url}")


if __name__ == "__main__":
    main()
