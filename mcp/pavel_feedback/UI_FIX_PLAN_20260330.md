# UI Fix Plan — Pavel L. Feedback (2026-03-30)

Based on `index.md` bug reports + `PIPELINE_PAGE_UI_REQUIREMENTS.md` spec + current frontend code audit.

---

## Priority Matrix

| Priority | Bugs | Why |
|----------|------|-----|
| **P0 — Blocking** | #5, #13 | No free gathering possible. Entire pipeline broken without emulators or exploration. |
| **P1 — Critical UX** | #2, #3, #11, #12 | Pipeline produces garbage results. 2% target rate = unusable. |
| **P2 — Important** | #1, #6, #8, #10 | Missing UI for token, credits, Apify. Users can't self-serve. |
| **P3 — Nice to have** | #4, #7, #9 | Gemini placeholder, already-fixed crash, reconnect UX. |

---

## Fix 1: Token Display After Signup (Bug #1)

**Problem:** Token saved to localStorage silently, user never sees it.

**Current state:** No `LoginPage.tsx` or `SetupPage.tsx` exists. Auth is handled at API level. The MCP setup flow likely returns a token that the frontend stores but never shows.

**Fix:**
1. In the MCP onboarding/setup flow, after token is received from backend:
   - Show a **modal dialog** with the full token in a monospace `<code>` block
   - Add a **"Copy to clipboard"** button using `navigator.clipboard.writeText(token)`
   - Warning text: "Save this token now. You won't see it again."
   - Modal is **not dismissable until user clicks "I've saved it"** or copies
2. Add a "Regenerate Token" button in `SettingsPage.tsx` under a new "MCP Connection" section
   - Shows current token as `mcp_abc1...xyz9` (masked)
   - "Regenerate" creates new token, shows the same modal

**Files to change:**
- `frontend/src/pages/SettingsPage.tsx` — add MCP Connection card
- New component: `frontend/src/components/TokenRevealModal.tsx`
- Backend: `POST /api/auth/regenerate-token` endpoint if not exists

**Effort:** Small (1-2h)

---

## Fix 2: Filter Confirmation Before Gathering (Bug #2)

**Problem:** MCP launches gathering without showing proposed Apollo filters to user.

**Fix — UI side:**
1. Pipeline page needs a **"Confirm Filters" modal** that shows:
   - Proposed keywords, locations, employee range, industries
   - Source type (Apollo emulator vs API)
   - Estimated result count (if available from exploration phase)
2. Modal has: "Approve & Start" / "Edit Filters" / "Cancel"
3. "Edit Filters" opens inline editing of each filter field

**Fix — MCP side (backend):**
1. `tam_gather` MCP tool must return proposed filters as a **pending state** before executing
2. New field on GatheringRun: `filters_confirmed: bool = False`
3. Gather only executes after `POST /runs/{id}/confirm-filters`

**Files to change:**
- `backend/app/api/gathering.py` — new `/runs/{id}/confirm-filters` endpoint
- `backend/app/models/gathering.py` — add `filters_confirmed` field
- `frontend/src/pages/PipelinePage.tsx` — filter confirmation modal
- MCP tool `tam_gather` — split into propose + confirm steps

**Effort:** Medium (4-6h)

---

## Fix 3: Apollo Keyword Validation (Bug #3) + Exploration Wiring (Bug #13)

**Problem:** MCP generates arbitrary keywords that don't exist in Apollo's taxonomy. Root cause: `exploration_service.py` exists but isn't wired into `tam_gather`.

**Fix:**
1. **Wire `exploration_service.py` into `tam_gather` as mandatory first step:**
   - `tam_gather` calls exploration first → probes Apollo with small queries
   - Exploration returns validated keywords + filter sets that actually return results
   - Only then does full gathering run
2. **UI: Show exploration results before full gather:**
   - New section in filter confirmation modal: "Validated Keywords"
   - Show which keywords returned results vs which returned 0
   - Let user add/remove keywords from the validated set

**Files to change:**
- `backend/app/services/exploration_service.py` — ensure it's functional
- `backend/app/services/gathering_service.py` — wire exploration into gather flow
- MCP tool handlers — add exploration step before gather

**Effort:** Large (8-12h) — this is the highest-impact fix

---

## Fix 4: Gemini Integration Error (Bug #4)

**Problem:** Backend returns `{"detail":"Unsupported integration: gemini"}` but UI shows Gemini button.

**Fix (choose one):**
- **Option A (quick):** Remove Gemini from frontend integration cards in `SettingsPage.tsx`. If backend doesn't support it, don't show it.
- **Option B (proper):** Add `gemini` to backend's supported integrations list. Store API key, test connection.

**Recommendation:** Option A for now. Add back when Gemini is actually needed.

**Files to change:**
- `frontend/src/pages/SettingsPage.tsx` — remove Gemini from `integrationCards` array
- OR `backend/app/api/integrations.py` — add gemini handler

**Effort:** Tiny (15min for Option A)

---

## Fix 5: Emulator Adapters Not Implemented (Bug #5) — CRITICAL

**Problem:** `apollo.companies.emulator`, `apollo.people.emulator`, `clay.companies.emulator` return `None` from `_get_adapter()`. Free gathering is impossible.

**Fix:**
1. Implement the 3 Puppeteer-based adapters under `backend/app/services/gathering_adapters/`:
   - `apollo_companies_emulator.py` — Puppeteer scrapes Apollo Companies tab
   - `apollo_people_emulator.py` — Puppeteer scrapes Apollo People tab
   - `clay_companies_emulator.py` — Puppeteer automates Clay TAM export
2. Register them in `_get_adapter()` mapping
3. **UI: Source type selector** in the filter confirmation modal (Fix #2) should show:
   - Available sources with cost indicator (Free / ~$0.01/company / Credits)
   - Default to emulators (free) — require confirmation for paid sources

**Note:** This is backend-heavy. The UI part is just showing available sources in the filter modal.

**Files to change:**
- `backend/app/services/gathering_adapters/` — 3 new adapter files
- `backend/app/services/gathering_service.py` — register adapters in `_get_adapter()`
- Frontend filter modal — source type selector

**Effort:** Very Large (2-3 days) — Puppeteer automation is complex

---

## Fix 6: Credit Tracking UI (Bug #6)

**Problem:** No visibility into Apollo credits spent per run or cumulative.

**Current state:** Backend returns `PipelineStats` with `apollo_credits_used` and `apollo_cost_estimate` fields, but they're not prominently displayed.

**Fix:**
1. **Per-run credit display on PipelinePage:**
   - Add a stats bar below the top controls: "This run: 502 companies fetched | ~$X.XX Apollo credits | 0 FindyMail credits"
   - Color-code: green if within budget, orange if high
2. **Cumulative on SettingsPage:**
   - New card "Credit Usage" in SettingsPage showing:
     - Apollo: X credits used (all time) / this month
     - FindyMail: X verifications ($X.XX)
     - OpenAI: $X.XX (already exists via localStorage, move to server-side tracking)
3. **Backend:** Track credits per gathering run in `gathering_runs` table
   - `credits_used_apollo: int`
   - `credits_used_findymail: int`
   - `cost_estimate_usd: float`

**Files to change:**
- `frontend/src/pages/PipelinePage.tsx` — stats bar component
- `frontend/src/pages/SettingsPage.tsx` — credit usage card
- `backend/app/models/gathering.py` — credit tracking fields
- `backend/app/services/gathering_service.py` — record credits after each phase
- `frontend/src/api/pipeline.ts` — types for credit data

**Effort:** Medium (4-6h)

---

## Fix 7: KeyError 'confidence' (Bug #7) — ALREADY FIXED

**Status:** Fixed by MCP agent during test session. Commit `77c2cf6`.

**Verify:** Check that `gathering_service.py` lines 567-571 now include `"confidence"` key in `target_list.append()`.

**No UI work needed.**

---

## Fix 8: Scrape Failure Visibility (Bug #8)

**Problem:** 29% of companies not scraped, user can't see which ones or why.

**Current state:** Apify proxy added to env. Scrape success rate should improve.

**UI Fix:**
1. **Scraped Website column** in pipeline table (per `PIPELINE_PAGE_UI_REQUIREMENTS.md`):
   - `success (12.4KB)` — green, shows text size
   - `error: 403 Forbidden` — orange, shows HTTP error
   - `pending` — gray, not yet attempted
   - `scraping...` — blue spinner
2. **Scrape stats in run header:**
   - "Scraped: 334/471 (71%) | Failed: 137 (29%)"
   - Clicking "Failed" filters table to show only failed scrapes
3. **Retry button** for failed scrapes (per-company or bulk):
   - "Retry with proxy" option if Apify is configured
   - "Retry all failed" bulk action

**Files to change:**
- `frontend/src/pages/PipelinePage.tsx` — scraped column renderer, stats bar
- `frontend/src/api/pipeline.ts` — scrape status types
- `backend/app/api/gathering.py` — retry endpoint `POST /runs/{id}/retry-scrape`

**Effort:** Medium (3-4h)

---

## Fix 9: MCP Connection Breaks After Rebuild (Bug #9)

**Problem:** Container rebuild drops SSE connection. Login fails with initialization error.

**Fix:**
1. **Frontend: SSE reconnect logic:**
   - If SSE connection drops, retry with exponential backoff (1s, 2s, 4s, 8s, max 30s)
   - Show toast: "Connection lost. Reconnecting..." with spinner
   - On reconnect, re-fetch current pipeline state
2. **Backend: Graceful shutdown:**
   - On container stop signal, send SSE close event before terminating
   - MCP server should handle re-initialization cleanly
3. **Frontend: Clear error message:**
   - If reconnect fails after 5 attempts: "MCP server restarting. Please refresh the page."
   - NOT "Invalid request parameters" — translate error codes to human-readable messages

**Files to change:**
- `frontend/src/api/client.ts` — SSE reconnect logic
- `mcp/` server code — graceful shutdown + re-init handling
- Frontend error boundary / toast system

**Effort:** Medium (4-5h)

---

## Fix 10: Apify Field in Setup UI (Bug #10)

**Problem:** No Apify configuration in Settings. Had to be inserted directly into DB/env.

**Fix:**
1. **Add Apify card to SettingsPage.tsx `integrationCards`:**
   - Label: "Apify (Proxy)"
   - Fields: API Token
   - Test: hit Apify API to validate token
   - On success: show account name + available proxy credits
2. **Backend: Read Apify from user's integration_settings, not just env:**
   - `backend/app/services/scraper_service.py` — check user settings first, fall back to env
   - `backend/app/api/integrations.py` — add `apify` to supported integrations

**Files to change:**
- `frontend/src/pages/SettingsPage.tsx` — add Apify integration card
- `backend/app/api/integrations.py` — add apify connect/disconnect/test
- `backend/app/services/scraper_service.py` — read from user settings

**Effort:** Small (2-3h)

---

## Fix 11: Client/Competitor Confusion in Analysis (Bug #11)

**Problem:** GPT prompt doesn't understand that iGaming providers are Mifort's CLIENTS, not competitors. 97.3% rejected as "direct competitors".

**Fix:**
1. **Auto-scrape sender's website before analysis:**
   - Before building GPT prompt, scrape the project owner's domain
   - Extract: what they sell, who they sell to, their value proposition
   - Include in GPT prompt: "The SENDER is [company] that provides [service]. The companies below are POTENTIAL CLIENTS, not competitors."
2. **Exploration phase (Fix #3/#13) handles this:**
   - Exploration probes a few known-good targets first
   - Learns the pattern: "these companies are targets BECAUSE they need outsourcing"
   - Feeds this context into the analysis prompt
3. **UI: Show sender context in Prompts subpage:**
   - Display what the system understood about the sender's business
   - Editable — user can correct if wrong

**This is fundamentally an exploration/prompt problem, not a pure UI fix.** But the UI should:
- Show the detected sender profile in the prompt configuration
- Let user edit/confirm before analysis runs
- Display the prompt context at Checkpoint 2

**Files to change:**
- `backend/app/services/exploration_service.py` — sender website analysis
- `backend/app/services/gathering_service.py` — inject sender context into prompt
- Pipeline page — sender context display in prompts section

**Effort:** Large (6-8h)

---

## Fix 12: GPT Segment Naming Broken (Bug #12)

**Problem:** GPT returns "YOU_ARE_CLASSIFYING" as segment name instead of real segments.

**Fix:**
1. **Structured output enforcement:**
   - Use GPT function calling / JSON mode with strict schema
   - Define allowed segment names as enum in the schema
   - Reject responses where segment name matches any prompt text
2. **Validation layer:**
   - After GPT response, check segment names against a blocklist of prompt fragments
   - If invalid segment detected, re-query with explicit instruction: "The segment name must be a SHORT business category like SLOT_DEVELOPER, not a quote from the instructions"
3. **UI: Segment editor at Checkpoint 2:**
   - Show all unique segments found
   - User can rename/merge segments before proceeding
   - Flag suspicious segments (>30 chars, contains spaces, ALL_CAPS sentence fragments)

**Files to change:**
- `backend/app/services/gathering_service.py` — GPT prompt + response validation
- `backend/app/services/analysis_prompts.py` (or wherever prompts live) — structured output schema
- Pipeline page — segment review UI at CP2

**Effort:** Medium (3-4h)

---

## Pipeline Page Overhaul (from `PIPELINE_PAGE_UI_REQUIREMENTS.md`)

The existing `PipelinePage.tsx` (1232 lines) needs significant rework to match the spec. Key changes:

### A. Replace current table with CRM-style table
- **Current:** ag-Grid with basic columns (Domain, Company Name, Status, Target checkbox)
- **Target:** CRM-pattern table with embedded column filters, click-to-modal, lazy loading
- Columns: Domain, Name, Industry, Keywords, Employee Size, Country, City, Scraped Website, Website Analysis, Status
- Remove separate Target checkbox column — Status column tells the story

### B. Add Iteration Selector
- Dropdown in top-left showing all gathering runs for this pipeline
- Each entry: `#ID — filters summary — date — N companies`
- "All" option combines companies from all iterations

### C. Add Stage Indicator
- Top-center dropdown showing current pipeline stage
- Past stages: checkmark. Current: highlighted. Future: disabled.
- Stages: Gather, Blacklist, CP1, Pre-Filter, Scrape, Analysis, CP2, Verification, CP3, Done

### D. Add Prompts Button + Subpage
- Button in top-right: "Prompts (N)"
- Subpage at `/pipeline/:runId/prompts` with prompt table
- Columns: Created, Prompt ID, Iteration, Prompt Body, Passed Companies, Identified Targets, Accuracy

### E. Add Company Detail Modal
- Replace inline expandable rows with click-to-modal (same pattern as CRM `ContactDetailModal`)
- 4 tabs: Details, Analysis, Scrape, Source
- Full GPT reasoning, scraped text preview, raw Apollo JSON

### F. Add Real-time Loading States
- Spinner at bottom during gathering: "Gathering in progress... X companies found so far"
- Per-row spinners during scraping/analyzing
- Poll every 5s or use SSE for live updates

### G. Add "View in CRM" Button
- Appears when any contacts are found
- Links to `/crm?pipeline={runId}`
- CRM page gets new Pipeline column (hidden by default, visible with filter)

### H. Remove from current implementation
- Checkpoint History section at bottom
- Separate Confidence column
- Horizontal phase bar
- Stats row
- Inline expandable rows

**Effort:** Very Large (3-5 days) — this is a full page rewrite

---

## Implementation Order

### Sprint 1 (Quick wins + unblock pipeline)
1. **Fix #4** — Remove Gemini from UI (15min)
2. **Fix #10** — Add Apify to Settings (2-3h)
3. **Fix #1** — Token reveal modal (1-2h)
4. **Fix #6** — Credit tracking UI (4-6h)

### Sprint 2 (Make pipeline produce good results)
5. **Fix #3 + #13** — Wire exploration into tam_gather (8-12h) — **highest impact**
6. **Fix #11** — Sender context in analysis prompts (6-8h)
7. **Fix #12** — Structured output + segment validation (3-4h)
8. **Fix #2** — Filter confirmation before gather (4-6h)

### Sprint 3 (Pipeline page overhaul)
9. **Pipeline page rewrite** — CRM-style table, iteration selector, stage indicator (3-5 days)
10. **Fix #8** — Scrape failure visibility + retry (3-4h)
11. **Fix #9** — MCP reconnect logic (4-5h)

### Sprint 4 (Emulators — separate track)
12. **Fix #5** — Implement Puppeteer emulator adapters (2-3 days)

---

## Total Effort Estimate

| Category | Effort |
|----------|--------|
| Quick wins (Sprint 1) | ~1 day |
| Pipeline quality (Sprint 2) | ~3-4 days |
| Pipeline page overhaul (Sprint 3) | ~4-5 days |
| Emulator adapters (Sprint 4) | ~2-3 days |
| **Total** | **~10-13 days** |

---

## Open Questions for Pavel

1. **Emulators (#5):** Are the Puppeteer scripts for Apollo/Clay already written somewhere (outside this repo)? Or from scratch?
2. **Exploration (#13):** Is `exploration_service.py` functional standalone, or does it need fixes before wiring in?
3. **Pipeline page overhaul:** Should we do incremental improvements to current page, or full rewrite to match spec?
4. **Credit tracking (#6):** Server-side tracking or is localStorage-based acceptable for now?
5. **Apify (#10):** Should scraper check per-user settings or is one global Apify key fine for all users?
