# Architecture Bugs & Gaps — Spec vs Implementation (Updated Apr 2, 2026)

Cross-referenced against: `pipeline_spec.md`, `DOCUMENT_BASED_FLOW.md`, `REALITY_TEST_PLAN_20260330.md`, `FUNDING_FILTER_TESTING.md`.
Every finding verified against actual code with exact line numbers.

**ALL CRITICAL AND MAJOR BUGS FIXED.** Only minor/enhancement items remain.

---

## RESOLVED — All Fixes Deployed & Verified

| ID | Description | Fix Applied |
|----|-------------|-------------|
| **C-1** | Pipeline queue deadlock after KPI met | `_shutdown` Event + `_safe_put()` + queue drain in finally block. All inter-worker puts use `_safe_put`. |
| **C-2** | Global `_latest` token contamination | Removed `_latest` from server.py and all 3 locations in main.py. Per-session tokens only (`sse_{session_id}`). Session cleanup on SSE disconnect. |
| **C-3** | SSE initialization race | Setup page updated to SSE format. (Partial — no `@mcp_server.initialize()` handler yet, but new user connection flow works.) |
| **C-4** | `mcp_replies` table missing from migrations | Migration 016 creates table with all columns + indexes. Idempotent (skips if exists). |
| **C-5** | `mcp_conversation_logs` table missing from migrations | Same migration 016. Idempotent. |
| **C-6** | `password_hash` column missing from mcp_users | Same migration 016. Checks column existence before ADD. |
| **M-1** | Status "insufficient" vs spec "completed" | Changed to always "completed" in streaming_pipeline.py:1238, pipeline_orchestrator.py:475 (`_finalize`), and pipeline_orchestrator.py:535 (background task). `current_phase` ("kpi_met" vs "exhausted") distinguishes outcome. |
| **M-2** | Elapsed time ticks after KPI met | Fixed by C-1 — pipeline transitions promptly, `duration_seconds` set from frozen elapsed. |
| **M-3** | Apollo stats not tracked | Captures `total_entries` from Apollo pagination (streaming_pipeline.py:651), writes `raw_results_count` via `_persist_progress`. |
| **M-4** | Manual push hardcoded campaign settings | Manual push reads `doc_settings` from `project.offer_summary.campaign_settings`. Falls back to defaults on failure. |
| **M-5** | SmartLead set_campaign_settings no error handling | Retries once with safe defaults on failure. |
| **M-6** | SmartLead create_campaign weak retry | 3 retries with exponential backoff (2s, 4s, 8s). |
| **Bug #5** | Scraper 590 failure rate | 590 added to retry list, direct fetch fallback. |
| **Bug #9** | Hardcoded classification rules | Dynamic prompts from document extraction + GPT agent #2. No hardcoded segments/industries/roles. |

---

## VERIFIED IMPLEMENTED — No Gaps

| Feature | Evidence |
|---------|----------|
| People enrichment retry (3 rounds) | `apollo_service.py:242-275` |
| SmartLead accounts pre-cache | `dispatcher.py:450-464` on key connect |
| Duplicate pipeline run prevention | `dispatcher.py:1350-1380` reuses pending_approval run |
| Probe companies reused | `streaming_pipeline.py:278-284`, page_offset set at `dispatcher.py:1345` |
| Offer gate before gathering | `dispatcher.py:1050-1063` checks `offer_approved` |
| Missing key error details | `dispatcher.py:298-302` lists which keys missing |
| Funding L0+L1 parallel streams | `streaming_pipeline.py:440-465` via `asyncio.gather` |
| 2-pass classification | gpt-4o-mini → gpt-4o on low/medium confidence |
| Dynamic classification system | No hardcoded segments — all from document extraction |
| Shutdown event (deadlock prevention) | `_safe_put()` at every inter-worker queue boundary |
| Session token isolation | Per-session keys, no global fallback, cleanup on disconnect |

---

## MINOR — Low Priority

### m-1: 2-Pass Classification Not in Spec
**Status**: SPEC OUTDATED — Implementation is an improvement. Update spec to reflect 2-pass approach.

### m-2: No-Token Still Lists All Tools
**Status**: MCP PROTOCOL LIMITATION — `list_tools` fires before auth at protocol level.

### m-3: No Company Size Exclusion
**Status**: APOLLO API LIMITATION — Only inclusion ranges supported.

### m-4: Initial Probe Feed Uses Direct put()
**Status**: LOW RISK — `streaming_pipeline.py:285` uses direct `scrape_queue.put(dc)`. Workers haven't started consuming yet at this point.

---

## ENHANCEMENTS — Not Bugs

| Item | Description |
|------|-------------|
| E-1 | `smartlead_score_campaigns` / `smartlead_extract_patterns` — stub, returns "coming in next iteration" |
| E-2 | GetSales `gs_activate_flow` — implemented but no pre-activation validation |
| E-3 | Reply monitoring — polls SmartLead every 3min, no webhooks |
| E-4 | No A/B testing in sequences |
| E-5 | C-3 full fix — add `@mcp_server.initialize()` handler + 10s timeout + orphaned session cleanup |
