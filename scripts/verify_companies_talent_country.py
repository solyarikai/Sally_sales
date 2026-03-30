#!/usr/bin/env python3
"""
For each corridor, check which target companies have employees in the talent country
using Clay browser search. Companies with ≥1 talent-country employee = confirmed target.

Runs Clay People Search with domains + country filter.
Batches of 200 domains to stay under Clay's 5K result cap.
"""
import asyncio
import json
import sys
import os
import time
from collections import defaultdict
from datetime import datetime

sys.path.insert(0, '/app')
from app.services.clay_service import ClayService
from app.services.google_sheets_service import GoogleSheetsService

SHEET_ID = '1pivHqk1NI-MHdDFSQugfg5olBMKTkBGr_yyjjXlWqKU'

CORRIDORS = {
    'au-philippines': {
        'source_tab': 'AU-PH Targets 0316_1308',
        'talent_country': 'Philippines',
        'output_prefix': 'AU-PH',
    },
    'arabic-southafrica': {
        'source_tab': 'Arabic-SA Targets 0316_1309',
        'talent_country': 'South Africa',
        'output_prefix': 'Arabic-SA',
    },
}

BATCH_SIZE = 200


async def check_corridor(corridor_key, config, clay, gs):
    print(f'\n{"="*60}')
    print(f'{corridor_key}: checking companies for {config["talent_country"]} employees')
    print(f'{"="*60}')

    # Read target contacts
    raw = gs.read_sheet_raw(SHEET_ID, config['source_tab'])
    headers = raw[0]
    rows = raw[1:]
    col = {h: i for i, h in enumerate(headers)}

    # Get unique domains
    domain_idx = col.get('Domain', 7)
    domains_to_contacts = defaultdict(list)
    for row in rows:
        domain = (row[domain_idx] if domain_idx < len(row) else '').strip().lower()
        if domain:
            domains_to_contacts[domain].append(row)

    all_domains = list(domains_to_contacts.keys())
    print(f'Total contacts: {len(rows)}')
    print(f'Unique domains: {len(all_domains)}')
    print(f'Contacts without domain: {sum(1 for r in rows if not (r[domain_idx] if domain_idx < len(r) else "").strip())}')

    # Batch Clay search: find companies with employees in talent country
    confirmed_domains = set()
    total_talent_employees = 0

    batches = [all_domains[i:i+BATCH_SIZE] for i in range(0, len(all_domains), BATCH_SIZE)]
    print(f'Batches: {len(batches)} x {BATCH_SIZE}')

    for batch_num, batch in enumerate(batches):
        print(f'\n  Batch {batch_num+1}/{len(batches)}: {len(batch)} domains -> {config["talent_country"]}')

        try:
            result = await clay.run_people_search(
                domains=batch,
                countries=[config['talent_country']],
                use_titles=False,  # Don't filter by title — we just want to know if ANY employee exists
            )
            people = result.get('people', [])
            print(f'  Found {len(people)} employees in {config["talent_country"]}')

            # Track which domains have matches
            for person in people:
                domain = (person.get('domain') or '').lower().strip()
                if domain:
                    confirmed_domains.add(domain)
                    total_talent_employees += 1

            batch_confirmed = sum(1 for d in batch if d in confirmed_domains)
            print(f'  Confirmed companies this batch: {batch_confirmed}/{len(batch)}')

        except Exception as e:
            print(f'  ERROR: {e}')
            continue

    print(f'\n{"="*60}')
    print(f'RESULTS: {corridor_key}')
    print(f'{"="*60}')
    print(f'Companies with {config["talent_country"]} employees: {len(confirmed_domains)}/{len(all_domains)}')
    print(f'Total talent-country employees found: {total_talent_employees}')

    # Build prioritized contact list
    tier1 = []  # Company has talent-country employees
    tier2 = []  # No confirmation but contact has language/university signal

    search_type_idx = col.get('Search Type', -1) if 'Search Type' in col else -1

    for row in rows:
        domain = (row[domain_idx] if domain_idx < len(row) else '').strip().lower()

        if domain in confirmed_domains:
            tier1.append(row)
        elif search_type_idx >= 0:
            st = (row[search_type_idx] if search_type_idx < len(row) else '').lower()
            if 'university' in st or 'language' in st:
                tier2.append(row)

    print(f'\nTier 1 (company confirmed): {len(tier1)} contacts')
    print(f'Tier 2 (language/uni signal, no company confirmation): {len(tier2)} contacts')
    print(f'Total target: {len(tier1) + len(tier2)} contacts')

    # Write to new tab
    ts = datetime.now().strftime('%m%d_%H%M')
    tab_name = f'{config["output_prefix"]} VERIFIED {ts}'

    # Add tier column
    out_headers = list(headers) + ['Tier', 'Talent Country Employees']
    out_rows = [out_headers]

    rank = 1
    for row in tier1:
        domain = (row[domain_idx] if domain_idx < len(row) else '').strip().lower()
        new_row = list(row)
        while len(new_row) < len(headers):
            new_row.append('')
        new_row[0] = str(rank)
        new_row.append('T1-confirmed')
        new_row.append('YES')
        out_rows.append(new_row)
        rank += 1

    for row in tier2:
        new_row = list(row)
        while len(new_row) < len(headers):
            new_row.append('')
        new_row[0] = str(rank)
        new_row.append('T2-signal')
        new_row.append('no')
        out_rows.append(new_row)
        rank += 1

    gs._initialize()
    try:
        gs.sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=SHEET_ID,
            body={'requests': [{'addSheet': {'properties': {'title': tab_name,
                  'gridProperties': {'rowCount': max(5000, len(out_rows) + 100)}}}}]}
        ).execute()
    except Exception:
        pass

    for i in range(0, len(out_rows), 500):
        batch = out_rows[i:i+500]
        gs.sheets_service.spreadsheets().values().update(
            spreadsheetId=SHEET_ID,
            range=f"'{tab_name}'!A{i+1}",
            valueInputOption='RAW',
            body={'values': batch}
        ).execute()

    print(f'Wrote to: {tab_name}')

    # Save confirmed domains
    json.dump(list(confirmed_domains),
              open(f'/tmp/{corridor_key}_confirmed_domains.json', 'w'))

    return confirmed_domains


async def main():
    clay = ClayService()
    gs = GoogleSheetsService()

    for corridor_key, config in CORRIDORS.items():
        await check_corridor(corridor_key, config, clay, gs)


if __name__ == '__main__':
    asyncio.run(main())
