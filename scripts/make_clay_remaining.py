#!/usr/bin/env python3
"""
Generate domain list for Clay People Search — remaining domains not yet searched.

Reads all unique domains from Google Sheet corridor tab,
subtracts domains already in Clay exports,
writes remaining to CSV for clay_people_search.js.

Usage (inside Docker on server):
  python3 scripts/make_clay_remaining.py uae-pakistan
  python3 scripts/make_clay_remaining.py au-philippines
  python3 scripts/make_clay_remaining.py arabic-southafrica

Output: /tmp/{corridor}_clay_remaining.csv (one domain per line)
"""
import json
import os
import sys
import glob

from google.oauth2 import service_account
from googleapiclient.discovery import build

SHEET_ID = '1pivHqk1NI-MHdDFSQugfg5olBMKTkBGr_yyjjXlWqKU'
CLAY_EXPORTS_DIR = os.path.expanduser('~/magnum-opus-project/repo/scripts/clay/exports')

SHARED_HOSTING = {
    'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'linkedin.com',
    'facebook.com', 'vercel.app', 'netlify.app', 'herokuapp.com', 'github.io',
    'wordpress.com', 'wixsite.com', 'squarespace.com', 'shopify.com', 'google.com',
    'live.com', 'icloud.com', 'aol.com', 'protonmail.com', 'zoho.com',
}

CORRIDOR_TABS = {
    'uae-pakistan': 'UAE-Pakistan - New Only',
    'au-philippines': 'AU-Philippines - New Only',
    'arabic-southafrica': 'Arabic-SouthAfrica - New Only',
}

CORRIDOR_COUNTRIES = {
    'uae-pakistan': 'Pakistan',
    'au-philippines': 'Philippines',
    'arabic-southafrica': 'South Africa',
}


def load_clay_searched_domains():
    """Load all domains already searched via Clay (from export files)."""
    searched = set()
    for f in glob.glob(os.path.join(CLAY_EXPORTS_DIR, 'people_*.json')):
        try:
            data = json.load(open(f))
            if isinstance(data, list):
                for person in data:
                    d = (person.get('Company Domain') or person.get('company_domain') or '').lower().strip()
                    if d:
                        searched.add(d)
        except Exception:
            pass
    return searched


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 make_clay_remaining.py <corridor>")
        print("Corridors: uae-pakistan, au-philippines, arabic-southafrica")
        return

    corridor = sys.argv[1]
    if corridor not in CORRIDOR_TABS:
        print(f"Unknown corridor: {corridor}")
        return

    tab = CORRIDOR_TABS[corridor]
    country = CORRIDOR_COUNTRIES[corridor]
    slug = corridor.replace('-', '_')

    # Google Sheets
    creds = service_account.Credentials.from_service_account_file(
        '/app/google-credentials.json',
        scopes=['https://www.googleapis.com/auth/spreadsheets']
    ).with_subject('services@getsally.io')
    sheets = build('sheets', 'v4', credentials=creds)

    print(f"Reading domains from '{tab}'...")
    result = sheets.spreadsheets().values().get(
        spreadsheetId=SHEET_ID,
        range=f"'{tab}'!A1:Z20000"
    ).execute()
    rows = result.get('values', [])
    if not rows:
        print("No data in sheet!")
        return

    headers = rows[0]
    dom_idx = headers.index('Domain') if 'Domain' in headers else -1
    if dom_idx < 0:
        print("No 'Domain' column!")
        return

    # Collect unique domains
    all_domains = set()
    for r in rows[1:]:
        if dom_idx < len(r) and r[dom_idx].strip():
            d = r[dom_idx].strip().lower()
            if d not in SHARED_HOSTING:
                all_domains.add(d)

    print(f"Unique domains in sheet: {len(all_domains)}")

    # Subtract already-searched
    searched = load_clay_searched_domains()
    print(f"Already searched by Clay: {len(searched)}")

    remaining = sorted(all_domains - searched)
    print(f"Remaining to search: {len(remaining)}")

    # Write output
    out_file = f'/tmp/{slug}_clay_remaining.csv'
    with open(out_file, 'w') as f:
        for d in remaining:
            f.write(d + '\n')

    print(f"\nWrote {len(remaining)} domains to {out_file}")
    print(f"Batches needed: {(len(remaining) + 199) // 200} (200 domains/batch)")
    print(f"Estimated time: ~{(len(remaining) + 199) // 200 * 3} min")
    print(f"\nTo run Clay search:")
    print(f"  node scripts/clay/clay_people_search.js --domains-file {out_file} --countries \"{country}\" --headless --auto")


if __name__ == '__main__':
    main()
