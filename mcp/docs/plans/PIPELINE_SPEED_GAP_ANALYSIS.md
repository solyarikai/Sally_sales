# Pipeline Speed Gap Analysis — Your Vision vs Current Implementation

## Your Vision (correct understanding)

```
Apollo page → each company IMMEDIATELY flows to:
  → Apify scrape (100 concurrent)
    → each scraped site IMMEDIATELY flows to:
      → OpenAI classify (100 concurrent)
        → each target IMMEDIATELY flows to:
          → People gather (20 concurrent)

Apollo fetches 10 pages in parallel batches.
No waiting. Pure streaming. KPI checked after every person saved.
```

## Current Implementation — TWO MODES

### Phase 1 (existing companies from tam_gather): **BATCH — NOT STREAMING** ❌

```python
# Lines 108-113 — SEQUENTIAL PHASES, each waits for ALL to finish
await self._batch_scrape(existing)          # Scrape ALL 600 companies → WAIT
scraped = [dc for dc in existing if dc.scraped_text]
await self._batch_classify(scraped)         # Classify ALL 300 scraped → WAIT
targets = [dc for dc in existing if dc.is_target]
await self._batch_people(targets)           # People ALL 100 targets → WAIT
```

**What happens:** Company #1 gets scraped in 1s. But it WAITS for companies #2-600 to all finish scraping before classification starts. If company #500 has a 15s timeout, ALL scraped companies wait 15s before ANY gets classified.

**Within each phase** concurrency IS correct (100 parallel scrapes, 100 parallel classifies, 20 parallel people). But **between phases** it's serial.

### Phase 2 (new Apollo pages): **TRUE STREAMING** ✅

```
scrape_queue → scraper_worker (100 concurrent) → classify_queue → classifier_worker (100 concurrent) → people_queue → people_worker (20 concurrent)
```

Company flows through immediately. When scraper finishes company #1, it goes to classifier right away. No waiting. This IS your vision.

**BUT Phase 2 only runs when Phase 1 doesn't hit KPI.** For most runs, Phase 1 processes all existing companies and either hits KPI or not — Phase 2 only adds MORE pages.

---

## Gap #1: Phase 1 should be streaming, not batch ❌ CRITICAL

**Impact:** For 600 existing companies, batch mode wastes ~30-40% of time.

Example timing:
- Batch: scrape(20s) → classify(15s) → people(10s) = 45s serial
- Streaming: all three phases overlap = ~25s (scrape + classify pipeline)

**Fix:** Use the same queue workers for Phase 1. Feed existing companies into `scrape_queue`, let them flow through `classify_queue` → `people_queue`. Wait for pipeline to drain (all queues empty + workers idle). Then check KPI.

---

## Gap #2: Apollo pages fetched ONE AT A TIME ❌

**Current (line 358):**
```python
results = await adapter.gather(batch_filters)  # 1 page at a time
```

Phase 2 fetches page 1, waits, fetches page 2, waits... 

**Your vision:** 10 pages in parallel per batch.

**Impact:** Apollo API responds in ~0.5-1s per page. 10 sequential = 5-10s. 10 parallel = 1s.

**Fix:** Fetch pages in parallel batches of 10 using `asyncio.gather()`, then feed all results to scrape_queue.

---

## Gap #3: Cost estimate doesn't include Phase 2 potential ⚠️

**Current cost estimate shown to user (dispatcher.py line 90-96):**
```
Company search: ~34 pages = 34 credits ($0.34)
Classification: ~$0.07 (GPT-4o-mini)
People search: FREE
Email enrichment: ~100 credits ($1.00)
Total: ~$1.41
```

This is for the INITIAL 10 pages. If Phase 2 kicks in with keyword regeneration (up to 5 cycles × 20 pages = 100 more pages), the real cost could be:
- Best case (KPI met from initial): 10 pages + 100 people = 110 credits ($1.10)
- Worst case (5 regen cycles): 10 + 100 extra pages + people = 210+ credits ($2.10)

**Fix:** Show two estimates:
- "Expected: ~$1.41 (if targets found in initial batch)"  
- "Max if exhausted: ~$3.00 (includes auto-recovery with new keywords)"

---

## Gap #4: No parallel page fetching in Phase 2 ❌

**Current:** `_feed_apollo_pages` fetches one page, ingests, fetches next.

**Your vision:** Parallel batches of 10 pages, each batch's results immediately flowing to workers.

---

## What IS Correctly Implemented ✅

| Feature | Status | Where |
|---------|--------|-------|
| 100 concurrent scraping | ✅ | `_batch_scrape` + `_scraper_worker` both use `Semaphore(100)` |
| 100 concurrent classification | ✅ | `_batch_classify` + `_classifier_worker` both use `Semaphore(100)` |
| 20 concurrent people search | ✅ | `_batch_people` + `_people_worker` both use `Semaphore(20)` |
| KPI checked per person | ✅ | `_kpi_met` flag checked in people extraction loops |
| Queue-based streaming (Phase 2) | ✅ | `scrape_queue → classify_queue → people_queue` with workers |
| Backpressure via maxsize | ✅ | Queues have `maxsize=200` / `maxsize=100` |
| Poison pill propagation | ✅ | `None` sentinel flows through queue chain |
| Domain dedup (in-memory + DB) | ✅ | `_domains_seen` set + pre-loaded project domains |
| Batch DB flush per page | ✅ | `_ingest_page_results` flushes once per page |
| Keyword regeneration | ✅ | `_regenerate_keywords` with GPT, excludes tried |
| Strategy switching | ✅ | Primary → backlog → regen cycles |
| Auto-push insufficient to SL | ✅ | `run_pipeline_background` pushes when `total_people > 0` |
| Issues in result | ✅ | `_build_result` returns `issues` list |

---

## Fixes Needed (Priority Order)

### Fix 1: Unify Phase 1 + Phase 2 into single streaming mode

**Remove** `_batch_scrape`, `_batch_classify`, `_batch_people`.

**Instead:** Always start workers, feed existing companies to `scrape_queue`, then feed Apollo pages. One code path.

```python
async def run_until_kpi(self, filters):
    workers = [scraper_worker, classifier_worker, people_worker]
    
    # Feed existing companies to scrape queue
    for dc in existing:
        await self.scrape_queue.put(dc)
    
    # If KPI not met yet, feed Apollo pages too
    # (workers are already processing existing companies in parallel)
    if not self._kpi_met:
        await self._feed_apollo_pages(filters)
    
    # Poison pill + wait
    await self.scrape_queue.put(None)
    await asyncio.gather(*workers)
```

**Problem solved:** No more serial phases. Company #1 flows through scrape→classify→people while company #600 is still being scraped.

**New problem:** How to know when existing companies are "done" before deciding to fetch more Apollo pages?

**Solution:** Don't decide upfront. Start workers, feed existing, start feeding Apollo in parallel. KPI flag stops everything as soon as target met. If existing companies are enough, Apollo pages will be mostly skipped because `_kpi_met` becomes True.

But this means we might fetch some Apollo pages unnecessarily. Acceptable tradeoff — a few extra credits vs significantly faster pipeline.

**Better solution:** Use an `asyncio.Event` to signal when scrape→classify→people pipeline has drained:

```python
# Feed existing companies
for dc in existing:
    await self.scrape_queue.put(dc)

# Wait for pipeline to drain (all existing processed)
await self._wait_pipeline_drain()

# Now check KPI — only fetch Apollo if needed
if not self._kpi_met:
    await self._feed_apollo_pages(filters)
```

To implement drain detection: track in-flight count per phase. When all three phases have 0 in-flight AND queues are empty → drained.

### Fix 2: Parallel Apollo page fetching

```python
# Fetch 10 pages in parallel
async def _fetch_page_batch(self, adapter, filters, start_page, count, per_page):
    tasks = []
    for p in range(start_page, start_page + count):
        f = dict(filters, page=p, max_pages=1, per_page=per_page)
        tasks.append(adapter.gather(f))
    return await asyncio.gather(*tasks, return_exceptions=True)
```

### Fix 3: Update cost estimate

In `cost_estimator.py`, add:
```python
"estimated_if_exhausted": {
    "max_extra_pages": 100,  # 5 regen × 20 pages
    "max_total_credits": search_credits + 100 + people_credits,
    "max_total_usd": ...,
    "note": "Only if initial filters are exhausted. Pipeline auto-recovers with new keywords."
}
```

---

## Summary: Your Vision vs Reality

| Aspect | Your Vision | Current | Gap |
|--------|------------|---------|-----|
| Scrape→Classify→People streaming | Each company flows immediately | Phase 1: batch (serial phases). Phase 2: streaming | **Phase 1 is serial** |
| Apollo page parallelism | 10 pages parallel per batch | 1 page at a time | **Sequential pages** |
| Concurrency per phase | 100/100/20 | 100/100/20 | ✅ Match |
| KPI stop immediately | After each person | After each person | ✅ Match |
| Continue until KPI met | Auto-loop with more pages | Auto-loop + keyword regen | ✅ Better than vision |
| Cost estimate shown | Show expected credits | Shows initial estimate only | **Missing worst-case** |
| People gathered per target | Immediately when classified | Phase 1: after ALL classified. Phase 2: immediately | **Phase 1 is serial** |
