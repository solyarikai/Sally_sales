# Website Scraping Architecture

## How it works

`scraper_service.scrape_batch()` — concurrent HTTP scraping via httpx + Apify residential proxy.

### Key parameters
- `max_concurrent=50` — 50 parallel HTTP connections (was 10, now 50)
- `timeout=15` — 15 seconds per request
- `delay_between_requests=0.05` — 50ms between launches (not sequential)
- `on_result` callback — stream results to DB as they arrive

### Streaming commits (crash-safe)

**Before (broken):**
```
scrape_batch(7000 urls) → holds ALL in memory → returns list → caller commits → CRASH = lose everything
```

**After (fixed):**
```
scrape_batch(7000 urls, on_result=save_to_db) → each result committed in batches of 50 → CRASH at 5000 = 5000 saved
```

The `on_result` async callback is called per successful scrape. The caller buffers 50 results then commits to DB. If process crashes, only the last 50 are lost.

### Proxy

Apify residential proxy auto-configured if `APIFY_PROXY_PASSWORD` env var is set. Rotates IP per session. Bypasses rate limiting and geo-blocks.

```python
def _get_proxy_url(self) -> Optional[str]:
    # Returns http://groups-RESIDENTIAL,session-XXX:PASSWORD@proxy.apify.com:8000
```

### What scraping does NOT do

- **No Puppeteer / Chromium** — plain HTTP only, no CPU load
- **No JS rendering** — gets raw HTML, extracts text via BeautifulSoup
- **No credits** — completely free (httpx + proxy subscription)

### Performance

| Setting | Speed | 7,000 companies |
|---------|-------|-----------------|
| 10 concurrent (old) | ~30/min | ~4 hours |
| 50 concurrent (new) | ~150/min | ~45 min |
| 50 concurrent + streaming commits | ~150/min | ~45 min, crash-safe |
