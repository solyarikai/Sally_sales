#!/usr/bin/env python3
"""Check search_type and schools signals in raw gathered data."""
import sys
sys.path.insert(0, '/app')
from collections import Counter
from app.services.google_sheets_service import GoogleSheetsService

SHEET_ID = '1pivHqk1NI-MHdDFSQugfg5olBMKTkBGr_yyjjXlWqKU'

gs = GoogleSheetsService()

UAE_KW = ['dubai', 'abu dhabi', 'uae', 'united arab', 'sharjah', 'ajman',
          'ras al', 'fujairah', '\u0627\u0644\u0625\u0645\u0627\u0631\u0627\u062a',
          '\u062f\u0628\u064a', '\u0623\u0628\u0648 \u0638\u0628\u064a']
AU_KW = ['australia', 'sydney', 'melbourne', 'brisbane', 'perth', 'adelaide',
         'canberra', 'gold coast', 'hobart', 'darwin', 'new south wales',
         'victoria', 'queensland', 'western australia']
GULF_KW = ['qatar', 'doha', 'saudi', 'riyadh', 'jeddah', 'bahrain', 'manama',
           'kuwait', 'oman', 'muscat', 'uae', 'dubai', 'abu dhabi', 'united arab',
           '\u0627\u0644\u0625\u0645\u0627\u0631\u0627\u062a', '\u062f\u0628\u064a',
           '\u0627\u0644\u0631\u064a\u0627\u0636', '\u0627\u0644\u0633\u0639\u0648\u062f\u064a\u0629']

PH_EXCLUDE = ['philippines', 'manila', 'cebu', 'davao', 'makati', 'india', 'pakistan']
SA_EXCLUDE = ['south africa', 'johannesburg', 'cape town', 'durban', 'india', 'pakistan', 'nigeria']

ANTI_TITLES = ['intern', 'student', 'trainee', 'junior', 'assistant', 'receptionist',
               'freelancer', 'volunteer', 'virtual assistant']

corridors = {
    'AU-Philippines': {'tab': 'AU-Philippines', 'buyer_kw': AU_KW, 'exclude': PH_EXCLUDE},
    'Arabic-SouthAfrica': {'tab': 'Arabic-SouthAfrica', 'buyer_kw': GULF_KW, 'exclude': SA_EXCLUDE},
}

for name, cfg in corridors.items():
    raw = gs.read_sheet_raw(SHEET_ID, cfg['tab'])
    headers = raw[0]
    rows = raw[1:]
    col = {h: i for i, h in enumerate(headers)}

    print(f'\n{"="*60}')
    print(f'{name}: {len(rows)} total contacts')
    print(f'Headers: {headers}')
    print(f'{"="*60}')

    # Filter by buyer location
    in_buyer = []
    for row in rows:
        loc = (row[col.get('Location', 7)] if col.get('Location', 7) < len(row) else '').lower()
        if any(x in loc for x in cfg['exclude']):
            continue
        if not loc:
            continue
        if any(x in loc for x in cfg['buyer_kw']):
            # Anti-title filter
            title = (row[col.get('Title', 4)] if col.get('Title', 4) < len(row) else '').lower()
            if any(a in title for a in ANTI_TITLES):
                continue
            in_buyer.append(row)

    print(f'In buyer country (after location + title filter): {len(in_buyer)}')

    # Analyze by search_type
    st_idx = col.get('Search Type', -1)
    schools_idx = col.get('Schools (from Clay)', -1)
    origin_idx = col.get('Origin Score', -1)
    reason_idx = col.get('Name Match Reason', -1)

    search_types = Counter()
    has_school = 0
    by_origin = Counter()

    lang_contacts = []
    uni_contacts = []
    other_contacts = []

    for row in in_buyer:
        st = (row[st_idx] if st_idx >= 0 and st_idx < len(row) else '').lower()
        schools = (row[schools_idx] if schools_idx >= 0 and schools_idx < len(row) else '').strip()
        origin = (row[origin_idx] if origin_idx >= 0 and origin_idx < len(row) else '0')
        reason = (row[reason_idx] if reason_idx >= 0 and reason_idx < len(row) else '')

        search_types[st] += 1
        if schools:
            has_school += 1
        by_origin[origin] += 1

        if 'language' in st or 'lang' in st:
            lang_contacts.append(row)
        elif 'university' in st or 'school' in st or 'uni' in st:
            uni_contacts.append(row)
        else:
            other_contacts.append(row)

    print(f'\nSearch type distribution:')
    for st, cnt in search_types.most_common():
        print(f'  {cnt:>5}  {st or "(empty)"}')

    print(f'\nOrigin score distribution:')
    for o, cnt in sorted(by_origin.items()):
        print(f'  origin={o}: {cnt}')

    print(f'\nHas school/university data: {has_school}')

    print(f'\n--- SIGNAL-BASED COUNTS ---')
    print(f'Language signal (Tagalog/Afrikaans etc): {len(lang_contacts)}')
    print(f'University signal: {len(uni_contacts)}')
    print(f'Other (surname/city-split/unknown): {len(other_contacts)}')
    print(f'TOTAL language + university: {len(lang_contacts) + len(uni_contacts)}')

    # Sample language contacts
    if lang_contacts:
        print(f'\nSample LANGUAGE contacts (first 5):')
        for r in lang_contacts[:5]:
            fn = r[col.get('First Name', 1)] if col.get('First Name', 1) < len(r) else ''
            ln = r[col.get('Last Name', 2)] if col.get('Last Name', 2) < len(r) else ''
            title = r[col.get('Title', 4)] if col.get('Title', 4) < len(r) else ''
            comp = r[col.get('Company', 5)] if col.get('Company', 5) < len(r) else ''
            loc = r[col.get('Location', 7)] if col.get('Location', 7) < len(r) else ''
            st = r[st_idx] if st_idx < len(r) else ''
            print(f'  {fn} {ln} | {title[:30]} | {comp[:25]} | {loc[:30]} | {st}')

    if uni_contacts:
        print(f'\nSample UNIVERSITY contacts (first 5):')
        for r in uni_contacts[:5]:
            fn = r[col.get('First Name', 1)] if col.get('First Name', 1) < len(r) else ''
            ln = r[col.get('Last Name', 2)] if col.get('Last Name', 2) < len(r) else ''
            title = r[col.get('Title', 4)] if col.get('Title', 4) < len(r) else ''
            schools = r[schools_idx] if schools_idx < len(r) else ''
            loc = r[col.get('Location', 7)] if col.get('Location', 7) < len(r) else ''
            print(f'  {fn} {ln} | {title[:30]} | {loc[:30]} | Schools: {schools[:50]}')
