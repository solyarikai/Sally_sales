# Architecture Bugs Fix Plan — Found via Real User Flow (Apr 2, 2026)

All bugs discovered from pipelines 478, 481, 483 and user rinat.khatipov@gmail.com connection.

---

## BUG 1: Pipeline Stuck in `running` After KPI Met (CRITICAL)

**Observed**: Pipeline 483 — KPI met (101/100 people) but status stayed `running`. Auto-push never fired. Had to manually finalize.

**Root cause**: `StreamingPipeline.run_until_kpi()` sets `_kpi_met = True` which stops the people worker from extracting more contacts. BUT scrape/classify workers keep draining their queues (200+ items each). `run_until_kpi()` waits for ALL workers to finish before returning. The orchestrator's `run_pipeline_background()` only finalizes (status=completed, auto-push) AFTER `run_until_kpi()` returns.

**Impact**: Every pipeline that hits KPI via keywords (large queue) gets stuck. The more companies in the queue, the longer it takes. Pipeline 483 had ~2500 companies still being scraped/classified when KPI hit.

**Fix**:
1. When `_kpi_met` is set, immediately send poison pills to scrape_queue and classify_queue
2. Workers check `_kpi_met` at the top of their loop and exit early
3. `_feed_apollo_pages()` checks `_kpi_met` before fetching next batch
4. `run_until_kpi()` returns result immediately after KPI met, cancels remaining worker tasks
5. Orchestrator finalizes (completed + auto-push) without waiting for workers to drain

**Files**: `streaming_pipeline.py` — `_scraper_worker()`, `_classifier_worker()`, `run_until_kpi()`, `_feed_apollo_pages()`

---

## BUG 2: Elapsed Time Keeps Ticking After KPI Met (MAJOR)

**Observed**: Pipeline 483 showed ever-increasing elapsed time in UI even after KPI was met. Frontend calculates `elapsed = now() - started_at` with no freeze point.

**Root cause**: `duration_seconds` on GatheringRun is only set when status transitions to `completed`. Since the pipeline was stuck in `running` (Bug 1), `duration_seconds` was null and the frontend fell back to live calculation.

**Fix**:
1. When `_kpi_met` is set in streaming pipeline, immediately set `duration_seconds` on the GatheringRun = time from started_at to now
2. Frontend: if `duration_seconds` is set, show that. If null and status=running, show live elapsed. If null and status=completed/insufficient, calculate from started_at→completed_at.
3. The pipeline should store `kpi_met_at` timestamp on GatheringRun for accurate timing

**Files**: `streaming_pipeline.py` (`_persist_progress`), `pipeline_orchestrator.py`, frontend `PipelinePage.tsx`

---

## BUG 3: SmartLead Campaign Settings 400 Error (MINOR)

**Observed**: `set_campaign_settings` returned 400 Bad Request during auto-push for campaign 3120832. Campaign was created and leads uploaded, but settings may be wrong.

**Root cause**: `set_campaign_settings()` accepts optional params `track_open`, `stop_on_reply`, `plain_text` but the SmartLead API may have changed its expected payload format, or the doc_settings extraction produced invalid values.

**Fix**:
1. Add error handling in `_auto_push_to_smartlead()` — log warning but continue (settings 400 is not fatal)
2. Verify the SmartLead API payload format matches current API version
3. Add retry with default settings if custom settings fail

**Files**: `smartlead_service.py` (`set_campaign_settings`), `pipeline_orchestrator.py` (`_auto_push_to_smartlead`)

---

## BUG 4: SmartLead Rate Limiting on Campaign Create (MINOR)

**Observed**: First attempt to create SmartLead campaign for run 483 got 429 Too Many Requests. The retry (built into `create_campaign`) also failed. Had to wait 15s and retry manually.

**Root cause**: `create_campaign()` retries once on "Plan expired" but NOT on 429. Rate limiting is common when multiple pipelines finish close together.

**Fix**:
1. Add 429 retry with exponential backoff (3 retries, 5s/10s/20s delays) in `create_campaign()`
2. Apply same retry logic to all SmartLead API calls in `_auto_push_to_smartlead()`

**Files**: `smartlead_service.py` (`create_campaign`, `_api_call`)

---

## BUG 5: Scraper 47% Failure Rate — Apify 590 Not Retried (FIXED)

**Observed**: Pipeline 478 — 1536/3274 companies failed scraping (47%). All failures were `590 UPSTREAM502/504` from Apify proxy.

**Root cause**: Scraper retried on `429, 500, 502, 503, 504` but NOT on `590` (Apify's custom upstream error code).

**Status**: FIXED on Apr 2. Added:
- 590/UPSTREAM errors to retry list
- Direct fetch fallback (no proxy) when proxy fails
- HTTP fallback if direct HTTPS also fails

**Files**: `scraper_service.py` — deployed

---

## BUG 6: MCP SSE Initialization Race — "Request Before Initialization Complete" (CRITICAL)

**Observed**: User rinat.khatipov@gmail.com — every tool call returns `MCP error -32602: Invalid request parameters`. Logs show `"Failed to validate request: Received request before initialization was complete"` for all requests from IP 93.109.140.220.

**Root cause**: MCP SDK 1.26.0 requires `initialize` → `initialized` handshake before accepting tool calls. When using the old `npx mcp-remote` approach (which Rinat had), the initialization handshake fails or times out. The new SSE direct approach (type: "sse") handles initialization correctly.

Multiple SSE connections from the same IP without tokens create orphaned sessions where initialization never completes. The `_latest` token fallback makes it worse by mixing sessions.

**Fix**:
1. Setup page already updated to show SSE format (deployed) — Rinat needs to re-copy
2. Add explicit `@mcp_server.initialize()` handler that logs success/failure
3. Add timeout: if initialization doesn't complete within 10s, close the SSE connection
4. Remove `_session_tokens["_latest"]` fallback — each session must authenticate independently
5. Log which sessions completed initialization vs which are stuck

**Files**: `server.py`, `main.py`

---

## BUG 7: Global Token State Contamination — `_session_tokens["_latest"]` (CRITICAL)

**Observed**: User 194 (rinat.khatipov) shows 1 tool call and 9 conversations she never made. Tokens from other users bled into her session via `_latest` fallback.

**Root cause**: `server.py` line 22: `_session_tokens: dict[str, str] = {}` is shared across ALL sessions. A `_latest` key gets overwritten by every new SSE connection. When a tool call doesn't have a token, it falls back to `_session_tokens["_latest"]` — which could be ANY user's token.

**Fix**:
1. Remove `_latest` key entirely — NEVER fall back to "most recent token"
2. Each SSE session must carry its own token extracted from the URL query string
3. Store tokens per `session_id`, not globally
4. If a tool call has no valid token → return auth error, NEVER silently use another user's token
5. Clean up orphaned sessions after disconnect

**Files**: `server.py` (`_session_tokens`, `call_tool`), `main.py` (SSE handler)

---

## BUG 8: No Country/City/Size Data for Most Companies (EXPECTED BEHAVIOR)

**Observed**: Pipeline 481 — only 70/1525 companies (4.6%) have country/city/employee_count. Pipeline 445 had 64%.

**Root cause**: NOT a bug. Apollo returns null for these fields on many companies, especially smaller/less-indexed ones. The code correctly saves whatever Apollo provides. The difference between runs is the query type: location-filtered searches (Italy) return companies WITH geo data, while broad keyword searches return many sparse profiles.

**Possible enhancement**: After classification, bulk-enrich target companies to fill in missing data (costs 1 credit/company but only ~50 targets). Add as optional step, not default.

---

## BUG 9: Hardcoded Classification Rules Still Present (KNOWN — from Audit)

**Observed**: Classification prompt in `streaming_pipeline.py` has fintech-specific exclusion categories. Role exclusions in `apollo_service.py` hardcoded. Both break for non-fintech campaigns.

**Status**: Already documented in `PIPELINE_CODE_AUDIT.md` as HARDCODE-01 and HARDCODE-02. Fix requires making all classification text dynamic from document extraction.

---

## PRIORITY ORDER

| # | Bug | Severity | Effort | Impact |
|---|-----|----------|--------|--------|
| 1 | Pipeline stuck after KPI met | CRITICAL | Medium | Every pipeline with large queue gets stuck |
| 7 | Global token contamination | CRITICAL | Small | Security — wrong user attribution |
| 6 | SSE initialization race | CRITICAL | Medium | New users can't connect |
| 2 | Elapsed time never freezes | MAJOR | Small | UX — confusing display |
| 9 | Hardcoded classification | MAJOR | Large | Blocks generality |
| 4 | SmartLead 429 retry | MINOR | Small | Occasional push failure |
| 3 | SmartLead settings 400 | MINOR | Small | Settings may be wrong |

**Fix order**: 1 → 7 → 6 → 2 → 4 → 3 (then 9 separately as larger effort)
