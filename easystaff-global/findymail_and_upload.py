#!/usr/bin/env python3
"""FindyMail enrichment + SmartLead upload for UAE-PK corridor.
Reads /tmp/uae_pk_for_findymail_final.json, finds emails, uploads to campaign."""
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, '/app')
from app.services.findymail_service import FindymailService
from app.services.smartlead_service import SmartleadService

CAMPAIGN_ID = '3043938'
CONCURRENT = 5
LEADS_FILE = '/tmp/uae_pk_for_findymail_final.json'
PROGRESS_FILE = '/tmp/findymail_final_progress.json'


async def main():
    fm = FindymailService()
    fm.set_api_key(os.environ.get('FINDYMAIL_API_KEY', ''))
    sl = SmartleadService()

    leads = json.load(open(LEADS_FILE))
    print(f"Total leads: {len(leads)}")

    # Resume from progress
    done = {}
    if os.path.exists(PROGRESS_FILE):
        done = json.load(open(PROGRESS_FILE))
        print(f"Resuming: {len(done)} already processed")

    sem = asyncio.Semaphore(CONCURRENT)
    found = 0
    failed = 0
    skipped = 0

    async def enrich(lead):
        nonlocal found, failed, skipped
        li = lead.get('linkedin_url', '')
        if not li:
            failed += 1
            return
        if li in done:
            email = done[li]
            if email:
                lead['email'] = email
                found += 1
            else:
                failed += 1
            skipped += 1
            return

        async with sem:
            try:
                result = await fm.find_email_by_linkedin(li)
                email = result.get('email', '') if result else ''
                if email:
                    lead['email'] = email
                    found += 1
                    done[li] = email
                else:
                    failed += 1
                    done[li] = ''
            except Exception as e:
                if '402' in str(e):
                    print(f"OUT OF CREDITS at {found + failed + skipped}")
                    raise
                failed += 1
                done[li] = ''

    t0 = time.time()
    batch_size = 50
    tasks = [enrich(l) for l in leads]
    for i in range(0, len(tasks), batch_size):
        await asyncio.gather(*tasks[i:i + batch_size], return_exceptions=True)
        processed = found + failed + skipped
        rate = processed / (time.time() - t0) if time.time() - t0 > 0 else 0
        eta = (len(leads) - processed) / rate if rate > 0 else 0
        print(f"  [{processed}/{len(leads)}] found={found} failed={failed} rate={rate:.1f}/s ETA={eta:.0f}s")
        json.dump(done, open(PROGRESS_FILE, 'w'))

    json.dump(done, open(PROGRESS_FILE, 'w'))
    elapsed = time.time() - t0
    print(f"\nFindyMail done in {elapsed:.0f}s")
    print(f"Found: {found}, Failed: {failed}, Rate: {found * 100 / max(1, found + failed):.0f}%")

    # Upload to SmartLead
    with_email = [l for l in leads if l.get('email')]
    print(f"\nUploading {len(with_email)} leads to campaign {CAMPAIGN_ID}...")

    sl_leads = [{
        'email': l['email'],
        'first_name': l.get('first_name', ''),
        'last_name': l.get('last_name', ''),
        'company_name': l.get('company', ''),
        'website': l.get('domain', ''),
        'custom_fields': {
            'title': l.get('title', ''),
            'location': l.get('location', ''),
            'linkedin_url': l.get('linkedin_url', ''),
        }
    } for l in with_email]

    total_added = 0
    for i in range(0, len(sl_leads), 100):
        batch = sl_leads[i:i + 100]
        try:
            result = await sl.add_leads_to_campaign(CAMPAIGN_ID, batch)
            if result.get('success'):
                total_added += result.get('data', {}).get('total_leads', len(batch))
                print(f"  Batch {i // 100 + 1}: uploaded {len(batch)}")
        except Exception as e:
            print(f"  Batch {i // 100 + 1}: ERROR - {e}")
        await asyncio.sleep(1)

    print(f"\nDone! {total_added} leads added to campaign {CAMPAIGN_ID}")
    print(f"Campaign: https://app.smartlead.ai/app/email-campaigns-v2/{CAMPAIGN_ID}/analytics")


if __name__ == '__main__':
    asyncio.run(main())
