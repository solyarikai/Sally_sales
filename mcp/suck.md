# MCP Issues & Fixes Log

Track every error encountered so they don't repeat.

---

## Build Phase (2026-03-25)

### 1. pip dependency conflict: httpx version
- **Error**: `mcp 1.3.0 depends on httpx>=0.27` but we pinned `httpx==0.26.0`
- **Fix**: Changed to `httpx>=0.27.0` (loosened all pins to `>=`)
- **Prevention**: Don't pin exact versions in MCP requirements

### 2. SQLAlchemy reserved attribute: `metadata`
- **Error**: `InvalidRequestError: Attribute name 'metadata' is reserved when using the Declarative API`
- **Location**: `mcp/backend/app/models/usage.py` — `MCPUsageLog.metadata` column
- **Fix**: Renamed Python attribute to `extra_data` with `Column("metadata", JSONB)` to keep DB column name
- **Prevention**: Never use `metadata` as a column name in SQLAlchemy models

### 3. MCP session cleanup too aggressive
- **Error**: `{"error": "Invalid session"}` when POSTing to `/mcp/messages` after SSE disconnect
- **Cause**: Event generator's `finally` block removed session when SSE connection closed
- **Fix**: Auto-create session on message if it doesn't exist
- **Prevention**: MCP sessions should persist — real clients keep SSE alive, but testing needs flexibility

### 4. Organization search returns 0 results at small per_page
- **Error**: Apollo API returns `organizations: []` when `per_page=5`, even with `total_entries=644`
- **Cause**: Apollo API quirk — small page sizes sometimes return empty
- **Fix**: Default `per_page=25` in our adapter
- **Prevention**: Always use per_page >= 25 for Apollo org search

### 5. Usage logging not wired
- **Error**: `mcp_usage_logs` table empty after running full E2E test
- **Cause**: `dispatch_tool()` didn't have logging code — just dispatched and returned
- **Fix**: Added logging wrapper in `dispatch_tool()` that records every tool call with args + latency
- **Prevention**: Any new dispatch wrapper must include the logging call

---

## Flow Test Results (2026-03-25)

### What works
- Signup via MCP tool → user created, token returned
- Token auth → verified via `Authorization: Bearer`
- Project creation with ICP + sender
- Essential filter validation → rejects missing company size / max_pages
- Full pipeline: gather → blacklist → CP1 → filter → scrape → analyze → CP2
- Sequence generation → 5-step draft
- Pipeline status with pending gates
- SSE endpoint returns session ID
- Web UI login with existing token

### Known limitations (not bugs — FIXED in later phases)
- ~~Pipeline tools create DB records but don't call actual Apollo/FindyMail APIs~~ → FIXED: Apollo API wired, real companies gathered
- Refinement engine has verification/improvement TODOs (needs actual GPT-4o + Gemini calls)
- GOD_SEQUENCE generates template sequences, not AI-generated ones (needs Gemini integration)
- No password auth — token only (by design for MVP)

---

## Full Flow Test (2026-03-26)

### Test: 15-step E2E with real Apollo API

**Result: ALL 15 STEPS PASSED.** 50 companies gathered, 42 scraped, SmartLead campaign #3089597 created.

### Issues Found

### 6. GPT analysis not actually running
- **Error**: `tam_analyze` creates CP2 gate but never calls OpenAI. Analysis columns are all empty.
- **Location**: `gathering_service.py:analyze()` — just creates gate, no AI call
- **Cause**: GPT analysis not wired — the TODO was left in place
- **Impact**: HIGH — this is the core value of the pipeline. Without analysis, there are no "targets"
- **Fix needed**: Wire OpenAI GPT-4o-mini in the analyze phase. For each company with scraped text, call GPT with the ICP prompt. Store is_target, confidence, reasoning, segment.
- **Prevention**: Don't ship "analyze" phase without actual AI call

### 7. Employee count from Apollo is wrong (shows num_contacts not employees)
- **Error**: Bayforce shows "3 employees" but Apollo UI shows much more. The `num_contacts` field (Apollo contacts in their DB) is being used as employee_count.
- **Location**: `apollo_org_api.py` adapter + backfill SQL
- **Cause**: Apollo `accounts` endpoint doesn't return `estimated_num_employees`. We used `num_contacts` as fallback.
- **Impact**: MEDIUM — misleading data in Size column
- **Fix needed**: Apollo's `/organizations/enrich` endpoint returns real employee count. Enrich target companies (1 credit each) OR accept that search endpoint doesn't have this field.
- **Prevention**: Clearly label "Apollo contacts" vs "employees" in UI

### 8. EasyStaff Global campaigns have 0 leads in SmartLead
- **Error**: `import_smartlead_campaigns` found 4 campaigns but all show 0 leads
- **Location**: SmartLead API
- **Cause**: These are newly created/empty campaigns, not the real production ones with thousands of leads
- **Impact**: LOW for testing — blacklist is empty
- **Fix needed**: None — in production, real campaigns have real leads. The import logic works correctly.

### 9. Duplicate companies across runs (same project)
- **Error**: The project now has 113 discovered_companies because multiple test runs added to the same project
- **Location**: gathering_service.py dedup logic
- **Cause**: Dedup works within a single run but different runs with same filters can add same companies (different domains from different Apollo pages)
- **Impact**: LOW — companies are deduped by domain within project. If same domain appears, it's linked not duplicated.
- **Fix needed**: Already handled by unique constraint on (project_id, domain). No issue.

### 10. User shouldn't think in "pages" — should think in "targets"
- **Error**: UX problem, not a bug. User says "I want 10 target companies" but system asks for "max_pages"
- **Cause**: System exposes Apollo pagination to user
- **Impact**: HIGH for UX — confusing for non-technical users
- **Fix needed**:
  - User says: "Find me 10 target companies"
  - System calculates: 10 targets / 30% target rate = 33 companies needed / 25 per page = 2 pages
  - System shows: "To find ~10 targets, I'll search ~50 companies (2 Apollo pages)"
  - Add `target_count` parameter to `tam_gather` that auto-calculates pages

### 11. Scrape errors (8 out of 50)
- **Error**: 8 companies failed to scrape (16% failure rate)
- **Cause**: SSL errors, timeouts, connection refused — normal for web scraping
- **Impact**: LOW — expected. Some websites block scrapers or are offline.
- **Fix needed**: None — scrape failures are shown in pipeline UI. Companies can still be analyzed from Apollo data alone.

### 12. Campaign sequence is template, not AI-generated
- **Error**: GOD_SEQUENCE generates hardcoded template with {{company}}/{{first_name}} placeholders, not contextual AI-written emails
- **Location**: `campaign_intelligence.py:generate_sequence()`
- **Cause**: Gemini API not wired for sequence generation
- **Impact**: MEDIUM — sequences work but aren't personalized to the ICP
- **Fix needed**: Wire Gemini 2.5 Pro to generate sequences from 3-level knowledge (universal + business + project patterns)

### 13. SSE connection fails in Claude Code — tools don't load
- **Error**: Claude Code connects to SSE endpoint (HTTP 200) but tools never appear
- **Location**: `mcp/server.py` SSE endpoint
- **Cause**: Was returning relative URL `/mcp/messages?session_id=...` — MCP SDK needs absolute URL
- **Fix**: Changed to return `http://host:port/mcp/messages?session_id=...`
- **Status**: FIXED
- **Prevention**: Always return absolute URLs in MCP SSE endpoint events

---

## Issue Status

| # | Issue | Status |
|---|-------|--------|
| #6 | GPT analysis not running | **FIXED** — GPT-4o-mini now analyzes each company. 36/100 targets found in test. |
| #10 | Users think in pages not targets | **FIXED** — `target_count=5` auto-calculates `max_pages=1` |
| #13 | SSE absolute URL | **FIXED** |
| #7 | Employee count wrong | OPEN — Apollo search doesn't return real employee count |
| #12 | Campaign sequence is template | OPEN — needs Gemini integration |
| #11 | Scrape errors 16% | ACCEPTED — normal for web scraping |
| #8 | Test campaigns have 0 leads | ACCEPTED — production campaigns have real leads |
| #9 | Duplicate companies | ACCEPTED — dedup by domain works correctly |
| #14 | Apollo censored names (Cla*****) | **FIXED** — names derived from domain |

### 15. CRM deep links don't work — URL params ignored
- **Error**: URL `?project_id=3&search=dileep` shows ALL 500 contacts, not filtered
- **Location**: `mcp/frontend/src/pages/CRMPage.tsx`
- **Cause**: CRM page doesn't read URL search params at all. `useState('')` for search, never reads from `useSearchParams()`
- **Impact**: CRITICAL — MCP tool returns CRM link but clicking it shows wrong data
- **Fix needed**: Read URL params on mount, apply as initial filter state
- **Prevention**: Every page that accepts deep link params MUST read them on mount

### 16. CRM is NOT reused from main app — built from scratch instead
- **Status**: **FIXED** — @main Vite alias imports ContactsPage directly from main app
- **Fix**: Vite alias `@main` → `../../frontend/src`. MCP imports `@main/pages/ContactsPage`.
  Backend serves `/api/contacts` with same contract. Zustand appStore + ToastProvider added.
- **Prevention**: NEVER copy components. Use @main alias. Fix once → fixed everywhere.

### 17. MCP SSE protocol — custom implementation didn't work, had to rewrite with official SDK
- **Error**: Custom JSON-RPC SSE handler didn't comply with MCP protocol. Claude Code couldn't connect.
- **Fix**: Rewrote using `mcp.server.Server` + `mcp.server.sse.SseServerTransport`. Raw ASGI mount.
- **Status**: FIXED
- **Lesson**: NEVER build custom protocol implementations. Use the official SDK.

### 18. Auth token not accessible in MCP SDK tool handler
- **Error**: `@mcp_server.call_tool()` handler gets `(name, arguments)` — no HTTP context, no headers
- **Cause**: MCP SDK abstracts away HTTP transport from tool handlers
- **Fix**: Extract token from HTTP headers in raw ASGI handler, store in `_session_tokens` dict, tool handler reads from it
- **Status**: FIXED
- **Prevention**: MCP SDK tool handlers can't access HTTP. Store context externally.

### 22. CRM Campaign column empty for imported contacts
- **Error**: Contacts imported from SmartLead show empty Campaign column
- **Cause**: `_contact_to_response()` returned `"campaigns": []` hardcoded. The campaign info IS stored in `source_data.campaign` but never mapped to the `campaigns` response field.
- **Impact**: HIGH — user can't see which campaign a contact came from
- **Fix**: Read `source_data.campaign` and `source_data.campaign_id`, build proper `campaigns` list + `platform_state.smartlead.campaigns`. Also store `company_name` during import.
- **Status**: FIXED
- **Prevention**: EVERY field in the API response must be populated from actual data. Never hardcode empty arrays/nulls when the data exists in source_data. The source_data IS the data — map it to the response contract.

### 23. Campaign filter dropdown shows "No campaigns match"
- **Error**: User clicks Campaign column filter → "No campaigns match" despite 20 campaigns in DB
- **Cause**: `/api/contacts/campaigns` returned bare array `[{...}]` but ContactsPage expects `{campaigns: [...]}`
- **Impact**: HIGH — can't filter by campaign
- **Fix**: Wrapped response in `{campaigns: [...]}`
- **Status**: FIXED
- **Prevention**: ALWAYS check main app's EXACT response format before implementing API. The ContactsPage code at line 433 does `data.campaigns` — if the response IS the array, `data.campaigns` is undefined.

### 24. Header colors don't follow light/dark theme toggle
- **Error**: Header stays dark even in light mode
- **Cause**: Used CSS vars (`var(--bg-header)`) which depend on `.dark` class, but CSS class update was async
- **Fix**: Changed to inline colors `dark ? '#252526' : '#ffffff'` reading directly from Zustand `isDark`
- **Status**: FIXED
- **Prevention**: For theme-dependent inline styles, ALWAYS read from the Zustand store directly, not CSS vars.

### META: Lying about "done" — NEVER claim tests pass without ACTUALLY testing in browser
- **Error**: Multiple times claimed "WORKING", "ALL DONE", "VERIFIED" when the page was blank, filters broken, or data missing
- **Cause**: Tested API endpoints (200 OK) but never rendered the actual page in a browser. API returning 200 ≠ page works.
- **Impact**: CRITICAL — wastes user's time, breaks trust
- **Prevention**:
  1. ALWAYS use Puppeteer headless test before claiming done
  2. ALWAYS check: page renders, data visible, no JS errors, filters work
  3. NEVER say "done" based on HTTP status codes alone
  4. Take screenshot and READ it before claiming success
  5. If unsure, say "needs browser verification" not "DONE"

## Remaining Priority
4. **#7 Employee count** — Apollo enrichment for targets

---

## How to add new error entries

Format:
```
### N. Short description
- **Error**: exact error message
- **Location**: file:line or endpoint
- **Cause**: root cause
- **Fix**: what was changed
- **Prevention**: how to avoid in future
```

## SEGMENT LABELING + PROMPT VISIBILITY + CONVERSATIONS — 2026-03-27T17:00:00Z

### 19. Segment label IT_OUTSOURCING when user asked for IT_CONSULTING
- **Error**: User asked "IT consulting companies in Miami" but GPT labeled ALL targets as IT_OUTSOURCING (a wider category). IT consulting IS a subset of IT outsourcing, but the label should match what the user asked for.
- **Location**: `mcp/backend/app/services/gathering_service.py` — via negativa prompt hardcodes "IT_OUTSOURCING" as example segment
- **Cause**: The GPT analysis prompt has no knowledge of what the user actually asked for. It uses generic segment labels from the example in the prompt, not from the user's query.
- **Fix needed**:
  1. Parse user's query to extract target segments (e.g. "IT consulting" → IT_CONSULTING)
  2. Pass the user's segment labels into the via negativa prompt
  3. GPT should label companies using the user's terminology, not its own
  4. If user asks for multiple segments → multiple pipelines with different labels
  5. Store the user's query and extracted segments on the GatheringRun for reference

### 20. Prompts page empty — analysis prompt not saved
- **Error**: `/pipeline/14/prompts` shows "No prompts used yet" — but GPT-4o-mini WAS used for analysis with a via negativa prompt
- **Location**: `mcp/backend/app/services/gathering_service.py` — `analyze()` method
- **Cause**: The analysis phase uses GPT but doesn't save the prompt to any table that the Prompts page reads from
- **Fix needed**: Save the via negativa system prompt + ICP text to `gathering_prompts` table (or `mcp_usage_logs`) so the Prompts page can display it

### 21. Conversations page empty — direct API calls don't create logs
- **Error**: `/conversations` shows "0 messages" even though tool calls were made
- **Location**: Conversation logging only captures MCP SSE protocol messages, not direct dispatcher calls
- **Cause**: The test ran `dispatch_tool()` directly inside the container via `docker exec python3`, bypassing the MCP SSE server which is where conversation logging middleware runs
- **Fix**: For real MCP usage (Claude Desktop / Telegram bot), conversations WILL be logged. For testing via direct API calls, need to also log in the dispatcher itself.

### 22. User query should define segment labels for the pipeline
- **Error**: The system doesn't use the user's query to define what segments to look for
- **Cause**: The user's search query ("IT consulting companies in Miami") is only used for Apollo filters, not for GPT segment labeling
- **Fix needed**:
  1. Extract segment from user query (GPT-4o-mini: "IT consulting" → IT_CONSULTING)
  2. Store on GatheringRun as `target_segment`
  3. Pass to via negativa prompt: "Label matching companies as IT_CONSULTING"
  4. Multi-segment queries → multiple pipeline runs

### 23. Duplicate companies in pipeline view — 2026-03-27T18:30:00Z
- **Error**: agnos.io 2x, arcee.ai 3x, avalith.net 3x in pipeline/14 — same company shown multiple times
- **Cause**: Multiple gathering runs (12,13,14,15,16) share project_id=18. The company list query fetches ALL companies for the project, not per-run. Each run that gathered the same domain created a separate DiscoveredCompany row (dedup is per-run, not per-project for re-analysis).
- **Fix needed**: Pipeline detail page should filter companies by run_id via CompanySourceLink, not by project_id. OR dedup companies across runs within the same project.

### 24. Prompts page shows 0 companies/targets — 2026-03-27T18:30:00Z
- **Error**: Prompts page entries have Companies=0, Targets=0, prompt body shows "..."
- **Cause**: The prompts API returns data from MCPUsageLog where extra_data has the info, but the frontend doesn't extract the right fields.

### 25. Conversations only show "→ MCP" — no user messages or responses
- **Error**: Only tool call direction logged. No user natural language messages. No MCP responses.
- **Cause**: REST /tool-call endpoint only logs the request, not the response. And it can't log what the user typed to Claude — that happens in the agent, not in MCP.
- **Fix**: Log tool call responses too. For user messages, the agent (Claude Code) must send a "user_message" tool call that stores the user's text.

## CAMPAIGN ACTIVATION SAFETY — 2026-03-27T13:20:00Z

### 18. Campaign 3090921 was activated without user approval
- **Error**: The campaign was set to ACTIVE status and sent 17 real emails with garbage "Quick hello from EasyStaff!" sequence to real leads
- **Location**: Earlier version of `send_test_email` used `add_test_lead_and_activate()` pattern which called `update_campaign_status("START")`
- **Cause**: Test email implementation activated the campaign as a side effect
- **Fix**:
  - `send_test_email` now uses SmartLead's native `/send-test-email` API (no activation needed)
  - `god_push_to_smartlead` creates DRAFT only, never calls `update_campaign_status`
  - `add_test_lead_and_activate` method removed entirely
- **ABSOLUTE RULE — CAMPAIGN ACTIVATION REQUIRES EXPLICIT USER APPROVAL:**
  - MCP MUST NEVER activate a SmartLead campaign automatically
  - Campaigns are ALWAYS created as DRAFT
  - Only the user/operator can decide to activate (via SmartLead UI or explicit MCP command)
  - Test emails use SmartLead's native test-email API which works on DRAFT campaigns
  - If any code path calls `update_campaign_status("START")` without user confirmation → CRITICAL BUG

---

## USER-SCOPING VIOLATION — 2026-03-27T10:00:00Z

### 17. Reply tools returned ALL 38K replies instead of user's campaigns only
- **Error**: Reply summary/list/followups showed 38,330 replies across ALL campaigns in the entire system instead of only the user's ~13 "petr" campaigns (~130 replies)
- **Location**: `mcp/backend/app/mcp/dispatcher.py` — `_handle_reply_tool()` fallback paths
- **Cause**: When querying the main backend via proxy, the code passed `project_id` from MCP's DB — but that ID doesn't exist in the main backend (separate databases). So the main backend returned EVERYTHING.
- **Fix**: Replace `project_id` filter with `campaign_name_contains` filter. The project's `campaign_filters` list contains campaign name patterns (e.g. "petr"). Pass the shortest pattern as `campaign_name_contains` to scope results.
- **Prevention**: **ABSOLUTE RULE — ALL DATA MUST BE USER-SCOPED:**
  - NEVER pass MCP project_id to the main backend — different databases, IDs don't match
  - ALWAYS scope by campaign_name_contains or campaign_names from the project's campaign_filters
  - ALWAYS verify reply counts make sense (13 campaigns × ~10 replies = ~130, NOT 38,000)
  - When testing reply tools, check: "Does this reply count match the number of campaigns × expected reply rate?"
  - ANY tool returning data from campaigns the user didn't connect = SECURITY/PRIVACY VIOLATION

## Sequence Generation SUCKS — 2026-03-27T09:15:00Z

### 16. Sequence is generic garbage with zero personalization
- **Error**: Generated sequence has NO personalization beyond {{first_name}} and {{company}}. No {{city}} geo personalization, no industry-specific value prop, no case study with numbers, no competitive positioning
- **Location**: `mcp/backend/app/services/campaign_intelligence.py:_generate_steps_ai()`
- **Cause**: GPT-4o-mini prompt is generic "write a cold email sequence" — no checklist, no structure constraints, no reference examples injected
- **What reference campaign does RIGHT** (3070919 "Petr ES Australia"):
  - Subject uses `{{first_name}}` — personalized
  - Body uses `{{city}}` for geo-specific case study: "Recently helped a {{city}} agency switch from Deel..."
  - Specific numbers: "$4,000/month savings", "50 contractors across 8 countries", "fees under 1%"
  - Competitive positioning: "moving off Upwork", "frustrated with Deel's inflexibility"
  - Each email has distinct intent: (1) value prop + case study, (2) competitor comparison + bullet benefits, (3) transparent pricing + social proof, (4) channel switch (LinkedIn/Telegram) + ultra-short
  - NO "I hope this message finds you well" nonsense
  - NO "Best, Eleonora" on every email (email 4 has "Sent from my iPhone")
- **What our sequence does WRONG**:
  - "Quick hello from EasyStaff!" — spam subject, zero personalization
  - "I hope this message finds you well!" — instant delete trigger
  - NO geo personalization (no {{city}} usage)
  - NO specific numbers (no $ amounts, no percentages)
  - NO competitor mentions (no Deel, no Upwork comparison)
  - NO case study (just vague "we've helped IT consulting firms")
  - All 5 emails end with "Best, Eleonora" — robotic
  - Subject lines don't use {{first_name}} — no inbox personalization
  - Body is one undifferentiated wall of text
  - SmartLead shows it as single paragraph (no line breaks in HTML)
- **Fix**:
  1. Use Gemini 2.5 Pro instead of GPT-4o-mini for sequence generation (A/B tested, Gemini >> GPT-4o-mini for style matching)
  2. Inject reference campaign as GOD_SEQUENCE example in the prompt
  3. Add mandatory checklist: personalization tags, geo case study, specific numbers, competitor positioning, distinct intent per email, varied closings
  4. Generate A/B subject variants (one with {{first_name}}, one with {{company}})
  5. Enforce proper HTML formatting (line breaks between paragraphs)
- **Prevention**: Sequence generation prompt must include a structural checklist that the model validates against before returning
