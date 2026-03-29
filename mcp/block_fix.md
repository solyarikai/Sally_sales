# Block Fix: tam_scrape blocks async event loop (Issue #29)

## The Problem

`gathering_service.scrape()` loops **sequentially** over companies:

```python
for dc in companies:
    scrape_result = await scraper_service.scrape_website(url)  # 2-30s each
    if not scrape_result["success"]:
        await asyncio.sleep(2)  # retry delay
        scrape_result = await scraper_service.scrape_website(url)  # another 2-30s
```

For 8 companies this takes 30-120 seconds. For 110 companies: 5-15 minutes.

**During this entire time, the FastAPI async event loop is blocked.** All other API requests (health checks, create_project, tool-call) queue up and timeout. Tests 10-15 crash at 0%.

The irony: `scraper_service` already HAS concurrent scraping (`scrape_batch`, `scrape_domains_fast` with `asyncio.gather` + semaphore). But `gathering_service.scrape()` doesn't use it.

---

## The Fix (3 lines changed, 0 new files)

### `mcp/backend/app/services/gathering_service.py` — replace sequential loop with concurrent batch

**Before (broken):**
```python
async def scrape(self, session, run, scraper_service=None):
    ...
    if scraper_service:
        for dc in companies:
            url = dc.website_url or f"https://{dc.domain}"
            scrape_result = await scraper_service.scrape_website(url)
            if not scrape_result["success"]:
                await asyncio.sleep(2)
                scrape_result = await scraper_service.scrape_website(url)
            # save to DB one by one...
```

**After (god-level):**
```python
async def scrape(self, session, run, scraper_service=None):
    ...
    if scraper_service:
        import asyncio as _asyncio

        # Build batch items with company reference
        batch_items = []
        company_map = {}
        for dc in companies:
            url = dc.website_url or f"https://{dc.domain}"
            batch_items.append({"url": url, "row_id": dc.id})
            company_map[dc.id] = dc

        # Concurrent scraping — uses existing scrape_batch with semaphore
        # max_concurrent=10 to avoid overwhelming the event loop
        async def on_result(result):
            nonlocal scraped, errors
            dc_id = result.get("row_id")
            scrape_record = CompanyScrape(
                discovered_company_id=dc_id,
                url=result.get("url", ""),
                scrape_status="success" if result.get("success") else "error",
                clean_text=result.get("text"),
                error_message=result.get("error"),
                http_status_code=result.get("status_code"),
                text_size_bytes=len(result.get("text", "")) if result.get("text") else 0,
            )
            session.add(scrape_record)
            if result.get("success"):
                scraped += 1
            else:
                errors += 1

        await scraper_service.scrape_batch(
            batch_items,
            timeout=10,
            max_concurrent=10,  # 10 concurrent, not 50 — be gentle on the event loop
            delay=0.1,
            on_result=on_result,
        )
```

### Why this works

1. **`scrape_batch` already exists** — uses `asyncio.gather` with semaphore. Proven code.
2. **`on_result` callback** saves to DB as each scrape completes — no memory accumulation.
3. **`max_concurrent=10`** — enough parallelism for speed, not enough to starve the event loop.
4. **8 companies at 10 concurrent = 1 batch** — finishes in ~3-5 seconds instead of 30-120.
5. **110 companies at 10 concurrent = 11 batches** — finishes in ~30-60 seconds instead of 5-15 minutes.

### Why not background task (Celery/create_task)?

- Celery adds infrastructure (Redis broker, worker process). Overkill for this.
- `asyncio.create_task` would work but the scrape result needs to be persisted to DB before the `tam_analyze` step runs. A fire-and-forget task would require a polling mechanism.
- The concurrent batch approach is **synchronous from the caller's perspective** (returns when all done) but **async internally** (doesn't block the event loop). This is the correct pattern.

### Test impact

- 8 companies: ~3s instead of ~60s (20x faster)
- Event loop stays responsive — other API calls return instantly
- Tests 10-15 no longer timeout

---

## Implementation checklist

1. Replace the `for dc in companies` loop in `gathering_service.scrape()` with `scrape_batch()` call
2. Add `on_result` callback for DB persistence
3. Set `max_concurrent=10` (not 50 — MCP runs on a single Hetzner box)
4. Test: run full 12-test suite, verify all pass
5. Test: while scrape is running, verify `/api/health` responds < 100ms
