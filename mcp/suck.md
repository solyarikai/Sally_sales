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

### Known limitations (not bugs)
- Pipeline tools create DB records but don't call actual Apollo/FindyMail APIs yet (adapters are stubs for non-manual sources)
- Refinement engine has verification/improvement TODOs (needs actual GPT-4o + Gemini calls)
- GOD_SEQUENCE generates template sequences, not AI-generated ones (needs Gemini integration)
- Frontend is not deployed with `npm install` — needs Node.js build on Hetzner
- No password auth — token only (by design for MVP)

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
