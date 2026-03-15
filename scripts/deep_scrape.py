#!/usr/bin/env python3
"""
Multi-page website scraper for EasyStaff corridor scoring.

Scrapes 5 page types per domain: homepage, about, contact, team, locations.
Tries multiple URL patterns per type, keeps first that returns content.

Output: /tmp/deep_scrape_v7.json  (additive cache)
Input:  top N domains from company analysis CSV, or --domains file

Usage (inside Docker on server):
  python3 scripts/deep_scrape.py                          # top 300 from UAE-PK analysis
  python3 scripts/deep_scrape.py --domains /tmp/top.txt   # custom domain list
  python3 scripts/deep_scrape.py --limit 500              # top 500
  python3 scripts/deep_scrape.py --corridor au-philippines # different corridor
"""
import asyncio
import json
import os
import re
import sys
import time

# Allow running from /scripts/ inside Docker (app is at /app)
if os.path.isdir('/app') and '/app' not in sys.path:
    sys.path.insert(0, '/app')

CACHE_FILE = '/tmp/deep_scrape_v7.json'
SCRAPE_CACHE = '/tmp/uae_pk_v6_scrape.json'

PAGE_PATHS = {
    'homepage': [''],
    'about': ['/about', '/about-us', '/about-us/', '/company', '/who-we-are'],
    'contact': ['/contact', '/contact-us', '/contact-us/', '/get-in-touch'],
    'team': ['/team', '/our-team', '/people', '/our-people', '/leadership'],
    'locations': ['/locations', '/offices', '/global', '/global-offices', '/where-we-are'],
}


def strip_html(html):
    if not html:
        return ''
    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()[:10000]


async def main():
    import httpx
    from app.core.config import settings

    # Parse args
    domains_file = None
    limit = 300
    corridor = 'uae_pakistan'
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == '--domains' and i + 1 < len(args):
            domains_file = args[i + 1]
            i += 2
        elif args[i] == '--limit' and i + 1 < len(args):
            limit = int(args[i + 1])
            i += 2
        elif args[i] == '--corridor' and i + 1 < len(args):
            corridor = args[i + 1].replace('-', '_')
            i += 2
        else:
            i += 1

    # Load cache
    cache = {}
    if os.path.exists(CACHE_FILE):
        cache = json.load(open(CACHE_FILE))
        print(f"Loaded deep scrape cache: {len(cache)} domains")

    # Determine domains
    if domains_file:
        with open(domains_file) as f:
            domains = [line.strip() for line in f if line.strip()]
    else:
        import csv
        csv_file = f'/tmp/{corridor}_v7_company_analysis.csv'
        if not os.path.exists(csv_file):
            print(f"No analysis CSV at {csv_file}. Use --domains or run scoring first.")
            return
        with open(csv_file) as f:
            rows = list(csv.DictReader(f))
        rows.sort(key=lambda r: -float(r.get('score', 0)))
        domains = [r['domain'] for r in rows if r['domain'] and r['domain'] not in cache][:limit]

    print(f"Domains to deep-scrape: {len(domains)}")
    if not domains:
        print("Nothing to scrape — all in cache.")
        return

    # Proxy setup
    proxy_password = getattr(settings, 'APIFY_PROXY_PASSWORD', None)
    client_kwargs = {
        'verify': False,
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        },
    }
    if proxy_password:
        client_kwargs['proxy'] = f'http://auto:{proxy_password}@proxy.apify.com:8000'
        print("Using Apify proxy")

    sem = asyncio.Semaphore(10)  # 10 concurrent (not 20 — multi-page = 5x requests per domain)
    ok = errors = 0
    t0 = time.time()

    async def scrape_domain(domain):
        nonlocal ok, errors
        result = {'pages': {}}
        async with sem:
            for page_type, paths in PAGE_PATHS.items():
                for path in paths:
                    url = f'https://{domain}{path}'
                    try:
                        async with httpx.AsyncClient(**client_kwargs) as client:
                            resp = await client.get(url, timeout=10.0, follow_redirects=True)
                            if 200 <= resp.status_code < 400 and len(resp.text) > 200:
                                html = resp.text
                                title_m = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
                                title = title_m.group(1).strip()[:200] if title_m else ''
                                text = strip_html(html)
                                if text and len(text) > 50:
                                    result['pages'][page_type] = {
                                        'path': path,
                                        'title': title,
                                        'text': text,
                                    }
                                    break  # Found a valid page for this type
                    except Exception:
                        pass
                    await asyncio.sleep(0.3)  # Rate limit per same host

        if result['pages']:
            ok += 1
        else:
            errors += 1
        cache[domain] = result

    # Process in batches of 30
    batch_size = 30
    for i in range(0, len(domains), batch_size):
        batch = domains[i:i + batch_size]
        await asyncio.gather(*[scrape_domain(d) for d in batch])
        elapsed = time.time() - t0
        rate = (i + len(batch)) / max(elapsed, 1) * 60
        print(f"  [{i + len(batch)}/{len(domains)}] {ok} ok, {errors} err | "
              f"{elapsed:.0f}s elapsed | ~{rate:.0f} domains/min")

        # Save after each batch
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache, f, ensure_ascii=False)

    print(f"\nDone: {ok} scraped, {errors} errors in {time.time() - t0:.0f}s")
    print(f"Total in cache: {len(cache)} domains")
    print(f"Saved to: {CACHE_FILE}")


if __name__ == '__main__':
    asyncio.run(main())
