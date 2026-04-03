#!/usr/bin/env python3
"""FindyMail enrichment — concurrent API calls. Run on Hetzner."""
import json, asyncio, os, sys

try:
    import httpx
except ImportError:
    os.system(f'{sys.executable} -m pip install httpx -q')
    import httpx

FINDYMAIL_KEY = os.environ.get('FINDYMAIL_API_KEY', 'dSxRrqArQIsG2E5zba36HLTy0pBk1bGZra5ZDtykea70c139')
BASE_URL = 'https://app.findymail.com/api'
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EXPORTS_DIR = os.path.join(SCRIPT_DIR, 'exports')
WORKERS = 5
cache_path = '/tmp/findymail_dm_cache.json'

async def enrich_one(client, p, cache):
    li = (p.get('LinkedIn Profile') or '').strip()
    name = (p.get('Full Name') or '').strip()
    domain = (p.get('Company Domain') or '').strip()
    key = li or f'{name}@{domain}'

    if key in cache:
        email = cache[key].get('email', '')
        return {**p, 'Email': email, 'Email_Verified': cache[key].get('verified', False)}, bool(email)

    try:
        if li and 'linkedin.com' in li:
            r = await client.post(f'{BASE_URL}/search/linkedin',
                json={'linkedin_url': li}, timeout=10)
        elif name and domain:
            parts = name.split()
            r = await client.post(f'{BASE_URL}/search/name',
                json={'first_name': parts[0], 'last_name': parts[-1] if len(parts)>1 else '', 'domain': domain}, timeout=10)
        else:
            return {**p, 'Email': '', 'Email_Verified': False}, False

        d = r.json()
        email = d.get('email', '') or d.get('contact', {}).get('email', '') or ''
        verified = d.get('verified', False) or d.get('contact', {}).get('verified', False)
        cache[key] = {'email': email, 'verified': verified}
        return {**p, 'Email': email, 'Email_Verified': verified}, bool(email)
    except:
        cache[key] = {'email': '', 'verified': False}
        return {**p, 'Email': '', 'Email_Verified': False}, False

async def main():
    with open(os.path.join(EXPORTS_DIR, 'dm_people.json')) as f:
        people = json.load(f)
    print(f'Total: {len(people)}', flush=True)

    cache = {}
    if os.path.exists(cache_path):
        cache = json.load(open(cache_path))
        print(f'Cache: {len(cache)} done', flush=True)

    headers = {'Authorization': f'Bearer {FINDYMAIL_KEY}', 'Content-Type': 'application/json'}
    async with httpx.AsyncClient(headers=headers) as client:
        # Check credits
        r = await client.get(f'{BASE_URL}/credits')
        cb = r.json()
        print(f'Credits: {cb["credits"]}', flush=True)

        sem = asyncio.Semaphore(WORKERS)
        results = [None] * len(people)
        found = 0
        done = 0

        async def worker(idx, p):
            nonlocal found, done
            async with sem:
                result, has_email = await enrich_one(client, p, cache)
                results[idx] = result
                if has_email: found += 1
                done += 1
                if done % 50 == 0:
                    print(f'  {done}/{len(people)} - {found} emails', flush=True)
                    json.dump(cache, open(cache_path, 'w'))

        await asyncio.gather(*[worker(i, p) for i, p in enumerate(people)])

    json.dump(cache, open(cache_path, 'w'))
    json.dump(results, open(os.path.join(EXPORTS_DIR, 'dm_people_with_emails.json'), 'w'), indent=2)

    async with httpx.AsyncClient(headers=headers) as client:
        r = await client.get(f'{BASE_URL}/credits')
        ca = r.json()

    print(f'\nDone! {found}/{len(people)} emails found', flush=True)
    print(f'Credits used: {cb["credits"] - ca["credits"]}', flush=True)

asyncio.run(main())
