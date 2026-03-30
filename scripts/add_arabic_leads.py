#!/usr/bin/env python3
"""Add Arabic-SouthAfrica corridor leads with emails to UAE-PK campaign.
These are Gulf-based contacts (UAE, Saudi, Qatar etc) — same corridor."""
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, '/app')
from app.services.findymail_service import FindymailService
from app.services.smartlead_service import SmartleadService
from app.services.google_sheets_service import GoogleSheetsService

SHEET_ID = '1pivHqk1NI-MHdDFSQugfg5olBMKTkBGr_yyjjXlWqKU'
CID = '3042239'
CONCURRENT = 5


async def main():
    gs = GoogleSheetsService()
    fm = FindymailService()
    fm.set_api_key(os.environ.get('FINDYMAIL_API_KEY', ''))
    sl = SmartleadService()

    # Read the Arabic-SA scored tab (latest)
    tabs = gs.get_tab_info(SHEET_ID)
    arabic_tabs = [t for t in tabs if 'Arabic-SouthAfrica v8 Scored' in t['name']]
    arabic_tabs.sort(key=lambda t: t['name'], reverse=True)

    if not arabic_tabs:
        print("No Arabic-SA scored tab found")
        return

    tab = arabic_tabs[0]['name']
    print(f"Reading {tab}...")
    raw = gs.read_sheet_raw(SHEET_ID, tab)
    headers = raw[0]
    col = {h: i for i, h in enumerate(headers)}
    rows = raw[1:]
    print(f"Total contacts: {len(rows)}")

    # Extract contacts with LinkedIn URLs
    contacts = []
    for row in rows:
        li = row[col.get('LinkedIn URL', 9)].strip() if col.get('LinkedIn URL', 9) < len(row) else ''
        email = row[col.get('Email', 3)].strip() if col.get('Email', 3) < len(row) else ''
        if not li:
            continue
        contacts.append({
            'first_name': row[col.get('First Name', 1)] if col.get('First Name', 1) < len(row) else '',
            'last_name': row[col.get('Last Name', 2)] if col.get('Last Name', 2) < len(row) else '',
            'email': email,
            'title': row[col.get('Title', 4)] if col.get('Title', 4) < len(row) else '',
            'company': row[col.get('Company', 6)] if col.get('Company', 6) < len(row) else '',
            'domain': row[col.get('Domain', 7)] if col.get('Domain', 7) < len(row) else '',
            'location': row[col.get('Location', 8)] if col.get('Location', 8) < len(row) else '',
            'linkedin_url': li,
        })

    already_have = sum(1 for c in contacts if c['email'])
    need_email = [c for c in contacts if not c['email']]
    print(f"Have LinkedIn: {len(contacts)}")
    print(f"Already have email: {already_have}")
    print(f"Need FindyMail: {len(need_email)}")

    # FindyMail enrichment
    sem = asyncio.Semaphore(CONCURRENT)
    found = 0
    failed = 0

    async def enrich(contact):
        nonlocal found, failed
        async with sem:
            try:
                result = await fm.find_email_by_linkedin(contact['linkedin_url'])
                email = result.get('email', '') if result else ''
                if email:
                    contact['email'] = email
                    found += 1
                else:
                    failed += 1
            except Exception:
                failed += 1

    t0 = time.time()
    batch_size = 50
    for i in range(0, len(need_email), batch_size):
        batch = need_email[i:i + batch_size]
        await asyncio.gather(*[enrich(c) for c in batch], return_exceptions=True)
        print(f"  [{i + len(batch)}/{len(need_email)}] found={found} failed={failed}")

    print(f"\nFindyMail: {found} emails in {time.time()-t0:.0f}s ({found*100/max(1,found+failed):.0f}%)")

    # Collect all with emails
    with_email = [c for c in contacts if c['email']]
    print(f"Total with email: {len(with_email)}")

    if not with_email:
        print("No emails, nothing to add")
        return

    # Add to campaign
    sl_leads = [{
        'email': c['email'],
        'first_name': c['first_name'],
        'last_name': c['last_name'],
        'company_name': c['company'],
        'website': c['domain'],
        'custom_fields': {
            'title': c['title'],
            'location': c['location'],
            'linkedin_url': c['linkedin_url'],
        }
    } for c in with_email]

    # Upload in batches
    total_added = 0
    for i in range(0, len(sl_leads), 100):
        batch = sl_leads[i:i + 100]
        result = await sl.add_leads_to_campaign(CID, batch)
        if result.get('success'):
            added = result.get('data', {}).get('total_leads', len(batch))
            total_added += added
            print(f"  Batch {i//100+1}: uploaded {len(batch)}")
        await asyncio.sleep(1)

    print(f"\nDone! Added {total_added} Arabic corridor leads to campaign {CID}")


if __name__ == '__main__':
    asyncio.run(main())
