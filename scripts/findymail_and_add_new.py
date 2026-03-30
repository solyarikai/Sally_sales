#!/usr/bin/env python3
"""FindyMail enrichment for 135 new Clay contacts, then add to SmartLead campaign."""
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, '/app')
from app.services.findymail_service import FindymailService
from app.services.smartlead_service import SmartleadService

CID = '3042239'
CONCURRENT = 5


async def main():
    fm = FindymailService()
    fm.set_api_key(os.environ.get('FINDYMAIL_API_KEY', ''))
    sl = SmartleadService()

    data = json.load(open('/tmp/uae_pk_enriched_all.json'))
    print(f"New contacts to enrich: {len(data)}")

    # FindyMail enrichment
    sem = asyncio.Semaphore(CONCURRENT)
    found = 0
    failed = 0

    async def enrich(contact):
        nonlocal found, failed
        li = contact.get('linkedin_url', '')
        if not li:
            failed += 1
            return
        async with sem:
            try:
                result = await fm.find_email_by_linkedin(li)
                email = result.get('email', '') if result else ''
                if email:
                    contact['email'] = email
                    found += 1
                else:
                    failed += 1
            except Exception as e:
                failed += 1

    t0 = time.time()
    tasks = [enrich(c) for c in data]
    # Process in batches for progress
    batch = 25
    for i in range(0, len(tasks), batch):
        await asyncio.gather(*tasks[i:i+batch], return_exceptions=True)
        print(f"  [{i+batch}/{len(data)}] found={found} failed={failed}")

    elapsed = time.time() - t0
    print(f"\nFindyMail done in {elapsed:.0f}s")
    print(f"Found: {found}, Failed: {failed}, Rate: {found*100/max(1,found+failed):.0f}%")

    # Filter to contacts with emails
    with_email = [c for c in data if c.get('email')]
    print(f"Contacts with email: {len(with_email)}")

    if not with_email:
        print("No emails found, nothing to add")
        return

    # Add to SmartLead campaign
    sl_leads = []
    for c in with_email:
        name = c.get('first_name', '')
        if not name:
            parts = c.get('name', '').split(' ', 1)
            name = parts[0]
        last = c.get('last_name', '')
        if not last:
            parts = c.get('name', '').split(' ', 1)
            last = parts[1] if len(parts) > 1 else ''

        sl_leads.append({
            'email': c['email'],
            'first_name': name,
            'last_name': last,
            'company_name': c.get('company', ''),
            'website': c.get('domain', ''),
            'custom_fields': {
                'title': c.get('title', ''),
                'location': c.get('location', ''),
                'linkedin_url': c.get('linkedin_url', ''),
            }
        })

    print(f"\nAdding {len(sl_leads)} leads to campaign {CID}...")
    result = await sl.add_leads_to_campaign(CID, sl_leads)
    print(f"Result: {result}")
    print(f"\nDone! {len(sl_leads)} new contacts added to campaign")


if __name__ == '__main__':
    asyncio.run(main())
