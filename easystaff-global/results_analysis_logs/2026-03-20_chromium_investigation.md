# Chromium Process Investigation — 2026-03-20 15:41 UTC+2

## Context

Server load average 8.44 on 4 cores. Backend container at 139% CPU. User noticed Chromium renderer processes eating CPU and questioned whether website scraping should be running via Puppeteer (should be Apify or plain HTTP — JS-heavy sites won't render properly with basic HTTP anyway).

## What's Running (ps aux snapshot)

| PID | CPU% | Process | Purpose |
|-----|------|---------|---------|
| 3918204 | 95% | Chromium renderer (`/usr/lib/chromium`) | **Website scraping** — inside backend container, spawned by `batch_analyze_easystaff.py` |
| 3918287 | 69% | Chrome renderer (`/opt/google/chrome`) | **Apollo People scraper** — batch 14, scraping wholesale/fashion brand contacts |
| 3914774 | 19% | Chrome renderer | **Another scrape tab** — secondary Puppeteer page |
| 3916969 | 8% | `python batch_analyze_easystaff.py` | **V4 analysis** — classifying companies via OpenAI |
| 3876072 | 7% | `node ciff_scrape_emails.js` | **CIFF email scraping** — separate standalone script (not committed to git, only on Hetzner) |
| 3918109 | 3% | `node apollo_scraper.js` | **Apollo scraper driver** — feeding URLs to Chromium |
| 3899344 | 5% | `uvicorn app.main:app` | **FastAPI backend** |

## Two DIFFERENT Chromium Binaries

1. **`/usr/lib/chromium/chromium`** — System Chromium inside the Docker container (backend). Used by `batch_analyze_easystaff.py`. This is the one at 95% CPU.
2. **`/opt/google/chrome/chrome`** — Google Chrome, likely installed separately. Used by Apollo/Clay Puppeteer scripts. This one has multiple renderer processes at 69%, 19%, etc.

## Finding: Phase 4 (SCRAPE) in Gathering Pipeline Does NOT Use Chromium

`gathering_service.py:scrape_companies()` calls `scraper_service.scrape_website()` which is pure **httpx + BeautifulSoup** — no Chromium, no Puppeteer. This is correct and efficient for B2B websites where ~80% are static HTML.

### Scrape method priority (in `company_search_service.py`):
1. **Project config** — `project.auto_enrich_config.scrape_method` can override
2. **Crona API** — headless browser as a service ($0.01/domain) for JS-heavy sites
3. **Apify residential proxy** — IP rotation via `proxy.apify.com` (needs `APIFY_PROXY_PASSWORD`)
4. **httpx** (default) — plain HTTP with rotating user agents

## So Why is Chromium Running at 95%?

The 95% CPU Chromium renderer (PID 3918204) is spawned from **within the backend Docker container** (`/usr/lib/chromium`). It's being used by `batch_analyze_easystaff.py` — this is the V4 batch analysis script.

Looking at the process tree:
- `batch_analyze_easystaff.py` (PID 3916969, 8% CPU) launched a Chromium process
- The Chromium renderer (PID 3918204, 95% CPU) is doing the actual page rendering

This means `batch_analyze_easystaff.py` is scraping websites with Puppeteer **as part of its analysis flow**, likely in `company_search_service.py` which has both httpx and Chromium paths.

## The Concern: JS-Heavy Websites

User correctly notes: "some websites JS-based won't be parsed" — httpx returns empty text for JS-rendered sites. The system handles this:

- `scraper_service.py` detects empty content: returns `"No text content (site may use JavaScript rendering)"`
- `company_search_service.py` has Crona fallback for JS sites (but costs $0.01/domain)
- Apify proxy only helps with IP blocks, not JS rendering
- **No automatic Puppeteer fallback exists in the gathering pipeline's Phase 4**

## Separate Process: `ciff_scrape_emails.js`

- Running since 15:06 (50 min), 7% CPU
- **NOT in git** — only exists on Hetzner at `scripts/ciff_scrape_emails.js`
- `ciff_scrape_brands.js` IS in git — scrapes brand list from ciff.dk/our-brands using Puppeteer
- The email variant is likely a one-off derivative that scrapes contact emails from brand websites

## Separate Process: Apollo Scraper

- `apollo_scraper.js` (PID 3918109) + multiple Chrome renderers
- Scraping Apollo People tab with Puppeteer (free, avoids API credits)
- Current batch: 30 fashion/wholesale brand domains (new-feet.com, noellafashion.dk, etc.)
- Multiple title filters: Head of Wholesale, Sales Director, CEO, Founder, etc.
- This is expected behavior — Apollo UI scraping requires Chromium

## Summary

| Process | Should it use Chromium? | Status |
|---------|------------------------|--------|
| Apollo People scraping | YES (UI scraping) | Correct |
| Clay TAM export | YES (UI scraping) | Not running now |
| Gathering Phase 4 (SCRAPE) | NO (uses httpx) | Correct |
| `batch_analyze_easystaff.py` | QUESTIONABLE — spawning Chromium for website scraping within analysis | Needs review |
| `ciff_scrape_emails.js` | YES (one-off brand scraping) | Fine but not in git |

## Action Items (Not Implemented — User Said Don't Change)

1. **Investigate why `batch_analyze_easystaff.py` spawns Chromium** — if it's scraping websites as part of analysis, it should reuse existing CompanyScrape data from Phase 4 instead
2. **JS-heavy site gap**: ~20% of B2B sites return empty content from httpx. Crona exists as fallback but isn't wired into the gathering pipeline's Phase 4. Could add automatic Crona fallback for empty scrapes.
3. **`ciff_scrape_emails.js`**: uncommitted script on Hetzner. Consider committing or removing if one-off task is done.
