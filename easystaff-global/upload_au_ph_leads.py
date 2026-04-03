#!/usr/bin/env python3
"""Upload AU-PH leads to already-created campaign 3057831 + add to project."""
import asyncio
import csv
import json
import os
import sys
from collections import Counter

sys.path.insert(0, '/app')
import httpx

CAMPAIGN_ID = '3057831'
CAMPAIGN_NAME = "AU-Philippines Petr 19/03"
SL_KEY = os.environ.get('SMARTLEAD_API_KEY', '')
SL_BASE = 'https://server.smartlead.ai/api/v1'

EMAILS_CSV = '/scripts/data/au_ph_with_emails.csv'
OPUS_FINAL_CSV = '/scripts/data/au_ph_OPUS_FINAL.csv'

API_BASE = "http://localhost:8000/api"
HEADERS = {"X-Company-ID": "1", "Content-Type": "application/json"}

# City extraction
CITY_ALIASES = {
    'greater sydney area': 'Sydney', 'greater melbourne area': 'Melbourne',
    'greater brisbane area': 'Brisbane', 'greater perth area': 'Perth',
    'greater adelaide area': 'Adelaide', 'greater darwin area': 'Darwin',
    'greater newcastle area': 'Newcastle', 'greater hobart area': 'Hobart',
    'greater geelong area': 'Geelong', 'greater gold coast area': 'Gold Coast',
    'brisbane city': 'Brisbane', 'sydney': 'Sydney', 'melbourne': 'Melbourne',
    'brisbane': 'Brisbane', 'perth': 'Perth', 'adelaide': 'Adelaide',
    'gold coast': 'Gold Coast', 'canberra': 'Canberra', 'darwin': 'Darwin',
    'hobart': 'Hobart', 'newcastle': 'Newcastle', 'wollongong': 'Wollongong',
    'geelong': 'Geelong', 'ballarat north': 'Ballarat',
    'sunshine coast': 'Sunshine Coast',
}
STATE_CITY = {
    'new south wales': 'Sydney', 'victoria': 'Melbourne', 'queensland': 'Brisbane',
    'western australia': 'Perth', 'south australia': 'Adelaide',
    'australian capital territory': 'Canberra', 'northern territory': 'Darwin',
    'tasmania': 'Hobart',
}

def extract_city(location):
    if not location:
        return 'Australia'
    parts = [p.strip() for p in location.split(',')]
    first = parts[0].lower()
    if first in CITY_ALIASES:
        return CITY_ALIASES[first]
    for part in parts:
        pl = part.strip().lower()
        if pl in STATE_CITY:
            return STATE_CITY[pl]
    return 'Australia' if 'australia' in location.lower() else (parts[0] or 'Australia')


def load_leads():
    with open(EMAILS_CSV) as f:
        email_rows = list(csv.DictReader(f))
    print(f"Loaded {len(email_rows)} contacts with emails")

    opus_by_li = {}
    with open(OPUS_FINAL_CSV) as f:
        for row in csv.DictReader(f):
            li = (row.get('LinkedIn') or '').strip().rstrip('/')
            if li:
                opus_by_li[li.lower()] = row
    print(f"Loaded {len(opus_by_li)} OPUS FINAL contacts")

    leads = []
    for e in email_rows:
        li = (e.get('linkedin_url') or '').strip().rstrip('/')
        opus = opus_by_li.get(li.lower(), {}) if li else {}
        location = opus.get('Location', '') or ''
        city = extract_city(location)

        lead = {
            "email": e['email'],
            "first_name": e.get('first_name', ''),
            "last_name": e.get('last_name', ''),
            "company_name": e.get('company_name', '') or opus.get('Company', ''),
            "website": e.get('company_url', '') or opus.get('Domain', '') or '',
            "custom_fields": {"city": city},
        }
        title = e.get('title', '') or opus.get('Title', '')
        if title:
            lead["custom_fields"]["title"] = title
        if li:
            lead["custom_fields"]["linkedin_url"] = li
        if location:
            lead["custom_fields"]["location"] = location
        leads.append(lead)

    cities = Counter(l["custom_fields"]["city"] for l in leads)
    print(f"\nCity distribution:")
    for city, cnt in cities.most_common(15):
        print(f"  {cnt:>4}  {city}")
    return leads


async def main():
    leads = load_leads()

    # Upload leads
    print(f"\nUploading {len(leads)} leads to campaign {CAMPAIGN_ID}...")
    async with httpx.AsyncClient(timeout=60) as c:
        total = 0
        for i in range(0, len(leads), 100):
            batch = leads[i:i + 100]
            r = await c.post(
                f"{SL_BASE}/campaigns/{CAMPAIGN_ID}/leads",
                params={"api_key": SL_KEY},
                json={"lead_list": batch}
            )
            if r.status_code == 200:
                uploaded = r.json().get('upload_count', len(batch))
                total += uploaded
                print(f"  Batch {i // 100 + 1}: {uploaded}")
            else:
                print(f"  Batch {i // 100 + 1} ERROR: {r.status_code} {r.text[:200]}")
            await asyncio.sleep(1)
    print(f"Total uploaded: {total}")

    # Add to project
    print(f"\nAdding to easystaff global project...")
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{API_BASE}/contacts/projects/names", headers=HEADERS)
        projects = resp.json() if resp.status_code == 200 else []
        es = next((p for p in projects if 'easystaff global' in p.get('name', '').lower()), None)
        if es:
            pid = es['id']
            resp = await client.get(f"{API_BASE}/contacts/projects/{pid}", headers=HEADERS)
            if resp.status_code == 200:
                pd = resp.json()
                filters = pd.get('campaign_filters') or []
                rules = pd.get('campaign_ownership_rules') or {}
                prefixes = rules.get('prefixes', [])
                changed = False
                if CAMPAIGN_NAME not in filters:
                    filters.append(CAMPAIGN_NAME)
                    changed = True
                if 'AU-Philippines Petr' not in prefixes:
                    prefixes.append('AU-Philippines Petr')
                    rules['prefixes'] = prefixes
                    changed = True
                if changed:
                    resp = await client.patch(
                        f"{API_BASE}/contacts/projects/{pid}", headers=HEADERS,
                        json={"campaign_filters": filters, "campaign_ownership_rules": rules}
                    )
                    print(f"Updated project {pid}: {resp.status_code}")
                else:
                    print("Already configured")
        else:
            print("ERROR: project not found")

    print(f"\nDONE — campaign {CAMPAIGN_ID}")
    print(f"URL: https://app.smartlead.ai/app/email-campaigns-v2/{CAMPAIGN_ID}/analytics")

if __name__ == '__main__':
    asyncio.run(main())
