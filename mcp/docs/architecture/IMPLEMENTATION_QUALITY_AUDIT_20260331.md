# Implementation Quality Audit — Brutal Honest Assessment

**Date**: 2026-03-31
**Auditor**: God-level analysis of actual code vs claims

---

## VERDICT: Pipeline works but has 7 critical quality issues

The pipeline CAN gather companies, classify them, and extract people. But the implementation cuts serious corners on performance, cost tracking, and error handling.

---

## Issue 1: COST TRACKING IS A FACADE

**Severity: CRITICAL**

The Account page shows Apollo credits, OpenAI tokens, Apify bytes — but **nobody writes actual API costs to the database**.

**What the Account API reads** (`account.py`):
```python
# Reads MCPUsageLog where action="api_cost" and service="openai"
# Reads MCPUsageLog where action="api_cost" and service="apify"
```

**What actually writes `action="api_cost"`**: NOTHING in the pipeline.

- `tam_gather` → writes `MCPUsageLog(action="tool_call")` — no cost data
- `tam_analyze` → calls OpenAI but writes NO usage log for tokens
- `scrape_companies` → calls Apify proxy but writes NO usage log for bytes
- `run_exploration` → spends 5 Apollo credits but writes NO usage log

**Result**: Account page shows `$0.00` for OpenAI and Apify always. Apollo gathering credits are tracked on `GatheringRun.credits_used` but exploration/enrichment credits are lost.

**Fix needed**: Every API call (OpenAI, Apollo, Apify) must write `MCPUsageLog(action="api_cost", extra_data={service, model, tokens, cost_usd, ...})`.

---

## Issue 2: SCRAPING NOT MAXIMALLY PARALLEL

**Severity: MEDIUM**

The MCP scraper uses `max_concurrent=10` semaphore. The main app uses `max_concurrent=50`.

```python
# MCP scraper_service.py
await scrape_batch(domains, max_concurrent=10)  # 10 at a time

# Main app scraper_service.py  
await scrape_domains_fast(domains, max_concurrent=50)  # 50 at a time
```

For 100 companies (4 pages × 25), scraping takes 5x longer than it should.

**Also**: No retry on 429 errors. Main app has exponential backoff. MCP scraper fails immediately.

**Fix needed**: Use `max_concurrent=50` + add retry with backoff on 429.

---

## Issue 3: per_page=25 WHEN APOLLO SUPPORTS 100

**Severity: HIGH**

```python
COMPANIES_PER_PAGE = 25  # pipeline_orchestrator.py
```

Apollo API supports `per_page=100`. At 25/page with 4 pages, we get 100 companies per batch. At 100/page with 4 pages, we'd get 400 companies per batch — 4x more companies for the SAME 4 credits.

**Another agent already fixed this to 100** (per the screenshot). But the point stands: this was shipping as 25 and nobody caught it.

---

## Issue 4: EXPLORATION CREDITS VANISH

**Severity: HIGH**

```python
# pipeline_orchestrator.py line 158
result["credits_used"] += exploration.get("credits_used", 0)
```

Exploration credits are added to the in-memory `result` dict. But they're NEVER written back to `run.credits_used`. When the pipeline finishes, only gathering credits are persisted.

5 Apollo credits per exploration × N pipelines = invisible spend.

**Fix needed**: After exploration, `run.credits_used += exploration.get("credits_used", 0)` and flush.

---

## Issue 5: PEOPLE EXTRACTION IS FIRE-AND-FORGET IN ITERATION 1

**Severity: MEDIUM**

```python
# Iteration 1
asyncio.create_task(self._extract_people_for_new_targets(...))  # Fire and forget

# Iteration 2+
await self._extract_people_for_new_targets(...)  # Properly awaited
```

Iteration 1's people extraction runs as an orphaned background task. If it fails, nobody knows. The count won't include iteration 1's people until iteration 2 checks.

**Fix needed**: Store the task handle, await it before starting iteration 2.

---

## Issue 6: MCPUsageLog COLUMN NAME MISMATCH

**Severity: LOW (works but confusing)**

```python
# Model
extra_data = Column("metadata", JSONB, nullable=True)
```

Python attribute is `extra_data`, DB column is `metadata`. Direct SQL queries using `extra_data` fail (as seen in the screenshot). ORM works fine, but any debugging via psql is broken.

---

## Issue 7: NO APIFY COST LOGGING DURING PIPELINE

**Severity: HIGH**

When the orchestrator scrapes websites, it uses Apify residential proxy (httpx + proxy URL). But:
- No bytes counter
- No domains counter
- No cost logging
- Account page shows 0 GB, 0 websites, $0.00

The main app tracks Apify usage. MCP doesn't.

**Fix needed**: After `scrape_batch`, log total bytes + domain count to MCPUsageLog.

---

## Summary: What Works vs What Doesn't

| Component | Status | Detail |
|-----------|--------|--------|
| Apollo company search | WORKS | Fetches pages, returns companies |
| Apollo credit counting (gather) | WORKS | `run.credits_used` persisted |
| Apollo credit counting (explore) | BROKEN | Credits in memory only, never persisted |
| Apollo credit counting (people) | BROKEN | Not tracked at all |
| Website scraping | WORKS (slow) | max_concurrent=10, should be 50 |
| Scrape retry on 429 | BROKEN | No retry, fails immediately |
| GPT classification | WORKS | Calls OpenAI, classifies companies |
| GPT cost logging | BROKEN | Tokens/cost never written to DB |
| Apify cost logging | BROKEN | Bytes/domains never written to DB |
| People extraction | WORKS (fragile) | Parallel within batch, fire-and-forget in iter 1 |
| Account page costs | FACADE | Reads from table nobody writes to |
| Pipeline progress (KPIs) | WORKS | New fields, properly persisted |
| Pause/resume | WORKS (untested) | Code exists, never battle-tested |
| Auto-campaign at KPI | UNTESTED | Code exists, calls generate_sequence |
| Telegram notification | UNTESTED | Code exists, correct bot token set |

---

## Priority Fixes

1. **P0**: Instrument ALL API calls with MCPUsageLog (OpenAI tokens, Apollo credits, Apify bytes)
2. **P0**: Persist exploration credits to `run.credits_used`
3. **P1**: Scraper max_concurrent → 50, add 429 retry
4. **P1**: per_page → 100 (already done by another agent)
5. **P2**: Await iteration 1 people task before iteration 2
6. **P2**: Battle-test pause/resume/auto-campaign with real Apollo data
