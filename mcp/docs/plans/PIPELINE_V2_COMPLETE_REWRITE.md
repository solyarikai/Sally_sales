# Pipeline V2 — Complete Rewrite Plan

## Root Cause Analysis

### Why Pipeline 442 Failed (and 439, 440 before it)
The streaming pipeline crashes with `asyncpg.InterfaceError: cannot perform operation: another operation is in progress` because **multiple async workers share one SQLAlchemy session and flush concurrently**. The scraper, classifier, and people workers all call `session.flush()` in parallel on the same connection — asyncpg doesn't support concurrent operations on one connection.

### Why Probe Fetched 306 Companies (should be 1 page = 100)
tam_gather preview calls Apollo probe with `per_page=100` (good) but then the filter_mapper + probe happens BEFORE returning preview. However, `start_gathering` in the CONFIRM step fetches 10 pages (max_pages=10) creating ALL 306 companies. The probe's 100 companies from page 1 should be the ONLY companies at preview time.

### All MCP Tool Errors from Screenshots
1. `create_project(website: "...")` → Error: 'name' is a required property — schema has `required: ["name"]`
2. `confirm_offer(project_id: "424")` → Error: '424' is not of type 'integer' — Claude sends string
3. `list_email_accounts` → Error: result exceeds 247K chars — returns ALL 2411 accounts
4. `align_email_accounts(project_id: "424", name_pattern: "elnar")` → Error: 'run_id' is a required property
5. Two pipelines created (#441 pending, #442 gather) — preview creates one, confirm creates another

---

## Fixes Required

### FIX 1: Session-Safe Streaming Pipeline (CRITICAL)
**Problem**: Workers crash on concurrent session.flush()
**Solution**: Each worker gets its OWN session. Only persist results to main session at the END.

```python
# Instead of sharing self.session across workers:
# Each worker creates its own session for reads/writes
# Results collected in memory (lists), flushed to main session once at end
```

Alternative (simpler): Use asyncio.Lock for all session operations:
```python
self._session_lock = asyncio.Lock()

async def _persist_progress(self):
    async with self._session_lock:
        self.run.total_people_found = self.total_people
        ...
        await self.session.flush()
```

### FIX 2: Single Pipeline Run (not two)
**Problem**: Preview creates run #441, confirm creates run #442 via start_gathering
**Solution**: Confirm should UPDATE the existing pending_approval run, not create a new one

```python
# In tam_gather confirm:
# 1. Find existing pending_approval run for this project
# 2. Update it: status=running, start gathering INTO it
# 3. Don't call start_gathering (which creates NEW run)
```

### FIX 3: Probe = 1 page only
**Problem**: Probe fetches per_page=100 but then start_gathering fetches 10 more pages
**Solution**: Probe is ONLY for total_available count + saving 100 companies. Gathering happens at confirm.

### FIX 4: Tool Schema Fixes
1. `create_project`: make `name` optional (auto-generate from website domain)
2. `confirm_offer`: change `project_id` from integer to `oneOf: [integer, string]` or just accept both
3. `align_email_accounts`: make `run_id` optional (already done in handler, but schema still requires it)
4. `list_email_accounts`: DON'T return all accounts. Return count + link to UI page. Never dump 2411 accounts into MCP.

### FIX 5: Email Accounts UX
- Don't list accounts in MCP (too large)
- Return: "2,411 accounts available. View at http://host/campaigns/accounts"
- Accept filter pattern: "all with elnar" → return count + preview of first 5
- Pre-cache accounts when SmartLead key connected

### FIX 6: Pipeline Completion Banner (already deployed)
- Show COMPLETED/INSUFFICIENT/PENDING APPROVAL banners

### FIX 7: Total Company Count at Top
- Always show total at top of list, not just "50 companies" (page size)

---

## Implementation Priority

1. **FIX 1**: Session lock in streaming pipeline (5 min) — unblocks everything
2. **FIX 2**: Single run (preview updates on confirm) (15 min)
3. **FIX 4**: Tool schema fixes (10 min)
4. **FIX 3**: Probe = 1 page (5 min)
5. **FIX 5**: Email accounts UX (15 min)
6. **FIX 7**: Total count at top (5 min)
