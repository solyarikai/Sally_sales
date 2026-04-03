#!/usr/bin/env python3
"""
FindyMail enrichment: find emails for all UAE-PK target contacts by LinkedIn URL.
Writes results to a NEW tab with emails filled in.
"""
import asyncio
import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, '/app')

from app.services.google_sheets_service import GoogleSheetsService
from app.services.findymail_service import FindymailService

SHEET_ID = '1pivHqk1NI-MHdDFSQugfg5olBMKTkBGr_yyjjXlWqKU'
SOURCE_TAB = 'UAE-PK FINAL 0316_1035'
BATCH_SAVE_EVERY = 50  # Save progress every N contacts
CONCURRENT = 5  # Parallel FindyMail requests


async def main():
    gs = GoogleSheetsService()
    fm = FindymailService()
    fm.set_api_key(os.environ.get('FINDYMAIL_API_KEY', ''))

    # Read source data
    print(f"Reading {SOURCE_TAB}...")
    raw = gs.read_sheet_raw(SHEET_ID, SOURCE_TAB)
    headers = raw[0]
    rows = raw[1:]
    col = {h: i for i, h in enumerate(headers)}
    li_idx = col['LinkedIn URL']
    email_idx = col['Email']

    print(f"Total contacts: {len(rows)}")

    # Check for resume file
    resume_file = '/tmp/findymail_uae_pk_progress.json'
    done_urls = {}
    if os.path.exists(resume_file):
        done_urls = json.load(open(resume_file))
        print(f"Resuming: {len(done_urls)} already processed")

    # Process contacts
    found = 0
    failed = 0
    skipped = 0
    sem = asyncio.Semaphore(CONCURRENT)

    async def process_one(row_idx, row):
        nonlocal found, failed, skipped
        li_url = row[li_idx].strip() if li_idx < len(row) else ''
        if not li_url:
            skipped += 1
            return

        # Already processed?
        if li_url in done_urls:
            email = done_urls[li_url]
            if email and email_idx < len(row):
                row[email_idx] = email
            if email:
                found += 1
            skipped += 1
            return

        async with sem:
            try:
                result = await fm.find_email_by_linkedin(li_url)
                email = result.get('email', '') if result else ''
                verified = result.get('verified', False) if result else False

                if email:
                    row[email_idx] = email
                    found += 1
                    done_urls[li_url] = email
                else:
                    failed += 1
                    done_urls[li_url] = ''

            except Exception as e:
                err = str(e)
                if '402' in err or 'credits' in err.lower():
                    print(f"\nFindyMail OUT OF CREDITS at contact {row_idx}")
                    done_urls[li_url] = ''
                    raise
                failed += 1
                done_urls[li_url] = ''

    t0 = time.time()
    tasks = []
    for i, row in enumerate(rows):
        tasks.append(process_one(i, row))

        # Process in batches for progress reporting
        if len(tasks) >= BATCH_SAVE_EVERY:
            await asyncio.gather(*tasks, return_exceptions=True)
            tasks = []

            elapsed = time.time() - t0
            processed = found + failed + skipped
            rate = processed / elapsed if elapsed > 0 else 0
            eta = (len(rows) - processed) / rate if rate > 0 else 0
            print(f"  [{processed}/{len(rows)}] found={found} failed={failed} "
                  f"rate={rate:.1f}/s ETA={eta:.0f}s")

            # Save progress
            json.dump(done_urls, open(resume_file, 'w'))

    # Process remaining
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

    # Final save
    json.dump(done_urls, open(resume_file, 'w'))

    elapsed = time.time() - t0
    print(f"\n=== FINDYMAIL ENRICHMENT COMPLETE ===")
    print(f"Total: {len(rows)}")
    print(f"Found email: {found} ({found/len(rows)*100:.1f}%)")
    print(f"No email: {failed}")
    print(f"Skipped (already had): {skipped}")
    print(f"Time: {elapsed:.0f}s")

    # Write to NEW tab
    ts = datetime.now().strftime('%m%d_%H%M')
    tab_name = f"UAE-PK With Emails {ts}"

    # Filter to only contacts WITH emails
    rows_with_email = [r for r in rows if r[email_idx].strip()]
    rows_without = [r for r in rows if not r[email_idx].strip()]

    print(f"\nWith email: {len(rows_with_email)}")
    print(f"Without email: {len(rows_without)}")

    # Re-rank
    for i, row in enumerate(rows_with_email):
        row[0] = str(i + 1)

    gs._initialize()
    try:
        gs.sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=SHEET_ID,
            body={'requests': [{'addSheet': {'properties': {'title': tab_name}}}]}
        ).execute()
    except Exception as e:
        print(f"Tab warning: {e}")

    data = [headers] + rows_with_email
    for i in range(0, len(data), 500):
        batch = data[i:i + 500]
        gs.sheets_service.spreadsheets().values().update(
            spreadsheetId=SHEET_ID,
            range=f"'{tab_name}'!A{i + 1}",
            valueInputOption='RAW',
            body={'values': batch}
        ).execute()

    print(f"\nWrote {len(rows_with_email)} contacts to '{tab_name}'")

    # Also save as JSON for SmartLead import
    leads_json = []
    for row in rows_with_email:
        leads_json.append({
            'email': row[email_idx],
            'first_name': row[col.get('First Name', 1)],
            'last_name': row[col.get('Last Name', 2)],
            'title': row[col.get('Title', 4)],
            'company': row[col.get('Company', 6)],
            'domain': row[col.get('Domain', 7)],
            'location': row[col.get('Location', 8)],
            'linkedin_url': row[li_idx],
        })
    json.dump(leads_json, open('/tmp/uae_pk_leads_for_smartlead.json', 'w'), indent=2)
    print(f"Saved JSON for SmartLead: /tmp/uae_pk_leads_for_smartlead.json ({len(leads_json)} leads)")


if __name__ == '__main__':
    asyncio.run(main())
