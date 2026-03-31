# Implementation Quality Audit v2 — After Fixes

**Date**: 2026-03-31 (updated after other agent's fixes)

---

## What Was Fixed by Other Agent

| Issue | Status | Commit |
|-------|--------|--------|
| per_page=25 → 100 | FIXED | `594a7883` — Apollo only works with per_page=100 |
| Pages per batch 4 → 5 | FIXED | `594a7883` — 5 pages × ~60 unique = ~300/batch |
| People extraction parallel | FIXED | `f04ab0de` — asyncio.gather with 5 concurrent |
| Cost tracker module | BUILT | `974fd967` — CostTracker class, logs OpenAI/Apollo/Apify |
| Services instrumented | DONE | All services call `get_tracker().log_*()` |
| Flush costs per iteration | DONE | `a6dca3a8` — `_flush_costs()` writes to mcp_usage_logs |
| People via Clay enrichment | REWRITTEN | `765b6c13` — Clay Add→Find People instead of Apollo |

---

## Remaining Issues

### Issue 1: COST ACTION NAME MISMATCH — Account Page Still Shows $0

**Severity: CRITICAL (cost tracking is wired but doesn't display)**

The orchestrator flushes costs with:
```python
action=f"cost_{entry['service']}"  # → "cost_openai", "cost_apollo", "cost_apify"
```

The Account API reads:
```python
MCPUsageLog.action == "api_cost"   # → NEVER MATCHES "cost_openai"
```

**Result**: Cost tracker logs are written to DB correctly, but the Account page query can't find them because it looks for `action="api_cost"` while the data has `action="cost_openai"`.

**Fix**: Either change the flusher to write `action="api_cost"` with `service` inside the JSONB, OR change the Account API to read `action.startswith("cost_")`.

### Issue 2: Exploration Credits Still Not Persisted to run.credits_used

**Severity: MEDIUM**

Line 161: `result["credits_used"] += exploration.get("credits_used", 0)` — adds to in-memory dict only.

`_flush_costs()` handles the cost_tracker entries BUT `run.credits_used` is only updated in `_gather_batch` (gathering credits). Exploration's 5 credits aren't in `run.credits_used`.

The cost_tracker DOES capture them if exploration calls `get_tracker().log_apollo()`. But `run.credits_used` (the field the frontend KPI display reads) is incomplete.

### Issue 3: Iteration 1 People Task Still Fire-and-Forget

**Severity: LOW (people extraction was rewritten to use Clay)**

Line 140: `asyncio.create_task(...)` — not awaited. But since people extraction was rewritten to use Clay (`765b6c13`), this may not even be the active code path anymore.

### Issue 4: Scraper Still max_concurrent=10, No 429 Retry

**Severity: MEDIUM**

`scraper_service.py` semaphore is 10, not 50. No retry on HTTP 429. These were in the original audit and not yet addressed.

### Issue 5: _read_kpis() Uses Old Column Names

**Severity: LOW (works via SQLAlchemy alias)**

The orchestrator docstring still says `target_count`, `contacts_per_company`, `min_targets` (line 10-12) but the actual model was renamed to `target_people`, `max_people_per_company`, `target_companies`. `_read_kpis()` correctly reads the renamed fields.

---

## Updated Severity Table

| Issue | Before | After Other Agent | Now |
|-------|--------|-------------------|-----|
| Cost tracking facade | CRITICAL | Instrumented + flushed | **Action name mismatch — still shows $0** |
| Scraper max_concurrent | MEDIUM | Not fixed | **Still 10, not 50** |
| per_page=25 | HIGH | **FIXED → 100** | Done |
| Exploration credits lost | HIGH | Partially (cost_tracker captures) | **run.credits_used still incomplete** |
| People fire-and-forget | MEDIUM | **Rewritten to Clay** | Low risk |
| Column name mismatch | LOW | Not relevant | Still exists |
| Apify logging | HIGH | **FIXED via cost_tracker** | Action name mismatch |
| 429 retry | MEDIUM | Not fixed | **Still no retry** |

---

## Priority Fixes Remaining

1. **P0**: Fix action name mismatch — Account API must read `action LIKE 'cost_%'` instead of `action = 'api_cost'`
2. **P1**: Add exploration credits to `run.credits_used`
3. **P1**: Scraper max_concurrent → 50 + 429 retry with backoff
4. **P2**: Update orchestrator docstring to match renamed KPI fields
