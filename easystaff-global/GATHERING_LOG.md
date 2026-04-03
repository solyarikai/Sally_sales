# EasyStaff Dubai Gathering — Execution Log

## Current Numbers (March 20, 2026)

| Metric | Count |
|--------|-------|
| Discovered companies in DB | 19,125 |
| With scraped website text | 6,176 (32%) |
| Without domains (Companies Tab) | ~7,782 |
| Total GPT analysis calls | 7,949 |
| Total GPT tokens used | 16,458,040 |
| Total GPT cost | $2.47 |
| Analysis runs created | 30 |
| Analysis runs completed | 10 |
| Analysis runs failed | 15 (rate limits, truncation, stale processes) |
| Approval gates (scope) | 5 approved |
| Approval gates (target review) | 8 rejected, 4 pending |

## Segment Distribution (all analysis runs combined)

| Segment | Count | Targets |
|---------|-------|---------|
| EMPTY (failed/truncated) | 6,683 | 25 |
| NOT_TARGET (v1 prompt) | 3,375 | 0 |
| NOT_A_MATCH (v2 prompt) | 1,585 | 1 |
| OTHER_HNWI (v1 wrong segment) | 373 | 367 |
| MARKETING_AGENCY | 5 | 5 |
| TECH_STARTUP | 4 | 4 |
| IT_SERVICES | 4 | 4 |
| CONSULTING_FIRM | 4 | 4 |
| DIGITAL_AGENCY | 2 | 2 |
| CREATIVE_STUDIO | 2 | 2 |

## Problems Found & Fixed

### 1. Analysis runs too slow (sequential GPT calls)
**Problem:** 1 company at a time = 10 hours for 6,000 companies.
**Fix:** Parallel calls with asyncio.gather + semaphore. 10-25 concurrent.
**Result:** 100-275 companies/min.

### 2. No intermediate commits
**Problem:** One massive transaction for 3,000+ companies. If anything fails, all progress lost.
**Fix:** Commit every 25-50 companies.
**Result:** Progress saved incrementally.

### 3. OpenAI 429 rate limits (66% failure rate)
**Problem:** 50 concurrent calls exceeded 500 RPM limit.
**Root cause:** Indentation bug — `import random` was OUTSIDE the `if resp.status_code == 429:` block. Every response triggered backoff.
**Fix:** Corrected indentation + reduced concurrency to 10-25.
**Result:** Rate limiting resolved.

### 4. GPT responses truncated (80% empty segments)
**Problem:** `max_tokens=600` too low for via negativa prompt's JSON output. Responses cut mid-JSON: `{"segment": "NOT_A_MATCH", "is_target": false...`
**Fix:** Increased to `max_tokens=1000` (OpenAI) / `1200` (Gemini).
**Result:** Full JSON responses.

### 5. Hardcoded system prompt overriding custom prompt
**Problem:** `company_search_service.analyze_company()` had hardcoded HNWI/real_estate scoring rubric. Custom via negativa prompt was injected as target_segments but the system prompt still told GPT to use old segment names.
**Result:** Companies tagged as OTHER_HNWI, INVESTMENT, FAMILY_OFFICE instead of DIGITAL_AGENCY, SOFTWARE_HOUSE.
**Fix:** Added `custom_system_prompt` parameter. When set, replaces the legacy system prompt entirely.

### 6. Legacy prompt duplicated in user message
**Problem:** Even after adding `custom_system_prompt`, the old `prompt = f"""...` was NOT inside the `else` block — it ran ALWAYS, overwriting the custom user message.
**Fix:** Moved legacy prompt construction inside `if not custom_system_prompt:` block.

### 7. OpenAI quota exhausted
**Problem:** API returned `insufficient_quota` (billing limit, not rate limit). All calls returned 429.
**Fix:** User topped up OpenAI account.

### 8. Multiple stale analysis processes competing
**Problem:** 6 simultaneous analysis processes from different script invocations, each with its own semaphore. Combined = 150+ concurrent GPT calls.
**Fix:** Kill all stale processes before launching new one. Reset stale `running` analysis runs to `failed`.

### 9. DB index corruption
**Problem:** `ix_discovered_company_project_domain` corrupted during mass imports. Caused `IntegrityError` on blacklist updates.
**Fix:** `REINDEX TABLE discovered_companies` after removing 20 duplicate records.

### 10. Segment key mismatch (v1 vs v2)
**Problem:** V1 prompt outputs `matched_segment`. V2 prompt outputs `segment`. Code only reads `matched_segment`.
**Fix:** Added normalization: if `segment` exists but `matched_segment` doesn't, copy it.

## What Still Needs Fixing

1. **6,683 EMPTY segments** — most are from failed analysis runs. Need to re-analyze these companies with the fixed pipeline.
2. **373 OTHER_HNWI targets** — from v1 prompt with wrong segment names. Need re-analysis with v2 via negativa prompt.
3. **7,782 companies without domains** (Companies Tab) — need RESOLVE phase to get domains from LinkedIn URLs.
4. **3,538 companies with domains but no scraped text** — scraping failed (timeout, blocked). Could retry or use different scraper.
5. **Target count too low** — only ~450 real targets so far. KPI is 5,000. Need more raw companies (20K+) AND better target rate.

## Gathering Runs in System

| Run | Strategy | Raw | New | Duplicates | Phase |
|-----|----------|-----|-----|-----------|-------|
| #1 | B (founder/c_suite/owner) | 5,602 | 3,867 | 8 | awaiting_targets_ok |
| #2 | Companies Tab (industry tags) | 7,782 | 7,782 | 0 | scraped (no domains) |
| #3 | C (vp/director/manager) | 1,207 | 1,143 | 64 | awaiting_targets_ok |
| #4 | A (80+ keywords) | 2,909 | 1,844 | 81 | awaiting_targets_ok |
| #5 | D (industry keywords) | 203 | 173 | 30 | awaiting_targets_ok |
