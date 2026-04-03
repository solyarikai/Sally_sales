#!/usr/bin/env python3
"""FindyMail enrichment — runs on HOST, not inside Docker.

Persistent cache at /home/leadokol/magnum-opus-project/repo/scripts/findymail_email_cache.json
Contacts from /home/leadokol/magnum-opus-project/repo/scripts/findymail_contacts.json
Auto-uploads to SmartLead campaign 3048388 when done.
"""
import asyncio
import json
import os
import time
import httpx

SCRIPTS = '/home/leadokol/magnum-opus-project/repo/scripts'
CACHE_FILE = f'{SCRIPTS}/findymail_email_cache.json'
CONTACTS_FILE = f'{SCRIPTS}/findymail_contacts.json'
RESULTS_FILE = f'{SCRIPTS}/findymail_results.json'
LOG_FILE = '/home/leadokol/findymail_log.txt'

FINDYMAIL_KEY = os.environ.get('FINDYMAIL_API_KEY', 'Gocy3c70tCEJN0CSzirLWUkmF4OpX6lfefV40wRk5827b184')
SMARTLEAD_KEY = os.environ.get('SMARTLEAD_API_KEY', 'eaa086b6-b7c0-4b2f-a6e9-b183c81122d5_638f7e5')
CAMPAIGN_ID = '3048388'

CONCURRENT = 5
BATCH_SIZE = 50


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, 'a') as f:
        f.write(line + '\n')


def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            cache = json.load(open(CACHE_FILE))
            log(f"Cache loaded: {len(cache)} entries ({sum(1 for v in cache.values() if v)} emails)")
            return cache
        except (json.JSONDecodeError, ValueError):
            log("Cache corrupted, starting fresh")
    return {}


def save_cache(cache):
    tmp = CACHE_FILE + '.tmp'
    json.dump(cache, open(tmp, 'w'))
    os.replace(tmp, CACHE_FILE)


def load_contacts():
    if not os.path.exists(CONTACTS_FILE):
        log(f"ERROR: {CONTACTS_FILE} not found!")
        raise SystemExit(1)
    contacts = json.load(open(CONTACTS_FILE))
    log(f"Contacts: {len(contacts)}")
    return contacts


async def findymail_lookup(client, linkedin_url):
    """Direct HTTP call to FindyMail API."""
    resp = await client.post(
        'https://app.findymail.com/api/search/linkedin',
        json={'linkedin_url': linkedin_url},
        headers={'Authorization': f'Bearer {FINDYMAIL_KEY}', 'Content-Type': 'application/json'},
        timeout=30,
    )
    if resp.status_code == 402:
        raise Exception('402_CREDITS_EXHAUSTED')
    if resp.status_code == 429:
        raise Exception('429_RATE_LIMITED')
    resp.raise_for_status()
    data = resp.json()
    contact = data.get('contact', {})
    return data.get('email') or contact.get('email') or ''


async def enrich_one(client, li_url, cache, sem):
    async with sem:
        for attempt in range(3):
            try:
                email = await findymail_lookup(client, li_url)
                cache[li_url] = email
                return email, None
            except Exception as e:
                err = str(e)
                if '402' in err:
                    cache[li_url] = ''
                    return '', 'credits'
                if '429' in err:
                    await asyncio.sleep(5 * (attempt + 1))
                    continue
                if attempt == 2:
                    cache[li_url] = ''
                    return '', 'error'
                await asyncio.sleep(2)
    cache[li_url] = ''
    return '', 'error'


async def upload_to_smartlead(contacts_with_email):
    async with httpx.AsyncClient() as client:
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

        log(f"Uploading {len(sl_leads)} leads to SmartLead campaign {CAMPAIGN_ID}...")
        total_added = 0
        for i in range(0, len(sl_leads), 100):
            batch = sl_leads[i:i + 100]
            try:
                resp = await client.post(
                    f'https://server.smartlead.ai/api/v1/campaigns/{CAMPAIGN_ID}/leads?api_key={SMARTLEAD_KEY}',
                    json={'lead_list': batch},
                    timeout=30,
                )
                data = resp.json()
                if data.get('ok') or resp.status_code == 200:
                    added = data.get('data', {}).get('total_leads', len(batch))
                    total_added += added
                    log(f"  Batch {i//100+1}: {added} uploaded")
                else:
                    log(f"  Batch {i//100+1}: {data}")
            except Exception as e:
                log(f"  Batch {i//100+1}: ERROR {e}")
            await asyncio.sleep(1)

        log(f"Done! {total_added} leads uploaded to campaign {CAMPAIGN_ID}")
        log(f"https://app.smartlead.ai/app/email-campaigns-v2/{CAMPAIGN_ID}/leads")


async def main():
    contacts = load_contacts()
    cache = load_cache()

    # Split cached vs new
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

    log(f"Cache: {cached_hits} emails, {cached_misses} no-email, {len(to_process)} need API")

    if to_process:
        log(f"Processing {len(to_process)} via FindyMail...")
        sem = asyncio.Semaphore(CONCURRENT)
        found = 0
        failed = 0
        t0 = time.time()

        async with httpx.AsyncClient() as client:
            for i in range(0, len(to_process), BATCH_SIZE):
                batch = to_process[i:i + BATCH_SIZE]
                results = await asyncio.gather(
                    *[enrich_one(client, c['linkedin_url'], cache, sem) for c in batch]
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

                log(f"  [{processed}/{total}] found={found} no_email={failed} "
                    f"rate={rate:.1f}/s hit={found*100//max(1,processed)}% ETA={eta:.0f}s")

                save_cache(cache)

                if credit_error:
                    log("STOPPING — out of credits")
                    break
    else:
        log("All in cache!")

    with_email = [c for c in contacts if c.get('email')]
    log(f"RESULTS: {len(with_email)} with email / {len(contacts)-len(with_email)} without / {len(contacts)} total")

    json.dump(with_email, open(RESULTS_FILE, 'w'), indent=2, ensure_ascii=False)
    save_cache(cache)
    log(f"Saved to {RESULTS_FILE}")

    if with_email:
        await upload_to_smartlead(with_email)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception:
        import traceback
        log("FATAL ERROR:")
        traceback.print_exc()
        with open(LOG_FILE, 'a') as f:
            traceback.print_exc(file=f)
