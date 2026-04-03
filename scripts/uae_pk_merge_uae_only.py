#!/usr/bin/env python3
"""Merge UAE-PK verified + reuse, keep UAE-located only, cap 3/company."""
import sys, os
sys.path.insert(0, '/app')

from collections import defaultdict
from datetime import datetime
from app.services.google_sheets_service import GoogleSheetsService

SHEET_ID = '1pivHqk1NI-MHdDFSQugfg5olBMKTkBGr_yyjjXlWqKU'

UAE_KW = ['dubai', 'abu dhabi', 'sharjah', 'uae', 'united arab', 'ajman',
          'ras al', 'fujairah', '\u0627\u0644\u0625\u0645\u0627\u0631\u0627\u062a',
          '\u062f\u0628\u064a', '\u0623\u0628\u0648 \u0638\u0628\u064a']

def is_uae(loc):
    loc = (loc or '').lower()
    return any(k in loc for k in UAE_KW)

gs = GoogleSheetsService()

# Read both tabs
tabs = ['UAE-PK VERIFIED 0316_0854', 'UAE-PK Reuse Scored 0316_1016']
headers = None
all_rows = []
for tab in tabs:
    raw = gs.read_sheet_raw(SHEET_ID, tab)
    if not raw or len(raw) < 2:
        continue
    if headers is None:
        headers = raw[0]
    all_rows.extend(raw[1:])
    print(f"{tab}: {len(raw)-1} rows")

col = {h: i for i, h in enumerate(headers)}
loc_idx = col['Location']
domain_idx = col['Domain']
company_idx = col['Company']

# Filter UAE-only, group by company
companies = defaultdict(list)
uae_total = 0
for row in all_rows:
    loc = row[loc_idx] if loc_idx < len(row) else ''
    if not is_uae(loc):
        continue
    uae_total += 1
    domain = (row[domain_idx] if domain_idx < len(row) else '').lower().strip()
    company = row[company_idx] if company_idx < len(row) else ''
    key = domain if domain else f"__name__{company.lower()}"
    companies[key].append(row)

print(f"\nUAE-located: {uae_total}")
print(f"Unique companies: {len(companies)}")

# Cap 3 per company
final = []
for key, rows in companies.items():
    final.extend(rows[:3])

# Re-rank
for i, row in enumerate(final):
    row[0] = str(i + 1)

ts = datetime.now().strftime('%m%d_%H%M')
tab_name = f"UAE-PK FINAL {ts}"

print(f"After 3/company cap: {len(final)} contacts")
print(f"Writing to: {tab_name}")

# Create tab
gs._initialize()
try:
    gs.sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=SHEET_ID,
        body={'requests': [{'addSheet': {'properties': {'title': tab_name,
              'gridProperties': {'rowCount': max(2500, len(final) + 100)}}}}]}
    ).execute()
except Exception as e:
    print(f"Tab warning: {e}")

# Write in batches
data = [headers] + final
for i in range(0, len(data), 500):
    batch = data[i:i + 500]
    start = i + 1
    range_str = f"'{tab_name}'!A{start}"
    gs.sheets_service.spreadsheets().values().update(
        spreadsheetId=SHEET_ID,
        range=range_str,
        valueInputOption='RAW',
        body={'values': batch}
    ).execute()
    print(f"  Wrote rows {start}-{start + len(batch) - 1}")

print(f"\nDone! {len(final)} UAE-located contacts in '{tab_name}'")

# Stats on companies needing more contacts
need_more = [(key, rows) for key, rows in companies.items()
             if len(rows) < 3 and not key.startswith('__name__')]
need_1 = sum(1 for _, r in need_more if len(r) == 1)
need_2 = sum(1 for _, r in need_more if len(r) == 2)
print(f"\nCompanies with <3 UAE contacts (could enrich via browser): {len(need_more)}")
print(f"  Have 1 contact: {need_1}")
print(f"  Have 2 contacts: {need_2}")
print(f"  Potential extra contacts: {need_1 * 2 + need_2 * 1}")

# Save domains needing enrichment
import json
enrich_list = [{'domain': key, 'name': rows[0][company_idx], 'have': len(rows), 'need': 3 - len(rows)}
               for key, rows in need_more]
enrich_list.sort(key=lambda x: -x['need'])
json.dump(enrich_list, open('/tmp/uae_pk_need_browser_enrich.json', 'w'), indent=2)
print(f"Saved enrichment list: /tmp/uae_pk_need_browser_enrich.json ({len(enrich_list)} companies)")
