#!/usr/bin/env python3
"""
Upload ALL gathered contacts from Clay/Apollo to Google Sheet.
Creates NEW tabs per source, never overwrites.

Tracks everything: every contact found, before any prioritization.

Usage:
  python3 /scripts/upload_gathered.py uae-pakistan clay
  python3 /scripts/upload_gathered.py uae-pakistan apollo
  python3 /scripts/upload_gathered.py au-philippines clay
  python3 /scripts/upload_gathered.py all
"""
import json
import os
import sys
import glob
import datetime

if os.path.isdir('/app') and '/app' not in sys.path:
    sys.path.insert(0, '/app')

from google.oauth2 import service_account
from googleapiclient.discovery import build

SHEET_ID = '1pivHqk1NI-MHdDFSQugfg5olBMKTkBGr_yyjjXlWqKU'
DATA_DIR = '/scripts/data' if os.path.isdir('/scripts/data') else os.path.expanduser('~/magnum-opus-project/repo/scripts/data')

def get_sheets():
    creds = service_account.Credentials.from_service_account_file(
        '/app/google-credentials.json',
        scopes=['https://www.googleapis.com/auth/spreadsheets']
    ).with_subject('services@getsally.io')
    return build('sheets', 'v4', credentials=creds)


def upload_clay(corridor, sheets):
    slug = corridor.replace('-', '_')
    clay_file = f'{DATA_DIR}/{slug}_clay_all.json'
    if not os.path.exists(clay_file):
        print(f"No Clay data for {corridor}")
        return

    data = json.load(open(clay_file))
    print(f"{corridor} Clay: {len(data)} total contacts")

    # Dedup against what's already in the main corridor sheet
    main_tab = {
        'uae-pakistan': 'UAE-Pakistan',
        'au-philippines': 'AU-Philippines',
        'arabic-southafrica': 'Arabic-SouthAfrica',
    }.get(corridor, corridor)

    try:
        r = sheets.spreadsheets().values().get(
            spreadsheetId=SHEET_ID,
            range=f"'{main_tab}'!I2:I20000"
        ).execute()
        existing = set(row[0].strip().lower().rstrip('/') for row in r.get('values', []) if row and row[0].strip())
    except:
        existing = set()

    new = [p for p in data if (p.get('LinkedIn Profile') or '').lower().strip().rstrip('/') not in existing]
    print(f"After dedup against '{main_tab}': {len(new)} new")

    if not new:
        print("No new contacts to upload")
        return

    ts = datetime.datetime.now().strftime('%m%d_%H%M')
    tab = f'{corridor} Clay Gathered {ts}'

    sheets.spreadsheets().batchUpdate(
        spreadsheetId=SHEET_ID,
        body={'requests': [{'addSheet': {'properties': {'title': tab,
              'gridProperties': {'rowCount': max(2000, len(new) + 100), 'columnCount': 20}}}}]}
    ).execute()

    header = ['Name', 'First Name', 'Last Name', 'Email', 'Title', 'Company', 'Domain',
              'Location', 'LinkedIn URL', 'Phone', 'Industry', 'Company Size',
              'Schools (from Clay)', 'Origin Score', 'Name Match Reason', 'Search Type', 'Source']
    rows = [header]
    for p in new:
        fn = p.get('First Name', '')
        ln = p.get('Last Name', '')
        name = p.get('Full Name', f'{fn} {ln}'.strip())
        rows.append([
            name, fn, ln, '',
            p.get('Job Title', ''),
            p.get('Company Name', ''),
            (p.get('Company Domain') or '').lower().strip(),
            p.get('Location', ''),
            p.get('LinkedIn Profile', ''),
            '', '', '',
            p.get('Schools (from Clay)', ''),
            '', '', '', 'Clay',
        ])

    for i in range(0, len(rows), 500):
        batch = rows[i:i + 500]
        start = i + 1
        end = start + len(batch) - 1
        sheets.spreadsheets().values().update(
            spreadsheetId=SHEET_ID,
            range=f"'{tab}'!A{start}:Q{end}",
            valueInputOption='RAW',
            body={'values': batch}
        ).execute()

    print(f"Wrote {len(new)} to NEW tab '{tab}'")


def upload_apollo(corridor, sheets):
    slug = corridor.replace('-', '_')
    apollo_files = sorted(glob.glob(f'{DATA_DIR}/apollo_{slug}*.json'))
    if not apollo_files:
        print(f"No Apollo data for {corridor}")
        return

    # Merge all Apollo files for this corridor
    all_contacts = []
    for f in apollo_files:
        try:
            data = json.load(open(f))
            if isinstance(data, list):
                all_contacts.extend(data)
                print(f"  {os.path.basename(f)}: {len(data)} contacts")
        except:
            pass

    # Dedup by LinkedIn URL
    seen = set()
    unique = []
    for p in all_contacts:
        li = (p.get('linkedin') or '').lower().strip().rstrip('/')
        if li and li not in seen:
            seen.add(li)
            unique.append(p)
        elif not li:
            unique.append(p)

    print(f"{corridor} Apollo: {len(unique)} unique contacts")

    ts = datetime.datetime.now().strftime('%m%d_%H%M')
    tab = f'{corridor} Apollo Gathered {ts}'

    sheets.spreadsheets().batchUpdate(
        spreadsheetId=SHEET_ID,
        body={'requests': [{'addSheet': {'properties': {'title': tab,
              'gridProperties': {'rowCount': max(3000, len(unique) + 100), 'columnCount': 20}}}}]}
    ).execute()

    header = ['Name', 'First Name', 'Last Name', 'Email', 'Title', 'Company', 'Domain',
              'Location', 'LinkedIn URL', 'OrgId', 'Source']
    rows = [header]
    for p in unique:
        name = p.get('name', '')
        parts = name.split(' ', 1)
        fn = parts[0] if parts else ''
        ln = parts[1] if len(parts) > 1 else ''
        rows.append([
            name, fn, ln, '',
            p.get('title', ''),
            p.get('company', ''),
            p.get('domain', ''),
            '',  # Apollo location was broken
            p.get('linkedin', ''),
            p.get('orgId', ''),
            'Apollo',
        ])

    for i in range(0, len(rows), 500):
        batch = rows[i:i + 500]
        start = i + 1
        end = start + len(batch) - 1
        sheets.spreadsheets().values().update(
            spreadsheetId=SHEET_ID,
            range=f"'{tab}'!A{start}:K{end}",
            valueInputOption='RAW',
            body={'values': batch}
        ).execute()

    print(f"Wrote {len(unique)} to NEW tab '{tab}'")


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 upload_gathered.py <corridor> [clay|apollo|all]")
        print("  python3 upload_gathered.py uae-pakistan clay")
        print("  python3 upload_gathered.py all")
        return

    sheets = get_sheets()

    corridors = ['uae-pakistan', 'au-philippines', 'arabic-southafrica'] if sys.argv[1] == 'all' else [sys.argv[1]]
    sources = [sys.argv[2]] if len(sys.argv) > 2 else ['clay', 'apollo']

    for corridor in corridors:
        print(f"\n{'='*60}")
        print(f"CORRIDOR: {corridor}")
        if 'clay' in sources:
            upload_clay(corridor, sheets)
        if 'apollo' in sources:
            upload_apollo(corridor, sheets)


if __name__ == '__main__':
    main()
