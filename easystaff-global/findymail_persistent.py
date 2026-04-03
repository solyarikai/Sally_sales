#!/usr/bin/env python3
"""FindyMail enrichment with PERSISTENT cache that survives container restarts.

Cache stored at /scripts/findymail_email_cache.json (host-mounted volume).
Input read from Google Sheet tab 'UAE-PK GOD SCORED 0316_1856'.
Applies enterprise blacklist + removal list filtering.
Does NOT upload to SmartLead — separate step.
"""
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, '/app')
from app.services.findymail_service import FindymailService
from app.services.google_sheets_service import GoogleSheetsService

# Persistent paths (survive container restart via /scripts mount)
CACHE_FILE = '/scripts/findymail_email_cache.json'
CONTACTS_FILE = '/scripts/findymail_contacts.json'
RESULTS_FILE = '/scripts/findymail_results.json'

SHEET_ID = '1pivHqk1NI-MHdDFSQugfg5olBMKTkBGr_yyjjXlWqKU'
SOURCE_TAB = 'UAE-PK GOD SCORED 0316_1856'
KEEP_FILE = '/scripts/uae_pk_FINAL_keep.json'  # 4,411 validated IDs

CONCURRENT = 5
BATCH_SIZE = 50


def load_cache():
    """Load persistent email cache."""
    if os.path.exists(CACHE_FILE):
        try:
            cache = json.load(open(CACHE_FILE))
            print(f"Loaded cache: {len(cache)} entries ({sum(1 for v in cache.values() if v)} with email)")
            return cache
        except (json.JSONDecodeError, ValueError):
            print("Cache file corrupted, starting fresh")
    return {}


def save_cache(cache):
    """Save cache to persistent storage."""
    tmp = CACHE_FILE + '.tmp'
    json.dump(cache, open(tmp, 'w'), indent=2)
    os.replace(tmp, CACHE_FILE)


def load_contacts():
    """Load contacts from Google Sheet, filter to validated 4K set, save persistently."""
    # Check if we already have a contacts file
    if os.path.exists(CONTACTS_FILE):
        try:
            contacts = json.load(open(CONTACTS_FILE))
            print(f"Loaded {len(contacts)} contacts from persistent file")
            return contacts
        except (json.JSONDecodeError, ValueError):
            print("Contacts file corrupted, rebuilding...")

    # Load the FINAL_keep IDs (validated contacts only)
    if not os.path.exists(KEEP_FILE):
        print(f"ERROR: {KEEP_FILE} not found! Copy uae_pk_FINAL_keep.json to /scripts/ first.")
        sys.exit(1)
    keep_ids = set(json.load(open(KEEP_FILE)))
    print(f"Keep list: {len(keep_ids)} validated IDs")

    print("Loading contacts from Google Sheet...")
    gs = GoogleSheetsService()
    raw = gs.read_sheet_raw(SHEET_ID, SOURCE_TAB)
    headers = raw[0]
    rows = raw[1:]
    print(f"Sheet: {len(rows)} rows, headers: {headers[:8]}")

    col = {h.strip(): i for i, h in enumerate(headers)}

    def g(row, name):
        idx = col.get(name, -1)
        return (row[idx] if 0 <= idx < len(row) else '').strip()

    # Load blacklist
    blacklist_domains = set()
    for bl_path in ['/scripts/data/enterprise_blacklist.json', '/app/../scripts/data/enterprise_blacklist.json']:
        if os.path.exists(bl_path):
            bl = json.load(open(bl_path))
            blacklist_domains = set(bl) if isinstance(bl, list) else set(bl.get('domains', []))
            print(f"Blacklist: {len(blacklist_domains)} domains from {bl_path}")
            break

    contacts = []
    skipped_not_validated = 0
    skipped_bl = 0
    skipped_no_li = 0
    for row in rows:
        rank = g(row, 'Rank') or g(row, '#')

        # Only process validated contacts
        if rank not in keep_ids:
            skipped_not_validated += 1
            continue

        domain = g(row, 'Domain').lower()
        linkedin_url = g(row, 'LinkedIn URL') or g(row, 'Person Linkedin Url')

        if domain in blacklist_domains:
            skipped_bl += 1
            continue
        if not linkedin_url:
            skipped_no_li += 1
            continue

        contacts.append({
            'rank': rank,
            'first_name': g(row, 'First Name'),
            'last_name': g(row, 'Last Name'),
            'title': g(row, 'Title'),
            'company': g(row, 'Company'),
            'domain': domain,
            'location': g(row, 'Location'),
            'linkedin_url': linkedin_url,
        })

    print(f"Contacts: {len(contacts)} validated")
    print(f"  Skipped: {skipped_not_validated} not validated, {skipped_bl} blacklisted, {skipped_no_li} no LinkedIn")

    # Save to persistent file
    json.dump(contacts, open(CONTACTS_FILE, 'w'), indent=2, ensure_ascii=False)
    print(f"Saved to {CONTACTS_FILE}")
    return contacts


CAMPAIGN_ID = '3048388'


async def enrich_one(fm, li_url, cache, sem):
    """Enrich a single LinkedIn URL. Returns (email_or_empty, error_type)."""
    async with sem:
        for attempt in range(3):
            try:
                result = await fm.find_email_by_linkedin(li_url)
                email = (result.get('email') or '') if result else ''
                cache[li_url] = email
                return email, None
            except Exception as e:
                err = str(e)
                if '402' in err:
                    cache[li_url] = ''
                    return '', 'credits'
                if '429' in err or 'rate' in err.lower():
                    await asyncio.sleep(5 * (attempt + 1))
                    continue
                if attempt == 2:
                    cache[li_url] = ''
                    print(f"    ERR after 3 tries: {li_url[:60]} — {err[:80]}")
                    return '', 'error'
                await asyncio.sleep(2)
    cache[li_url] = ''
    return '', 'error'


async def upload_to_smartlead(contacts_with_email):
    """Upload enriched contacts to SmartLead campaign."""
    from app.services.smartlead_service import SmartleadService
    sl = SmartleadService()

    sl_leads = [{
        'email': c['email'],
        'first_name': c.get('first_name', ''),
        'last_name': c.get('last_name', ''),
        'company_name': c.get('company', ''),
        'website': c.get('domain', ''),
        'custom_fields': {
            'title': c.get('title', ''),
            'location': c.get('location', ''),
            'linkedin_url': c.get('linkedin_url', ''),
        }
    } for c in contacts_with_email]

    print(f"\nUploading {len(sl_leads)} leads to campaign {CAMPAIGN_ID}...")
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
    print(f"https://app.smartlead.ai/app/email-campaigns-v2/{CAMPAIGN_ID}/leads")


async def main():
    contacts = load_contacts()
    cache = load_cache()

    fm = FindymailService()
    fm.set_api_key(os.environ.get('FINDYMAIL_API_KEY', ''))
    sem = asyncio.Semaphore(CONCURRENT)

    # Split: cached vs need API
    to_process = []
    cached_hits = 0
    cached_misses = 0

    for c in contacts:
        li = c['linkedin_url']
        if li in cache:
            if cache[li]:
                c['email'] = cache[li]
                cached_hits += 1
            else:
                cached_misses += 1
        else:
            to_process.append(c)

    print(f"\nCache: {cached_hits} emails, {cached_misses} no-email, {len(to_process)} need API")

    if to_process:
        print(f"Processing {len(to_process)} contacts...")
        found = 0
        failed = 0
        t0 = time.time()

        for i in range(0, len(to_process), BATCH_SIZE):
            batch = to_process[i:i + BATCH_SIZE]
            results = await asyncio.gather(
                *[enrich_one(fm, c['linkedin_url'], cache, sem) for c in batch]
            )

            credit_error = False
            for j, (email, err_type) in enumerate(results):
                if email:
                    batch[j]['email'] = email
                    found += 1
                else:
                    failed += 1
                if err_type == 'credits':
                    credit_error = True

            processed = found + failed
            total = len(to_process)
            elapsed = time.time() - t0
            rate = processed / elapsed if elapsed > 0 else 0
            eta = (total - processed) / rate if rate > 0 else 0

            print(f"  [{processed}/{total}] found={found} failed={failed} "
                  f"rate={rate:.1f}/s hit={found*100//max(1,processed)}% ETA={eta:.0f}s")

            save_cache(cache)

            if credit_error:
                print("STOPPING — out of credits.")
                break
    else:
        print("All contacts in cache!")

    # Results
    with_email = [c for c in contacts if c.get('email')]
    print(f"\n{'='*60}")
    print(f"RESULTS: {len(with_email)} with email / {len(contacts) - len(with_email)} without / {len(contacts)} total")
    print(f"Hit rate: {len(with_email)*100 / max(1, len(contacts)):.1f}%")
    print(f"Cache: {len(cache)} entries")
    print(f"{'='*60}")

    json.dump(with_email, open(RESULTS_FILE, 'w'), indent=2, ensure_ascii=False)
    print(f"Results: {RESULTS_FILE}")

    # Auto-upload to SmartLead
    if with_email:
        await upload_to_smartlead(with_email)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception as e:
        import traceback
        print(f"\n!!! FATAL ERROR !!!")
        traceback.print_exc()
        # Save whatever cache we have
        try:
            cache_path = CACHE_FILE
            if os.path.exists(cache_path):
                d = json.load(open(cache_path))
                print(f"Cache preserved: {len(d)} entries")
        except Exception:
            pass
