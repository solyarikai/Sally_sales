#!/usr/bin/env python3
"""Build clean UAE-PK list by removing flagged contacts."""
import json, sys
from datetime import datetime
sys.path.insert(0, '/app')
from app.services.google_sheets_service import GoogleSheetsService

SHEET_ID = '1pivHqk1NI-MHdDFSQugfg5olBMKTkBGr_yyjjXlWqKU'
SOURCE_TAB = 'UAE-PK GOD SCORED 0316_1856'

gs = GoogleSheetsService()
raw = gs.read_sheet_raw(SHEET_ID, SOURCE_TAB)
headers = raw[0]
rows = raw[1:]

# Load removal list
removals = set(json.load(open('/tmp/uae_pk_removals.json')))
print(f'Total contacts: {len(rows)}')
print(f'Removals: {len(removals)}')

# Filter
clean = []
removed = 0
for row in rows:
    rank = row[0].strip() if row else ''
    if rank in removals:
        removed += 1
        continue
    clean.append(row)

# Re-rank
for i, row in enumerate(clean):
    row[0] = str(i + 1)

print(f'Removed: {removed}')
print(f'Clean: {len(clean)}')

# Write to new tab
ts = datetime.now().strftime('%m%d_%H%M')
tab_name = f'UAE-PK FINAL CLEAN {ts}'

gs._initialize()
try:
    gs.sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=SHEET_ID,
        body={'requests': [{'addSheet': {'properties': {'title': tab_name,
              'gridProperties': {'rowCount': max(10000, len(clean) + 100)}}}}]}
    ).execute()
except Exception:
    pass

data = [headers] + clean
for i in range(0, len(data), 500):
    batch = data[i:i + 500]
    gs.sheets_service.spreadsheets().values().update(
        spreadsheetId=SHEET_ID,
        range=f"'{tab_name}'!A{i + 1}",
        valueInputOption='RAW',
        body={'values': batch}
    ).execute()

print(f'Wrote {len(clean)} contacts to: {tab_name}')

# Save JSON for FindyMail
contacts_json = []
col = {h: i for i, h in enumerate(headers)}
for row in clean:
    def g(name):
        idx = col.get(name, -1)
        return (row[idx] if idx >= 0 and idx < len(row) else '').strip()
    contacts_json.append({
        'first_name': g('First Name'),
        'last_name': g('Last Name'),
        'title': g('Title'),
        'company': g('Company'),
        'domain': g('Domain'),
        'location': g('Location'),
        'linkedin_url': g('LinkedIn URL'),
    })
json.dump(contacts_json, open('/tmp/uae_pk_clean_for_findymail.json', 'w'), indent=2, ensure_ascii=False)
print(f'JSON saved: /tmp/uae_pk_clean_for_findymail.json')
