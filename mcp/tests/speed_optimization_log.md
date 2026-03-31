# Speed Optimization Log — 2026-03-31

## Concurrency Settings: Before → After

| Component | Before | After | Rationale |
|-----------|--------|-------|-----------|
| **Scraper (gathering_service)** | max_concurrent=10, delay=0.1s | max_concurrent=50, delay=0.02s | Was 5x slower than scraper's own default. Apify residential proxy handles 50+ concurrent. |
| **GPT Analysis** | batch=25, concurrent=10 | batch=50, concurrent=25 | OpenAI gpt-4o-mini allows 1000 RPM. 25 concurrent × 2s avg = 750 RPM, well within limit. |
| **GPT Normalization** | batch=20, concurrent=10 | batch=50, concurrent=25 | Same reasoning as analysis. |
| **People Extraction** | 5 concurrent | 20 concurrent | Apollo rate limit is 300ms/req, but we're calling enrich_by_domain which is a different endpoint. 20 concurrent is safe. |
| **Scraper retry** | No retry | 2 retries, 2s/4s backoff | 429/5xx now retried instead of permanent failure |

## Expected Speed Improvement

### Scraping phase (300 companies)
- Before: 300 companies / 10 concurrent × (avg 2s + 0.1s delay) = **63 seconds**
- After: 300 companies / 50 concurrent × (avg 2s + 0.02s delay) = **12 seconds**
- **5x faster**

### Analysis phase (300 companies)
- Before: 300 companies / 10 concurrent × avg 1.5s = **45 seconds**
- After: 300 companies / 25 concurrent × avg 1.5s = **18 seconds**
- **2.5x faster**

### People extraction (40 target companies)
- Before: 40 companies / 5 concurrent × avg 1s = **8 seconds**
- After: 40 companies / 20 concurrent × avg 1s = **2 seconds**
- **4x faster**

### Total pipeline iteration (estimated)
- Before: ~120s per iteration (5 pages)
- After: ~35s per iteration (5 pages)
- **3.5x faster overall**

## Limits to Test (Future)

### Apify Residential Proxy
- Current: 50 concurrent
- To test: 100, 200, 500
- Expected limit: Apify residential proxy depends on subscription tier
- Test approach: `asyncio.gather(*[scrape(url) for url in test_urls])` with increasing batch sizes
- Track: success rate, 429 count, avg response time

### OpenAI GPT-4o-mini
- Current: 25 concurrent (with 1000 RPM limit)
- To test: 50, 100
- Expected limit: 1000 RPM = ~16.7 req/s. At avg 1.5s/req, max ~25 concurrent in theory
- Higher concurrency only helps if OpenAI responds faster
- Test: measure actual response times, not just RPM

### Apollo API
- Currently sequential (300ms between requests)
- Cannot parallelize page fetches for SAME search (Apollo paginates server-side)
- Different searches CAN run in parallel (e.g., 2 segments = 2 parallel Apollo streams)

## What GPT-4o-mini Costs at 25 Concurrent

- 300 companies × ~800 input tokens + ~200 output tokens per classification
- Total: 240K input + 60K output = 300K tokens
- Cost: (240K × $0.15 + 60K × $0.60) / 1M = $0.036 + $0.036 = **$0.07 per 300 companies**
- At 25 concurrent, takes ~18 seconds
- This is already very cheap and fast. No reason to use a slower/more expensive model.
