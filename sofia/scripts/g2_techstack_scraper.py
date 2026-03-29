#!/usr/bin/env python3
"""
G2 + Tech Stack Scraper → Pipeline
===================================
Scrapes G2/Capterra category pages for influencer marketing tools,
then searches Google for tech stack signals (companies using competitor tools).
Deduplicates against project blacklist and existing discovered_companies.
Creates gathering runs via backend API.

Usage (on Hetzner):
    set -a && source .env && set +a
    python3 -u sofia/scripts/g2_techstack_scraper.py
"""

import os
import re
import sys
import json
import time
import logging
import requests
from urllib.parse import urlparse, urljoin
from typing import List, Set, Dict

# ── Config ───────────────────────────────────────────────────
PROJECT_ID = 42
API_BASE = os.getenv("API_BASE", "http://localhost:8000/api")
API_KEY = os.getenv("API_KEY", "")
HEADERS = {"X-Company-Id": "1", "Content-Type": "application/json"}
if API_KEY:
    HEADERS["Authorization"] = f"Bearer {API_KEY}"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

# ── G2 Categories to scrape ──────────────────────────────────
G2_CATEGORIES = [
    "influencer-marketing",
    "influencer-marketing-platforms",
    "creator-management",
    "social-media-analytics",
    "social-media-monitoring",
    "user-generated-content",
    "affiliate-marketing",
    "creator-economy-platforms",
]

# ── Capterra Categories ──────────────────────────────────────
CAPTERRA_CATEGORIES = [
    "influencer-marketing-software",
    "social-media-analytics-software",
    "social-media-monitoring-software",
]

# ── Tech stack signals (Google queries) ──────────────────────
# Companies that USE these tools = potential OnSocial customers
TECHSTACK_QUERIES = [
    # Direct competitors - companies using them
    '"powered by HypeAuditor"',
    '"HypeAuditor" "we use"',
    '"CreatorIQ" "our platform" -site:creatoriq.com',
    '"Traackr" "we switched" OR "we use" -site:traackr.com',
    '"Grin" influencer "our tool" -site:grin.co',
    '"Upfluence" "our agency" OR "we use" -site:upfluence.com',
    '"Modash" "our team" OR "we use" -site:modash.io',
    '"Klear" influencer "our data" -site:klear.com',
    # Integration pages - companies that integrated with competitors
    '"HypeAuditor API" integration',
    '"CreatorIQ API" integration',
    '"influencer analytics" "white label" OR "white-label"',
    # G2 reviewer companies
    'site:g2.com "HypeAuditor" review "I use"',
    'site:g2.com "CreatorIQ" review "I use"',
    'site:g2.com "influencer marketing" review agency',
    # Capterra reviewer companies
    'site:capterra.com "influencer marketing" review',
]

# ── Helpers ──────────────────────────────────────────────────

def extract_domain(url: str) -> str:
    """Extract clean domain from URL."""
    if not url:
        return ""
    if not url.startswith("http"):
        url = "https://" + url
    try:
        parsed = urlparse(url)
        domain = parsed.hostname or ""
        domain = domain.lower().strip()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


EXCLUDED_DOMAINS = {
    "g2.com", "capterra.com", "google.com", "linkedin.com", "facebook.com",
    "twitter.com", "youtube.com", "instagram.com", "tiktok.com", "reddit.com",
    "wikipedia.org", "crunchbase.com", "github.com", "medium.com",
    "hypeauditor.com", "creatoriq.com", "traackr.com", "grin.co",
    "upfluence.com", "modash.io", "klear.com", "onsocial.com",
    "trustradius.com", "getapp.com", "softwareadvice.com",
    "producthunt.com", "techcrunch.com", "forbes.com", "businessinsider.com",
    "hubspot.com", "salesforce.com", "mailchimp.com",
    "amazonaws.com", "cloudfront.net", "herokuapp.com",
}


def is_valid_company_domain(domain: str) -> bool:
    """Check if domain looks like a real company website."""
    if not domain or len(domain) < 4:
        return False
    if any(domain.endswith(f".{exc}") or domain == exc for exc in EXCLUDED_DOMAINS):
        return False
    # Skip common non-company TLDs
    if domain.endswith((".gov", ".edu", ".mil")):
        return False
    return True


# ── G2 Scraper ───────────────────────────────────────────────

def scrape_g2_category(category: str) -> Set[str]:
    """Scrape a G2 category page for company domains."""
    domains = set()
    # G2 category pages list products with links to company websites
    for page in range(1, 6):  # up to 5 pages per category
        url = f"https://www.g2.com/categories/{category}?page={page}"
        log.info(f"  G2: {category} page {page}")
        try:
            resp = requests.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "text/html",
            }, timeout=15)
            if resp.status_code != 200:
                log.warning(f"  G2 {category} page {page}: HTTP {resp.status_code}")
                break

            html = resp.text

            # Extract product page URLs from listing
            # G2 listing pages have links like /products/company-name/reviews
            product_links = re.findall(r'href="(/products/[^"]+)"', html)
            if not product_links:
                log.info(f"  No more products on page {page}")
                break

            # Also look for direct website links in the listing
            website_links = re.findall(r'href="(https?://(?:www\.)?[a-zA-Z0-9][a-zA-Z0-9.-]+\.[a-z]{2,})[^"]*"', html)
            for link in website_links:
                domain = extract_domain(link)
                if is_valid_company_domain(domain):
                    domains.add(domain)

            # Extract company names from product URLs for later domain resolution
            for link in set(product_links):
                # Visit product page to get website URL
                product_url = f"https://www.g2.com{link}"
                try:
                    presp = requests.get(product_url, headers={
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                        "Accept": "text/html",
                    }, timeout=15)
                    if presp.status_code == 200:
                        # Look for "Visit Website" or external links
                        ext_links = re.findall(r'href="(https?://(?:www\.)?[a-zA-Z0-9][a-zA-Z0-9.-]+\.[a-z]{2,})[^"]*"', presp.text)
                        for el in ext_links:
                            d = extract_domain(el)
                            if is_valid_company_domain(d):
                                domains.add(d)
                except Exception as e:
                    log.debug(f"  Error fetching {product_url}: {e}")
                time.sleep(0.5)  # be polite

            time.sleep(1)  # between pages

        except Exception as e:
            log.warning(f"  G2 error {category}: {e}")
            break

    return domains


def scrape_capterra_category(category: str) -> Set[str]:
    """Scrape Capterra category for company domains."""
    domains = set()
    for page in range(1, 4):  # up to 3 pages
        url = f"https://www.capterra.com/{category}/"
        if page > 1:
            url += f"?page={page}"
        log.info(f"  Capterra: {category} page {page}")
        try:
            resp = requests.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "text/html",
            }, timeout=15)
            if resp.status_code != 200:
                break

            # Extract website links
            website_links = re.findall(r'href="(https?://(?:www\.)?[a-zA-Z0-9][a-zA-Z0-9.-]+\.[a-z]{2,})[^"]*"', resp.text)
            for link in website_links:
                domain = extract_domain(link)
                if is_valid_company_domain(domain):
                    domains.add(domain)

            time.sleep(1)
        except Exception as e:
            log.warning(f"  Capterra error {category}: {e}")
            break

    return domains


# ── Google Search (via SerpAPI or direct) ────────────────────

def google_search_domains(query: str, num_results: int = 30) -> Set[str]:
    """Search Google and extract domains from results.

    Uses SerpAPI if SERPAPI_KEY is set, otherwise falls back to direct scraping.
    """
    domains = set()
    serpapi_key = os.getenv("SERPAPI_KEY", "")

    if serpapi_key:
        # Use SerpAPI
        try:
            resp = requests.get("https://serpapi.com/search", params={
                "q": query,
                "num": num_results,
                "api_key": serpapi_key,
                "engine": "google",
            }, timeout=20)
            if resp.status_code == 200:
                data = resp.json()
                for result in data.get("organic_results", []):
                    link = result.get("link", "")
                    domain = extract_domain(link)
                    if is_valid_company_domain(domain):
                        domains.add(domain)
        except Exception as e:
            log.warning(f"  SerpAPI error: {e}")
    else:
        # Fallback: use requests with Google (may get blocked)
        log.info(f"  No SERPAPI_KEY, using direct Google (may be rate-limited)")
        try:
            resp = requests.get("https://www.google.com/search", params={
                "q": query,
                "num": num_results,
            }, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            }, timeout=15)
            if resp.status_code == 200:
                links = re.findall(r'href="(https?://[^"]+)"', resp.text)
                for link in links:
                    domain = extract_domain(link)
                    if is_valid_company_domain(domain):
                        domains.add(domain)
        except Exception as e:
            log.warning(f"  Google error: {e}")

    return domains


# ── Blacklist check ──────────────────────────────────────────

def get_blacklisted_domains() -> Set[str]:
    """Fetch all blacklisted domains for project."""
    try:
        import psycopg2
        conn = psycopg2.connect(
            host="localhost", port=5432, dbname="leadgen",
            user="leadgen", password=os.getenv("POSTGRES_PASSWORD", "leadgen")
        )
        cur = conn.cursor()
        cur.execute("SELECT domain FROM project_blacklist WHERE project_id=%s", (PROJECT_ID,))
        bl = {row[0] for row in cur.fetchall()}
        cur.close()
        conn.close()
        return bl
    except Exception as e:
        log.warning(f"DB blacklist fetch failed: {e}, using API fallback")
        return set()


def get_existing_domains() -> Set[str]:
    """Fetch all already-discovered domains for project."""
    try:
        import psycopg2
        conn = psycopg2.connect(
            host="localhost", port=5432, dbname="leadgen",
            user="leadgen", password=os.getenv("POSTGRES_PASSWORD", "leadgen")
        )
        cur = conn.cursor()
        cur.execute("SELECT domain FROM discovered_companies WHERE project_id=%s", (PROJECT_ID,))
        existing = {row[0] for row in cur.fetchall()}
        cur.close()
        conn.close()
        return existing
    except Exception as e:
        log.warning(f"DB existing domains fetch failed: {e}")
        return set()


# ── Pipeline integration ─────────────────────────────────────

def create_gathering_run(domains: List[str], source_description: str) -> dict:
    """Create a gathering run via backend API with manual domain list."""
    url = f"{API_BASE}/pipeline/gathering/start"
    payload = {
        "project_id": PROJECT_ID,
        "source_type": "manual.companies.manual",
        "filters": {
            "domains": domains,
            "source_description": source_description,
        },
        "input_mode": "structured",
        "notes": f"Auto-scraped: {source_description}",
    }
    try:
        resp = requests.post(url, json=payload, headers=HEADERS, timeout=30)
        if resp.status_code in (200, 201):
            data = resp.json()
            run_id = data.get("id", "?")
            log.info(f"  Created gathering run #{run_id} with {len(domains)} domains")
            return data
        else:
            log.error(f"  API error {resp.status_code}: {resp.text[:200]}")
            return {}
    except Exception as e:
        log.error(f"  API error: {e}")
        return {}


# ── Main ─────────────────────────────────────────────────────

def main():
    log.info("=" * 60)
    log.info("G2 + Tech Stack Scraper for OnSocial")
    log.info("=" * 60)

    all_domains: Dict[str, str] = {}  # domain -> source

    # ── Step 1: G2 Categories ──────────────────────────
    log.info("\n[1/3] Scraping G2 categories...")
    for cat in G2_CATEGORIES:
        domains = scrape_g2_category(cat)
        for d in domains:
            if d not in all_domains:
                all_domains[d] = f"G2/{cat}"
        log.info(f"  {cat}: {len(domains)} domains")

    # ── Step 2: Capterra Categories ────────────────────
    log.info("\n[2/3] Scraping Capterra categories...")
    for cat in CAPTERRA_CATEGORIES:
        domains = scrape_capterra_category(cat)
        for d in domains:
            if d not in all_domains:
                all_domains[d] = f"Capterra/{cat}"
        log.info(f"  {cat}: {len(domains)} domains")

    # ── Step 3: Tech Stack Google Search ───────────────
    log.info("\n[3/3] Google tech stack search...")
    for query in TECHSTACK_QUERIES:
        domains = google_search_domains(query)
        for d in domains:
            if d not in all_domains:
                all_domains[d] = f"Google/{query[:40]}"
        log.info(f"  '{query[:50]}...': {len(domains)} domains")
        time.sleep(2)  # rate limit

    log.info(f"\nTotal raw domains: {len(all_domains)}")

    # ── Step 4: Deduplicate ────────────────────────────
    log.info("\nDeduplicating against blacklist + existing...")
    blacklisted = get_blacklisted_domains()
    existing = get_existing_domains()
    excluded = blacklisted | existing

    new_domains = {d: src for d, src in all_domains.items() if d not in excluded}
    log.info(f"  Blacklisted: {len(all_domains) - len(new_domains)} removed")
    log.info(f"  New unique domains: {len(new_domains)}")

    if not new_domains:
        log.info("\nNo new domains found. Done.")
        return

    # ── Step 5: Create gathering runs (batch by 500) ──
    log.info(f"\nCreating gathering runs (batches of 500)...")
    domain_list = sorted(new_domains.keys())
    BATCH_SIZE = 500
    runs_created = []

    for i in range(0, len(domain_list), BATCH_SIZE):
        batch = domain_list[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (len(domain_list) + BATCH_SIZE - 1) // BATCH_SIZE

        # Group sources for this batch
        sources = set()
        for d in batch:
            sources.add(new_domains[d].split("/")[0])
        source_desc = f"G2+TechStack batch {batch_num}/{total_batches} ({', '.join(sorted(sources))})"

        run = create_gathering_run(batch, source_desc)
        if run:
            runs_created.append(run.get("id"))
        time.sleep(1)

    # ── Summary ────────────────────────────────────────
    log.info("\n" + "=" * 60)
    log.info("SUMMARY")
    log.info("=" * 60)
    log.info(f"  Raw domains scraped: {len(all_domains)}")
    log.info(f"  After dedup: {len(new_domains)}")
    log.info(f"  Gathering runs created: {len(runs_created)}")
    if runs_created:
        log.info(f"  Run IDs: {runs_created}")
    log.info(f"\nSource breakdown:")
    source_counts: Dict[str, int] = {}
    for src in new_domains.values():
        key = src.split("/")[0]
        source_counts[key] = source_counts.get(key, 0) + 1
    for src, count in sorted(source_counts.items(), key=lambda x: -x[1]):
        log.info(f"    {src}: {count}")

    log.info("\nNext: run pipeline phases (blacklist, scrape, classify) on created runs")
    log.info("Done!")


if __name__ == "__main__":
    main()
