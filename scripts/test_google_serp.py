"""
Test Google SERP via Apify Proxy — Standalone
==============================================
Tests Apify SERP proxy with Deliryo-relevant queries.
Measures: domains found per query, response time, cost.
Does NOT touch the database.

Apify SERP pricing: ~$0.0017 per Google SERP request (charged per page load).

Usage:
  python scripts/test_google_serp.py
  # or on Hetzner:
  docker run --rm --name test-serp \
    python:3.11 bash -c 'pip install -q httpx beautifulsoup4 && python /scripts/test_google_serp.py'
"""
import asyncio
import logging
import random
import re
import time
from typing import Set
from urllib.parse import quote_plus, urlparse

import httpx
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("test_serp")

# ---------------------------------------------------------------------------
# Apify proxy config
# ---------------------------------------------------------------------------
# In Apify, the proxy password IS the API token.
# Personal key: apify_api_pMz9L7dexD8OT6ZM41j9bPtvTrSOQ10jLwGJ
# Org key:      apify_api_GY8SYEybE2wOTarb6dQNzEM04XWUfA2l8b3f
APIFY_PROXY_PASSWORD = "apify_proxy_zZ12PNY7illL44MXT8Cf3vKetkI5I62Oupn2"  # proxy-specific password (NOT API token)
APIFY_PROXY_HOST = "proxy.apify.com"
APIFY_PROXY_PORT = 8000

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]

# ---------------------------------------------------------------------------
# Deliryo test queries — mix of English + Russian, broad + narrow
# ---------------------------------------------------------------------------
TEST_QUERIES = [
    'family office Russia',
    '"family office" Москва',
    'wealth management HNWI Russia',
    '"фэмили офис" управление капиталом',
    'private banking Russia "high net worth"',
]

# ---------------------------------------------------------------------------
# Domain extraction (copied from search_service.py to keep standalone)
# ---------------------------------------------------------------------------
TRASH_PATTERNS = [
    r"^(google|yandex|bing|yahoo|facebook|instagram|twitter|tiktok|youtube|wikipedia|linkedin|vk\.com|ok\.ru)\.",
    r"\.(gov|edu|mil)$",
    r"^(mail|web|ftp|ns\d|dns|proxy|cdn)\.",
]
_trash_re = [re.compile(p) for p in TRASH_PATTERNS]


def normalize_domain(raw: str) -> str:
    d = raw.lower().strip().rstrip(".")
    if d.startswith("www."):
        d = d[4:]
    return d


def matches_trash(domain: str) -> bool:
    return any(r.search(domain) for r in _trash_re)


def extract_domains(html: str) -> Set[str]:
    domains = set()
    soup = BeautifulSoup(html, "html.parser")

    # Method 1: links
    for link in soup.find_all("a", href=True):
        href = link["href"]
        skip = ["google.com", "google.ru", "gstatic.com", "youtube.com",
                "webcache.", "/search?", "javascript:", "#"]
        if any(x in href for x in skip):
            if "/url?q=" in href:
                m = re.search(r"/url\?q=([^&]+)", href)
                if m:
                    href = m.group(1)
                else:
                    continue
            else:
                continue
        try:
            parsed = urlparse(href)
            if parsed.scheme in ("http", "https") and parsed.netloc:
                d = normalize_domain(parsed.netloc)
                if d and not matches_trash(d):
                    domains.add(d)
        except Exception:
            continue

    # Method 2: cite elements
    for cite in soup.find_all("cite"):
        text = cite.get_text()
        m = re.search(r"(?:https?://)?(?:www\.)?([a-zA-Z0-9][-a-zA-Z0-9]*\.[a-zA-Z]{2,})", text)
        if m:
            d = normalize_domain(m.group(1))
            if d and not matches_trash(d):
                domains.add(d)

    return domains


def check_captcha(html: str) -> bool:
    indicators = ["unusual traffic", "captcha", "recaptcha", "sorry/index",
                   "detected unusual traffic", "automated queries", "please verify"]
    html_lower = html.lower()
    return any(ind in html_lower for ind in indicators)


# ---------------------------------------------------------------------------
# Main test
# ---------------------------------------------------------------------------
async def test_query(query: str, max_pages: int = 1) -> dict:
    """Run a single Google SERP query via Apify proxy. Returns stats."""
    session_id = f"serp_{random.randint(10000, 99999)}"
    proxy_url = (
        f"http://groups-GOOGLE_SERP,session-{session_id}:"
        f"{APIFY_PROXY_PASSWORD}@"
        f"{APIFY_PROXY_HOST}:{APIFY_PROXY_PORT}"
    )

    all_domains: Set[str] = set()
    pages_fetched = 0
    captcha = False
    errors = []
    t0 = time.monotonic()

    for page in range(max_pages):
        start = page * 100  # num=100 per page
        url = f"http://www.google.com/search?q={quote_plus(query)}&num=100&start={start}&hl=ru"
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
        }

        try:
            async with httpx.AsyncClient(
                proxy=proxy_url,
                timeout=30.0,
                follow_redirects=True,
            ) as client:
                resp = await client.get(url, headers=headers)

            if resp.status_code == 429:
                errors.append(f"page {page}: 429 rate limit")
                break
            elif resp.status_code != 200:
                errors.append(f"page {page}: HTTP {resp.status_code}")
                break

            html = resp.text
            if check_captcha(html):
                captcha = True
                errors.append(f"page {page}: CAPTCHA detected")
                break

            domains = extract_domains(html)
            new = domains - all_domains
            all_domains.update(domains)
            pages_fetched += 1

            logger.info(f"  Page {page}: {len(domains)} domains ({len(new)} new)")

            if not new and page > 0:
                break

            if page < max_pages - 1:
                await asyncio.sleep(random.uniform(1.5, 3.0))

        except Exception as e:
            errors.append(f"page {page}: {type(e).__name__}: {e}")
            break

    elapsed = time.monotonic() - t0
    cost_estimate = pages_fetched * 0.0017  # ~$0.0017 per SERP page

    return {
        "query": query,
        "domains_found": len(all_domains),
        "pages_fetched": pages_fetched,
        "elapsed_sec": round(elapsed, 2),
        "cost_usd": round(cost_estimate, 4),
        "captcha": captcha,
        "errors": errors,
        "sample_domains": sorted(list(all_domains))[:15],
    }


async def main():
    logger.info("=" * 60)
    logger.info("GOOGLE SERP VIA APIFY — TEST RUN")
    logger.info(f"Queries: {len(TEST_QUERIES)}")
    logger.info(f"Max pages per query: 1 (num=100 results per page)")
    logger.info(f"Estimated cost: ~${len(TEST_QUERIES) * 0.0017:.3f}")
    logger.info("=" * 60)

    results = []
    total_domains = set()

    for i, query in enumerate(TEST_QUERIES):
        logger.info(f"\n[{i+1}/{len(TEST_QUERIES)}] Query: {query}")
        result = await test_query(query, max_pages=1)
        results.append(result)
        total_domains.update(result["sample_domains"])  # just for unique count from samples

        logger.info(
            f"  -> {result['domains_found']} domains, "
            f"{result['elapsed_sec']}s, "
            f"~${result['cost_usd']}, "
            f"captcha={result['captcha']}"
        )
        if result["errors"]:
            logger.warning(f"  Errors: {result['errors']}")
        if result["sample_domains"]:
            logger.info(f"  Sample: {', '.join(result['sample_domains'][:5])}")

        # Pause between queries
        if i < len(TEST_QUERIES) - 1:
            await asyncio.sleep(random.uniform(2.0, 4.0))

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    total_cost = sum(r["cost_usd"] for r in results)
    total_found = sum(r["domains_found"] for r in results)
    total_pages = sum(r["pages_fetched"] for r in results)
    captcha_count = sum(1 for r in results if r["captcha"])
    error_count = sum(len(r["errors"]) for r in results)

    logger.info(f"Queries run:      {len(results)}")
    logger.info(f"Pages fetched:    {total_pages}")
    logger.info(f"Total domains:    {total_found} (with duplicates across queries)")
    logger.info(f"CAPTCHAs:         {captcha_count}")
    logger.info(f"Errors:           {error_count}")
    logger.info(f"Total cost:       ~${total_cost:.4f}")
    logger.info(f"Cost per query:   ~${total_cost/max(len(results),1):.4f}")
    logger.info(f"Domains per $:    ~{total_found/max(total_cost, 0.001):.0f}")

    logger.info("\nPer-query breakdown:")
    for r in results:
        status = "OK" if not r["errors"] else f"ERRORS: {r['errors']}"
        logger.info(f"  [{r['domains_found']:3d} domains] {r['query'][:50]:50s} | {status}")

    # If all queries worked, estimate full Deliryo Google SERP run
    if captcha_count == 0 and total_found > 0:
        # Assume ~200 queries for full Deliryo (regions × terms), 1 page each
        est_queries = 200
        est_cost = est_queries * 0.0017
        avg_domains = total_found / max(len(results), 1)
        est_domains = int(avg_domains * est_queries * 0.6)  # 0.6 = overlap factor
        logger.info(f"\n--- FULL RUN ESTIMATE ---")
        logger.info(f"  Queries: ~{est_queries}")
        logger.info(f"  Cost:    ~${est_cost:.2f}")
        logger.info(f"  Domains: ~{est_domains} (after dedup ~60%)")
    else:
        logger.info("\nCAPTCHA or errors detected — check proxy config before full run")


if __name__ == "__main__":
    asyncio.run(main())
