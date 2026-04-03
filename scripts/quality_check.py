#!/usr/bin/env python3
"""Quality check: spot-check contacts from both scored corridor tabs."""
import random
import sys
sys.path.insert(0, '/app')
from app.services.google_sheets_service import GoogleSheetsService

SHEET_ID = '1pivHqk1NI-MHdDFSQugfg5olBMKTkBGr_yyjjXlWqKU'
TABS = [
    'AU-PH Targets 0316_1308',
    'Arabic-SA Targets 0316_1309',
]

gs = GoogleSheetsService()

for tab in TABS:
    raw = gs.read_sheet_raw(SHEET_ID, tab)
    headers = raw[0]
    rows = raw[1:]
    col = {h: i for i, h in enumerate(headers)}

    print(f'\n{"="*80}')
    print(f'{tab}: {len(rows)} contacts')
    print(f'{"="*80}')

    # 20 random samples
    sample = random.sample(rows, min(20, len(rows)))
    for i, row in enumerate(sample):
        def g(name):
            idx = col.get(name, -1)
            return row[idx].strip() if idx >= 0 and idx < len(row) else ''

        name = g('First Name') + ' ' + g('Last Name')
        title = g('Title')
        company = g('Company')
        loc = g('Location')
        domain = g('Domain')
        origin = g('Origin Score')
        tier = g('Role Tier')
        li = g('LinkedIn URL')

        print(f'\n  [{i+1}] {name}')
        print(f'      Title:    {title}')
        print(f'      Company:  {company}')
        print(f'      Location: {loc}')
        print(f'      Domain:   {domain}')
        print(f'      LinkedIn: {li[:60]}')
        print(f'      Origin:   {origin}  Role: {tier}')

    # Aggregate checks
    print(f'\n--- AGGREGATE CHECKS ---')

    # Empty fields
    empty_title = sum(1 for r in rows if not r[col.get('Title', 4)].strip())
    empty_company = sum(1 for r in rows if not r[col.get('Company', 6)].strip())
    empty_location = sum(1 for r in rows if not r[col.get('Location', 8)].strip())
    empty_linkedin = sum(1 for r in rows if not r[col.get('LinkedIn URL', 9)].strip())
    empty_domain = sum(1 for r in rows if not r[col.get('Domain', 7)].strip())
    print(f'Empty title:    {empty_title}/{len(rows)}')
    print(f'Empty company:  {empty_company}/{len(rows)}')
    print(f'Empty location: {empty_location}/{len(rows)}')
    print(f'Empty LinkedIn: {empty_linkedin}/{len(rows)}')
    print(f'Empty domain:   {empty_domain}/{len(rows)}')

    # Suspicious: origin=0 means failed origin check
    origin_idx = col.get('Origin Score', 10)
    low_origin = sum(1 for r in rows if (r[origin_idx].strip() if origin_idx < len(r) else '0') in ('0', '-1', ''))
    print(f'Origin 0/-1:    {low_origin}/{len(rows)}')

    # Check for talent country in location (SHOULD NOT BE THERE)
    if 'AU-PH' in tab:
        bad_loc = sum(1 for r in rows if any(x in r[col['Location']].lower() for x in ['philippines', 'manila', 'cebu']))
    else:
        bad_loc = sum(1 for r in rows if any(x in r[col['Location']].lower() for x in ['south africa', 'johannesburg', 'cape town']))
    print(f'WRONG location: {bad_loc}/{len(rows)}')
