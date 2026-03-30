#!/usr/bin/env python3
"""Spot-check contacts by search signal type for both corridors."""
import sys, random
sys.path.insert(0, '/app')
from app.services.google_sheets_service import GoogleSheetsService

SHEET_ID = '1pivHqk1NI-MHdDFSQugfg5olBMKTkBGr_yyjjXlWqKU'

AU_KW = ['australia', 'sydney', 'melbourne', 'brisbane', 'perth', 'adelaide',
         'canberra', 'gold coast', 'new south wales', 'victoria', 'queensland',
         'western australia', 'hobart', 'darwin']
GULF_KW = ['qatar', 'doha', 'saudi', 'riyadh', 'jeddah', 'bahrain', 'manama',
           'kuwait', 'oman', 'muscat', 'uae', 'dubai', 'abu dhabi', 'united arab',
           '\u0627\u0644\u0625\u0645\u0627\u0631\u0627\u062a', '\u062f\u0628\u064a',
           '\u0627\u0644\u0631\u064a\u0627\u0636', '\u0627\u0644\u0633\u0639\u0648\u062f\u064a\u0629']
PH_EXCLUDE = ['philippines', 'manila', 'cebu', 'davao', 'makati', 'india', 'pakistan']
SA_EXCLUDE = ['south africa', 'johannesburg', 'cape town', 'durban', 'india', 'pakistan', 'nigeria']

gs = GoogleSheetsService()

for corridor, tab, buyer_kw, exclude in [
    ('AU-PH', 'AU-Philippines', AU_KW, PH_EXCLUDE),
    ('Arabic-SA', 'Arabic-SouthAfrica', GULF_KW, SA_EXCLUDE),
]:
    raw = gs.read_sheet_raw(SHEET_ID, tab)
    headers = raw[0]
    col = {h: i for i, h in enumerate(headers)}
    rows = raw[1:]

    def g(row, name):
        idx = col.get(name, -1)
        return (row[idx] if idx >= 0 and idx < len(row) else '').strip()

    # Filter buyer-located
    buyer_rows = []
    for r in rows:
        loc = g(r, 'Location').lower()
        if any(x in loc for x in exclude):
            continue
        if not loc:
            continue
        if any(x in loc for x in buyer_kw):
            buyer_rows.append(r)

    # Group by search type
    groups = {}
    for r in buyer_rows:
        st = g(r, 'Search Type').lower()
        if 'language_city' in st:
            key = 'city_split'
        elif 'language' in st:
            key = 'language'
        elif 'university' in st or 'extended_university' in st:
            key = 'university'
        elif 'surname' in st:
            key = 'surname'
        else:
            key = 'other'
        groups.setdefault(key, []).append(r)

    print(f'\n{"="*70}')
    print(f'{corridor} — {len(buyer_rows)} contacts in buyer country')
    print(f'{"="*70}')

    for signal_type in ['language', 'city_split', 'university', 'surname', 'other']:
        contacts = groups.get(signal_type, [])
        if not contacts:
            continue

        print(f'\n--- {signal_type.upper()} ({len(contacts)} contacts) ---')
        sample = random.sample(contacts, min(10, len(contacts)))
        looks_target = 0
        looks_wrong = 0
        for r in sample:
            fn = g(r, 'First Name')
            ln = g(r, 'Last Name')
            title = g(r, 'Title')[:35]
            company = g(r, 'Company')[:25]
            loc = g(r, 'Location')[:30]
            origin = g(r, 'Origin Score')
            reason = g(r, 'Name Match Reason')[:40]
            print(f'  {fn:12s} {ln:18s} | {title:35s} | {company:25s} | {loc:30s} | O={origin} | {reason}')

        print()
