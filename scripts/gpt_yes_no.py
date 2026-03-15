#!/usr/bin/env python3
"""
Simple GPT YES/NO classifier for EasyStaff prospects.

Reads scored companies, asks ONE binary question per company,
saves results. Replaces complex keyword matching for edge cases.

Usage:
  python3 /scripts/gpt_yes_no.py uae-pakistan
  python3 /scripts/gpt_yes_no.py au-philippines
  python3 /scripts/gpt_yes_no.py arabic-southafrica

Cost: ~$0.0001 per company. 5,000 companies = $0.50.
Speed: ~5/sec with 25 concurrent.
"""
import asyncio
import json
import os
import sys
import time

if os.path.isdir('/app') and '/app' not in sys.path:
    sys.path.insert(0, '/app')

DATA_DIR = '/scripts/data' if os.path.isdir('/scripts/data') else '/tmp'

CORRIDOR_CONTEXT = {
    'uae-pakistan': 'UAE companies pay remote contractors in Pakistan',
    'au-philippines': 'Australian companies pay remote contractors in Philippines',
    'arabic-southafrica': 'Gulf companies pay remote contractors in South Africa',
}

PROMPT = """Is this company a good prospect for EasyStaff (cross-border contractor payments)?

COMPANY: {company}
DOMAIN: {domain}
WEBSITE: {text}

Answer ONLY: YES or NO"""


async def main():
    import httpx

    if len(sys.argv) < 2:
        print("Usage: python3 gpt_yes_no.py <corridor>")
        return

    corridor = sys.argv[1]
    slug = corridor.replace('-', '_')
    context = CORRIDOR_CONTEXT.get(corridor, '')
    buyer = corridor.split('-')[0].upper()

    cache_file = f'{DATA_DIR}/{slug}_gpt_yesno.json'
    scored_file = f'{DATA_DIR}/{slug}_v8_scored.json'
    scrape_file = f'{DATA_DIR}/uae_pk_v6_scrape.json'

    # Load cache
    cache = {}
    if os.path.exists(cache_file):
        cache = json.load(open(cache_file))
        print(f"Cache: {len(cache)} domains")

    # Load scored contacts
    scored = json.load(open(scored_file))
    scrape = json.load(open(scrape_file))

    # Get unique domains to check
    seen = set()
    to_check = []
    for s in scored:
        dom = s.get('domain', '')
        if dom and dom not in seen and dom not in cache:
            seen.add(dom)
            sd = scrape.get(dom, {})
            text = (sd.get('text') or '')[:1000]
            if text:
                to_check.append((dom, s.get('company', dom), text))

    print(f"To check: {len(to_check)} (cached: {len(cache)})")
    if not to_check:
        print("All cached.")
        return

    api_key = os.environ.get('OPENAI_API_KEY', '')
    sem = asyncio.Semaphore(25)
    ok = errors = 0
    t0 = time.time()

    async def check_one(client, domain, company, text):
        nonlocal ok, errors
        prompt = PROMPT.format(context=context, buyer=buyer, company=company, domain=domain, text=text)
        async with sem:
            try:
                resp = await client.post(
                    'https://api.openai.com/v1/chat/completions',
                    headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
                    json={'model': 'gpt-4o-mini', 'messages': [{'role': 'user', 'content': prompt}],
                          'temperature': 0.1, 'max_tokens': 5},
                    timeout=15.0,
                )
                if resp.status_code == 200:
                    answer = resp.json()['choices'][0]['message']['content'].strip().upper()
                    cache[domain] = 'YES' if answer.startswith('YES') else 'NO'
                    ok += 1
                else:
                    errors += 1
            except Exception:
                errors += 1

    async with httpx.AsyncClient(verify=False) as client:
        batch = 100
        for i in range(0, len(to_check), batch):
            b = to_check[i:i + batch]
            await asyncio.gather(*[check_one(client, d, c, t) for d, c, t in b])
            with open(cache_file, 'w') as f:
                json.dump(cache, f)
            elapsed = time.time() - t0
            print(f"  [{i + len(b)}/{len(to_check)}] {ok} ok, {errors} err | {elapsed:.0f}s")

    # Stats
    yes_count = sum(1 for v in cache.values() if v == 'YES')
    no_count = sum(1 for v in cache.values() if v == 'NO')
    print(f"\nDone: {ok} ok, {errors} err in {time.time() - t0:.0f}s")
    print(f"YES: {yes_count}, NO: {no_count}")
    print(f"Saved: {cache_file}")


if __name__ == '__main__':
    asyncio.run(main())
