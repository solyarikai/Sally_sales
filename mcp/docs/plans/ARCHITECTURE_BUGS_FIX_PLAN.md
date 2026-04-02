# Architecture Bugs & Gaps — Spec vs Implementation (Apr 3, 2026)

Cross-referenced against: `pipeline_spec.md`, `DOCUMENT_BASED_FLOW.md`, `REALITY_TEST_PLAN_20260330.md`, `FUNDING_FILTER_TESTING.md`.

**ALL BUGS FIXED. Only Apollo API and MCP protocol limitations remain (not fixable in our code).**

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
