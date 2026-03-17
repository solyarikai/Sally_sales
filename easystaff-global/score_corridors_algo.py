#!/usr/bin/env python3
"""Score AU-PH and Arabic-SA corridors using algorithmic blacklist only.
No AI, no GPT. Pure pattern matching against enterprise_blacklist.json.
Requires domain. Removes: enterprise, government, recruitment, anti-titles, junk."""
import json, sys, os
from collections import Counter
from datetime import datetime

sys.path.insert(0, '/app')
from app.services.google_sheets_service import GoogleSheetsService

SHEET_ID = '1pivHqk1NI-MHdDFSQugfg5olBMKTkBGr_yyjjXlWqKU'

# Load blacklist
bl_path = os.path.join(os.path.dirname(__file__), 'data', 'enterprise_blacklist.json')
if not os.path.exists(bl_path):
    bl_path = '/app/scripts/data/enterprise_blacklist.json'
bl = json.load(open(bl_path))

ent_domains = set(d.lower() for d in bl['enterprise_domains'])
ent_names = [n.lower() for n in bl['enterprise_names_contains']]
blocked_suffixes = bl.get('blocked_domain_suffixes', [])
gov_names = [n.lower() for n in bl['government_names_contains']]
rec_names = [n.lower() for n in bl['recruitment_names_contains']]
comp_domains = set(d.lower() for d in bl['competitor_domains'])
india_domains = set(d.lower() for d in bl['india_outsourcing_domains'])
anti_titles = [t.lower() for t in bl.get('anti_titles', [])]
fake_domains = set(d.lower() for d in bl.get('junk_patterns', {}).get('fake_domains', []))
placeholder = [p.lower() for p in bl.get('junk_patterns', {}).get('placeholder_companies', [])]

CORRIDORS = {
    'au-philippines': {
        'source_tab': 'AU-Philippines',
        'buyer_kw': ['australia', 'sydney', 'melbourne', 'brisbane', 'perth', 'adelaide',
                     'canberra', 'gold coast', 'new south wales', 'victoria', 'queensland',
                     'western australia'],
        'exclude_loc': ['philippines', 'manila', 'cebu', 'davao', 'india', 'pakistan'],
    },
    'arabic-southafrica': {
        'source_tab': 'Arabic-SouthAfrica',
        'buyer_kw': ['qatar', 'doha', 'saudi', 'riyadh', 'jeddah', 'bahrain', 'manama',
                     'kuwait', 'oman', 'muscat', 'uae', 'dubai', 'abu dhabi', 'united arab',
                     '\u0627\u0644\u0625\u0645\u0627\u0631\u0627\u062a', '\u062f\u0628\u064a',
                     '\u0627\u0644\u0631\u064a\u0627\u0636', '\u0627\u0644\u0633\u0639\u0648\u062f\u064a\u0629'],
        'exclude_loc': ['south africa', 'johannesburg', 'cape town', 'durban', 'india', 'pakistan', 'nigeria'],
    },
}

gs = GoogleSheetsService()

for corridor_key, cfg in CORRIDORS.items():
    print(f"\n{'='*60}")
    print(f"SCORING: {corridor_key}")
    print(f"{'='*60}")

    raw = gs.read_sheet_raw(SHEET_ID, cfg['source_tab'])
    headers = raw[0]
    rows = raw[1:]
    col = {h: i for i, h in enumerate(headers)}
    print(f"Total: {len(rows)}")

    def gv(row, name):
        idx = col.get(name, -1)
        return (row[idx] if idx >= 0 and idx < len(row) else '').strip()

    # Step 1: Location filter
    in_buyer = []
    for row in rows:
        loc = gv(row, 'Location').lower()
        if not loc:
            continue
        if any(x in loc for x in cfg['exclude_loc']):
            continue
        if any(x in loc for x in cfg['buyer_kw']):
            in_buyer.append(row)

    print(f"In buyer country: {len(in_buyer)}")

    # Step 2: Domain required
    with_domain = [r for r in in_buyer if gv(r, 'Domain').strip()]
    print(f"With domain: {len(with_domain)}")

    # Step 3: Blacklist filter
    clean = []
    removed = 0
    for row in with_domain:
        domain = gv(row, 'Domain').lower()
        company = gv(row, 'Company').lower()
        title = gv(row, 'Title').lower()

        hit = False
        if domain in ent_domains or domain in comp_domains or domain in india_domains or domain in fake_domains:
            hit = True
        if not hit:
            for s in blocked_suffixes:
                if domain.endswith(s):
                    hit = True; break
        if not hit:
            for n in ent_names:
                if n in company:
                    hit = True; break
        if not hit:
            for n in gov_names:
                if n in company:
                    hit = True; break
        if not hit:
            for n in rec_names:
                if n in company:
                    hit = True; break
        if not hit:
            for t in anti_titles:
                if t in title:
                    hit = True; break
        if not hit:
            for p in placeholder:
                if company == p or company.startswith(p):
                    hit = True; break

        if hit:
            removed += 1
        else:
            clean.append(row)

    print(f"Blacklist removed: {removed}")
    print(f"Clean: {len(clean)}")

    # Step 4: Cap 3 per company
    from collections import defaultdict
    companies = defaultdict(list)
    for row in clean:
        d = gv(row, 'Domain').lower()
        key = d if d else gv(row, 'Company').lower()
        companies[key].append(row)

    final_rows = []
    for key, cc in companies.items():
        final_rows.extend(cc[:3])

    print(f"After 3/company cap: {len(final_rows)}")

    # Step 5: Write to new sheet
    url = gs.create_and_populate(
        f"{corridor_key} ALGO SCORED {datetime.now().strftime('%m%d_%H%M')}",
        [headers] + final_rows
    )
    print(f"Sheet: {url}")

    # Save JSON for Opus review
    contacts = []
    for row in final_rows:
        contacts.append({
            'r': str(len(contacts) + 1),
            'n': gv(row, 'First Name') + ' ' + gv(row, 'Last Name'),
            't': gv(row, 'Title'),
            'c': gv(row, 'Company'),
            'd': gv(row, 'Domain'),
            'l': gv(row, 'Location')[:30],
        })
    json.dump(contacts, open(f'/tmp/{corridor_key.replace("-","_")}_scored.json', 'w'), ensure_ascii=False)
    print(f"JSON: /tmp/{corridor_key.replace('-','_')}_scored.json ({len(contacts)} contacts)")
