# MCP System — What's Left to Build

Updated 2026-03-27. Only remaining work items. See `answers2603.md` for decision rationale.

---

## Status Summary

| Area | Status |
|------|--------|
| Docker + DB + Alembic | DONE |
| Auth (signup, token, middleware) | DONE |
| Integration connect (SmartLead, Apollo) | DONE |
| Project CRUD | DONE |
| Gathering pipeline (gather > blacklist > CP1 > pre-filter > scrape > analyze > CP2 > verify > CP3) | DONE |
| MCP SSE server + 26+ tools + dispatcher | DONE |
| Sequence generation (GOD_SEQUENCE) | DONE |
| SmartLead campaign creation (DRAFT) | DONE |
| Pipeline page (company table, filters, modal, segments, confidence) | DONE |
| Projects page | DONE |
| Prompts/iterations page | DONE |
| Setup page | DONE |
| Account page | DONE |
| CRM page (via @main alias) | DONE |
| Tasks/Replies page (via @main alias, stub endpoints) | DONE |
| User-scoped pipeline | DONE |
| REST endpoints (gates, sequences, campaigns, runs) | DONE |
| SmartLead campaign import (import_smartlead_campaigns tool) | DONE (tool defined) |
| Filter intelligence (suggest_apollo_filters) | DONE |
| Refinement engine (refinement_engine.py) | DONE (code exists, not E2E tested) |
| Reply analysis service (classification logic) | DONE (code exists, not wired) |

---

## Remaining Work — Priority Order

### P0: Wire reply tracking to MCP campaigns

**What**: When `import_smartlead_campaigns` runs, it should automatically kick off background reply analysis.

**Files**: `mcp/backend/app/services/reply_analysis_service.py`, `mcp/backend/app/mcp/dispatcher.py`

**Tasks**:
1. In dispatcher's `import_smartlead_campaigns` handler, after importing contacts, call `reply_analysis_service.analyze_campaign_replies()` as a background task
2. Implement `analyze_campaign_replies()`: call SmartLead `/campaigns/{id}/replies` API, fetch reply text for each, run `classify_reply()`, store results in `extracted_contacts.source_data` (fields: `has_replied`, `reply_category`, `reply_confidence`, `reply_time`, `reply_text`)
3. Wire the CRM page's `latest_reply_category` column to show real data (the field mapping in `contacts.py:_contact_to_response` already reads from `source_data`)

**Verify**: After importing campaigns, CRM shows contacts with reply categories. `query_contacts(reply_category="interested")` returns warm leads.

---

### P1: Test email sending after campaign creation

**What**: After `god_push_to_smartlead` creates a DRAFT campaign, send a test email to the user's signup email.

**Files**: `mcp/backend/app/services/smartlead_service.py`

**Tasks**:
1. Add `send_test_email(campaign_id, recipient_email)` method using SmartLead `POST /api/v1/campaigns/{id}/test-email`
2. Wire into dispatcher: after `god_push_to_smartlead` succeeds, call `send_test_email` with the user's email from the session
3. Return test email status in the tool response

---

### P2: Refinement engine E2E test

**What**: `refinement_engine.py` (193 lines) has the full algorithm but has never run against real data.

**Files**: `mcp/backend/app/services/refinement_engine.py`

**Tasks**:
1. Run the refinement loop on a real pipeline run with ~50 companies
2. Verify: GPT-4o-mini analyzes, GPT-4o verifies sample, Gemini improves prompt, accuracy converges
3. Fix any runtime errors (API key injection, model parameters, response parsing)
4. Wire `auto_refine=true` flag in `tam_analyze` dispatcher to trigger the engine

---

### P3: CRM deep links with filter params

**What**: `query_contacts` MCP tool should return URLs that open CRM pre-filtered.

**Files**: `mcp/backend/app/mcp/dispatcher.py`, `mcp/frontend/src/App.tsx` (routing)

**Tasks**:
1. Construct CRM URL with query params: `/crm?project_id=X&reply_category=interested&has_replied=true`
2. Ensure the @main CRM page reads these params on mount and applies filters
3. Test: agent says "warm leads" -> tool returns link -> user clicks -> CRM shows filtered view

---

### P4: Apollo filters auto-discovery cron

**What**: Background job to discover Apollo's industry/keyword taxonomy and cache it.

**Files**: `mcp/apollo_filters/PLAN.md` (199 lines, plan exists), needs implementation

**Tasks**:
1. Create `mcp/backend/app/services/apollo_taxonomy_service.py`
2. Scrape Apollo's industry tree via API probe calls (1 credit per probe)
3. Store in Redis cache with daily TTL
4. `suggest_apollo_filters` reads from cache instead of generating from scratch each time
5. Schedule as background task on startup

---

### P5: Sequence subject line normalization

**What**: Merge tags in generated sequences (`{{first_name}}`, `{{company}}`) must be clean and match SmartLead's syntax.

**Files**: `mcp/backend/app/services/campaign_intelligence.py`

**Tasks**:
1. Add `_normalize_sequence_fields()` post-processing: strip special chars from names, verify merge tag format
2. Validate against SmartLead's expected merge tag syntax
3. Apply before `push_to_smartlead`

---

### P6: Contact detail — planned sequence view

**What**: When clicking a contact in CRM, show the email sequence planned for them (not just past conversation).

**Files**: MCP frontend CRM integration, `mcp/backend/app/api/contacts.py`

**Tasks**:
1. Add endpoint: `GET /api/contacts/{id}/planned-sequence` — joins extracted_contact -> discovered_company -> gathering_run -> generated_sequence
2. Return sequence steps with scheduled day offsets
3. Show in contact detail modal as "Planned" tab alongside "Conversation" tab

---

### P7: Apollo filter performance tracking per keyword

**What**: Show which Apollo keywords/filters produced the most targets.

**Files**: `mcp/backend/app/api/pipeline.py`

**Tasks**:
1. Add endpoint: `GET /api/pipeline/filter-stats?project_id=X` — aggregate target rate by keyword/filter across runs
2. Show in Prompts page: for each iteration, show filters applied + how many targets each keyword produced
3. This helps the agent and user understand which filters work best

---

### P8: Learning page (operator corrections)

**What**: Page showing how operator corrections improved reply drafts over time.

**Depends on**: P0 (reply tracking must work first)

**Tasks**:
1. Store operator corrections: when user edits a draft via MCP, log the diff
2. Build Learning page: corrections over time, patterns learned, quality scores
3. Low priority until reply flow is production-ready

---

### P9: Onboarding flow polish

**What**: Telegram notification opt-in, guided first-run experience.

**Tasks**:
1. Optional Telegram bot token in Setup page
2. First-run wizard: connect APIs -> create/select project -> import campaigns -> ready
3. Low priority — current MCP chat-based onboarding works

---

## Architecture Reference

```
MCP Client (Claude Desktop)          Browser (:3000)
    |                                    |
    | SSE (MCP protocol)                 | HTTP
    |                                    |
    v                                    v
 mcp-backend (FastAPI, :8002)
  /mcp/sse  — MCP protocol
  /api/*    — REST for frontend
  Services  — pipeline, refinement, GOD
         |
    +----+----+
    v         v
mcp-postgres  mcp-redis
(:5433)       (:6380)
```

Existing system (postgres:5432, redis:6379, backend:8000, frontend:80) is UNTOUCHED.

---

## Key Files

| File | Purpose |
|------|---------|
| `mcp/backend/app/mcp/tools.py` | 26+ tool definitions with JSON schemas |
| `mcp/backend/app/mcp/dispatcher.py` | Tool name -> service method routing |
| `mcp/backend/app/mcp/server.py` | MCP SSE protocol handler |
| `mcp/backend/app/services/gathering_service.py` | Pipeline orchestrator |
| `mcp/backend/app/services/refinement_engine.py` | Self-refinement loop (needs E2E test) |
| `mcp/backend/app/services/filter_intelligence.py` | NL -> Apollo filters |
| `mcp/backend/app/services/campaign_intelligence.py` | GOD_SEQUENCE generation |
| `mcp/backend/app/services/reply_analysis_service.py` | Reply classification (needs wiring) |
| `mcp/backend/app/services/smartlead_service.py` | SmartLead API (campaign lifecycle) |
| `mcp/backend/app/api/pipeline.py` | REST endpoints (runs, companies, gates, sequences) |
| `mcp/backend/app/api/contacts.py` | CRM endpoints (contacts, companies) |
| `mcp/frontend/src/pages/PipelinePage.tsx` | Company table with filters, modal, status |
| `mcp/frontend/src/App.tsx` | Routing, @main alias imports for CRM + Tasks |
