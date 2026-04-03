# Architecture Bugs & Gaps — Spec vs Implementation (Apr 3, 2026)

Cross-referenced against: `pipeline_spec.md`, `DOCUMENT_BASED_FLOW.md`, `REALITY_TEST_PLAN_20260330.md`, `FUNDING_FILTER_TESTING.md`.

**Updated 2026-04-03: New gaps found after 1-filter-per-request pipeline rewrite.**

---

## ALL RESOLVED

| ID | Description | Fix |
|----|-------------|-----|
| **C-1** | Pipeline queue deadlock after KPI met | `_shutdown` Event + `_safe_put()` + queue drain. Every inter-worker `put()` — including probe feed — uses `_safe_put`. |
| **C-2** | Global `_latest` token contamination | Removed `_latest` everywhere. Per-session tokens only. `cleanup_session()` evicts on SSE disconnect. |
| **C-3** | SSE initialization race | Session tracking via `_initialized_sessions`. `cleanup_session()` removes orphaned sessions on disconnect. |
| **C-4** | `mcp_replies` table missing from migrations | Migration 016 (idempotent). |
| **C-5** | `mcp_conversation_logs` table missing from migrations | Migration 016 (idempotent). |
| **C-6** | `password_hash` column missing | Migration 016 (idempotent). |
| **M-1** | Status "insufficient" vs spec "completed" | Always "completed" in `streaming_pipeline.py`, `pipeline_orchestrator.py` (`_finalize` + background task). `current_phase` distinguishes kpi_met vs exhausted. |
| **M-2** | Elapsed time ticks after KPI | Fixed by C-1 — pipeline transitions promptly, `duration_seconds` set from frozen elapsed. |
| **M-3** | Apollo stats not tracked | Captures `total_entries` from Apollo pagination, writes `raw_results_count` via `_persist_progress`. |
| **M-4** | Manual push hardcoded campaign settings | Reads `doc_settings` from `project.offer_summary.campaign_settings`. Falls back to defaults on failure. |
| **M-5** | SmartLead settings 400 not handled | `set_campaign_settings` retries once with safe defaults on failure. |
| **M-6** | SmartLead create_campaign weak retry | 3 retries with exponential backoff (2s, 4s, 8s). |
| **m-4** | Probe feed used direct `queue.put()` | Now uses `_safe_put` like all other inter-worker puts. |
| **Bug #5** | Scraper 590 failures | 590 in retry list + direct fetch fallback. |
| **Bug #9** | Hardcoded classification | Dynamic prompts from document extraction + GPT agent #2. |
| **C-7** | Probe page accounting — `run.pages_fetched` set to `max_pages` (10) instead of 1, causing streaming pipeline to skip pages 2-10 | Fixed: `run.pages_fetched = probe_page_done` (actual pages fetched by probe). Pipeline now starts from page 2 correctly. |

---

## OPEN BUGS (from Apr 3 pipeline rewrite)

### C-8: `_current_source` Race Condition — CRITICAL
**File**: `streaming_pipeline.py` line 529
**Problem**: Multiple `_run_single_filter` coroutines run in parallel via `asyncio.gather`. All write to `self._current_source`. When `_ingest_page_results` reads it, it gets the WRONG source because another coroutine overwrote it.
**Impact**: Companies tagged with wrong `found_by` keyword/industry. Per-keyword `targets_found` stats are inaccurate.
**Fix**: Pass `source_info` dict as parameter through `_fetch_pages_parallel` → `_ingest_page_results` instead of using shared instance variable.

### C-9: Exclusion logic missing competitor conquest warning on production
**File**: Production `document_extractor.py` line 48
**Problem**: Prompt says `exclusion_list: company types to NOT target` without warning about competitor conquest sequences. GPT may extract Belkins/CIENCE as exclusions when the document intends them as targets for conquest.
**Fix**: Add to exclusion_list prompt: "If the document describes targeting users of competing vendors (competitor conquest), those are TARGETS, not exclusions."

### M-7: PipelinePage explanation text references removed systems
**File**: `PipelinePage.tsx` lines 769-776
**Problem**: References "AI classifier" (A11 — removed), "112 industry categories" (now 84), "20 consecutive pages" (now LOW_YIELD_THRESHOLD=10), "keywords_first strategy" (no longer exists as a named strategy).
**Fix**: Update text to reflect current architecture: 84 industries, 1-filter-per-request parallel, per-keyword tracking.

### M-8: `_level_stats` dead code in PipelinePage
**File**: `PipelinePage.tsx` lines 751-767
**Problem**: "CASCADE LEVELS" section reads from `run.filters._level_stats` which is no longer populated. The new `_run_single_filter` architecture stores `keyword_stats` and `industry_stats` instead.
**Fix**: Remove dead `_level_stats` display. Already replaced by KEYWORD PERFORMANCE and INDUSTRY PERFORMANCE tables.

### m-5: `_wait_for_processing` doesn't track in-flight tasks
**File**: `streaming_pipeline.py` lines 566-580
**Problem**: Checks `queue.qsize() == 0` but workers may have dequeued items still being processed. Method returns "done" prematurely.
**Impact**: Low — may cause premature round transitions where KPI check sees stale target counts.
**Fix**: Track in-flight count with atomic counter: increment on dequeue, decrement on task completion.

---

## SPEC GAPS (requirements docs outdated, not code bugs)

### GAP-1: REALITY_TEST_PLAN checkpoint flow is obsolete
**Source**: REALITY_TEST_PLAN Phase 4 Tests 4.1-4.4
**Issue**: Describes manual tam_blacklist_check → checkpoint → approve flow. Replaced by auto-pipeline streaming.
**Action**: Update REALITY_TEST_PLAN to reflect auto-pipeline architecture.

### GAP-2: REALITY_TEST_PLAN iteration selector is obsolete
**Source**: REALITY_TEST_PLAN Phase 7 Tests 7.1-7.8
**Issue**: Describes pipeline_iterations table + iteration selector UI. Replaced by round-based gathering with keyword/industry performance tracking.
**Action**: Update REALITY_TEST_PLAN Phase 7 to describe keyword/industry stats UI instead.

### GAP-3: REALITY_TEST_PLAN references old IP
**Source**: REALITY_TEST_PLAN Test 1.1
**Issue**: References `http://46.62.210.24:3000/setup`. Should be `https://gtm-mcp.com/setup`.
**Action**: Update all URLs in REALITY_TEST_PLAN.

### GAP-4: Funded vs unfunded not shown in UI
**Source**: FUNDING_FILTER_TESTING "UI Visibility"
**Issue**: `source_data.funded_stream` tracked per company but PipelinePage doesn't display it.
**Action**: Add funded badge to company table (low priority).

---

## VERIFIED IMPLEMENTED — No Gaps

| Feature | Evidence |
|---------|----------|
| People enrichment retry (3 rounds) | `apollo_service.py:242-275` |
| SmartLead accounts pre-cache | `dispatcher.py:450-464` |
| Duplicate run prevention | `dispatcher.py:1350-1380` |
| Probe companies reused | `streaming_pipeline.py:278-285` + `dispatcher.py:1345` |
| Offer gate before gathering | `dispatcher.py:1050-1063` |
| Missing key error details | `dispatcher.py:298-302` |
| Funding L0+L1 parallel | `streaming_pipeline.py:440-465` |
| 2-pass classification | gpt-4o-mini → gpt-4o on low/medium confidence |
| Dynamic classification | No hardcoded segments/industries/roles |
| Shutdown event (deadlock prevention) | `_safe_put` at every queue boundary |
| Session token isolation | Per-session keys + `cleanup_session()` on disconnect |
| Email verification (verified-only) | `apollo_service.py:295` — only `email_status == "verified"` saved |
| Credit tracking (1/person not 1/search) | `apollo_service.py:288-289` |
| GPT role selection + CRO disambiguation | `apollo_service.py:320-399` |
| SmartLead variable consistency | Upload uses `company_name`; sequences use `{{company}}`; SmartLead auto-maps |
| Reply classification + Telegram notify | `reply_monitor.py:184-200` — warm replies → Telegram |
| Document extraction (all fields) | `document_extractor.py:35-84` + variable normalization |
| 7 "NEVER" rules from spec | All verified compliant (filters, sessions, scraping, classification) |

---

## NOT FIXABLE — External Limitations

| Item | Why |
|------|-----|
| No-token still lists all tools | MCP SDK protocol: `list_tools` fires before auth at protocol level |
| No company size exclusion | Apollo API only supports inclusion ranges |
| 2-pass classification not in spec | Spec outdated — implementation is an improvement |

---

## FUTURE ENHANCEMENTS (not bugs)

| Item | Description |
|------|-------------|
| E-1 | `smartlead_score_campaigns` / `smartlead_extract_patterns` — feature stubs |
| E-2 | GetSales `gs_activate_flow` — add pre-activation validation |
| E-3 | Reply monitoring — add webhook support (currently polls every 3min) |
| E-4 | A/B testing in sequences |
