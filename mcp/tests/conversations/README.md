# MCP Test Plan — GOD LEVEL

## 3 Layers of Testing

Testing happens at 3 levels. Each catches different bugs. ALL THREE are required.

### Layer 1: Unit Tests (backend logic)
```bash
ssh hetzner "cd ~/magnum-opus-project/repo && python3 -m pytest mcp/tests/test_processing_steps.py -v"
```
- Tests models, services, domain logic in isolation
- Fast (<10s), no network, no Docker
- **Does NOT test**: MCP protocol, agent decisions, UI

### Layer 2: REST Dispatcher Tests (tool-call endpoint)
```bash
ssh hetzner "cd ~/magnum-opus-project/repo && python3 mcp/tests/run_conversation_tests.py"
```
- Calls `/api/pipeline/tool-call` directly with pre-determined tool names and args
- Tests: dispatcher routing, DB operations, API responses, scoping
- Fast (~3-5 min for all 12 tests)
- **Does NOT test**: MCP SSE protocol, agent tool selection, Claude's understanding of user intent

### Layer 3: REAL MCP Agent Tests (the only valid test)
```
Connect a REAL Claude agent → MCP SSE → have a conversation → screenshot UI
```
- A real Claude agent (Claude Desktop, Cursor, or Claude Code CLI) connects via SSE
- Agent receives user prompts and DECIDES which tools to call
- Tests the COMPLETE chain: user intent → agent reasoning → tool selection → MCP execution → UI state
- **This is how real users will use the system**

**Layer 3 is the ONLY test that proves the system works for real users.**
Layers 1-2 are regression safety nets. They catch code bugs but can't verify agent behavior.

---

## Layer 3: How to Run Real MCP Tests

### Option A: Claude Code CLI (recommended for automation)
```bash
# Add MCP server
claude mcp add magnum-opus http://46.62.210.24:8002/mcp/sse

# Start conversation and type test prompts:
claude
> "My website is https://easystaff.io/. I'm Eleonora from EasyStaff."
> "Find IT consulting companies in Miami and video production in London"
> "Use Eleonora's email accounts from the petr campaigns"
```

### Option B: Claude Desktop (recommended for demos)
Add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "magnum-opus": {
      "url": "http://46.62.210.24:8002/mcp/sse"
    }
  }
}
```

### Option C: Cursor IDE
Add MCP server in Cursor settings → MCP Servers → URL: `http://46.62.210.24:8002/mcp/sse`

### What to Verify During Real Conversation

While the agent converses with MCP, watch these pages IN A BROWSER:

1. **http://46.62.210.24:3000/conversations** — every tool call appears in real-time
2. **http://46.62.210.24:3000/pipeline** — pipeline runs appear as gathering starts
3. **http://46.62.210.24:3000/campaigns** — campaigns appear when created
4. **http://46.62.210.24:3000/crm** — contacts appear after import

### Screenshot Verification
After each test conversation, screenshot these pages and compare:
- Pipeline page: runs visible, segment badges, target counts
- Pipeline detail: companies table with status filters
- Campaigns page: DRAFT status, sequence preview
- CRM page: contacts with campaign filter
- Conversations page: full tool call history
- Setup page: integrations connected

---

## Test Conversations (JSON specs)

Each JSON file defines ONE user journey. Used by:
- **Layer 2**: `run_conversation_tests.py` reads prompts + expected tools, calls REST API
- **Layer 3**: Human or automated agent reads prompts, types them into Claude, verifies behavior

### User 1: pn@getsally.io (EasyStaff-Global)
```
01: Full journey — auth, project setup, 2-segment gathering, sequence, campaign, replies
03: Add more targets to existing pipeline
04: Edit sequence + provide feedback + override target
05: Activate campaign with confirmation
16: Campaign lifecycle — sequence → SmartLead push (DRAFT) → test email → activate → monitoring ON
17: GetSales flow — destination clarification → LinkedIn flow → push
18: Session continuity — disconnect → reconnect → verify context restored
19: Reply intelligence — warm leads, follow-ups, CRM deep links, meetings
20: Apollo credits — cost estimation, usage history, budget cap
21: CRM verification — contacts visible, conversation tab default, source tracking
22: Campaigns monitoring — MCP vs user badge, listening toggle, bulk toggle
```

### User 2: services@getsally.io (Result + OnSocial UK)
```
02: New user — fashion brands Italy + OnSocial UK (2 projects)
09: CSV import (110 companies) → custom prompt → full pipeline
10: Google Sheet import (110, 40 overlap with CSV) → "add to existing?" → dedup
11: Google Drive import (105, 35+35 overlap) → "add to existing?" → dedup
12: Custom prompt chain — re-analyze with multi-step classification
13: Blacklist isolation — project B independent from Result
14: Source suggestion edge cases (7 scenarios)
15: Processing step add/remove iterations (4 iterations tracked)
23: Second project OnSocial UK — multi-project switching, data isolation
```

### Test Data (in `mcp/backend/test_data/`)
```
test_csv_batch.csv     — 8 companies (indices 0-7)
test_sheet_batch.csv   — 8 companies (indices 4-11, 4 overlap with CSV)
test_drive_file1.csv   — 3 companies (indices 0-2, all CSV overlap)
test_drive_file2.csv   — 3 companies (indices 4-6, CSV+Sheet overlap)
test_drive_file3.csv   — 3 companies (indices 9-11, Sheet-only)

Dedup matrix:
  CSV ∩ Sheet: 4 overlapping companies
  CSV ∩ Drive: 6 overlapping companies
  Sheet ∩ Drive: 6 overlapping companies
  Total unique across all sources: 12
```

### Data Cleanup Between Test Cycles
- Before each full test cycle: soft-delete all test user projects (`is_active=False`)
- Data stays in DB for recovery — NEVER hard-delete
- Endpoint: `DELETE /api/pipeline/cleanup-test-data`
- Each pipeline phase (pre_filter, scrape, analyze) scoped to current `gathering_run_id` — no cross-run bleed

---

## Critical MCP Behaviors to Test

### 1. Agent Tool Selection (Layer 3 ONLY)
The agent must DECIDE which tools to call based on natural language:
- "Find IT consulting companies" → `parse_gathering_intent` → `tam_gather`
- "I have a CSV" → detect source type → `tam_gather` with `csv.companies.file`
- "Make the tone more casual" → `provide_feedback`
- "Activate the campaign" → `activate_campaign` with user_confirmation

**This CANNOT be tested via REST. Only a real agent test validates tool selection.**

### 2. Multi-Segment Splitting
"IT consulting in Miami and video production in London" → 2 separate pipeline runs

### 3. Source Detection
- File path → CSV
- Google Sheet URL → Sheet
- Google Drive URL → Drive
- Keyword query → Apollo (if key available)

### 4. Dedup Across Sources
Same project, multiple sources → overlapping companies deduplicated

### 5. Project-Scoped Blacklist
Different projects can contact same company. Same project deduplicates.

### 6. Campaign Safety
- Campaign ALWAYS created as DRAFT
- Activation requires explicit user confirmation quote
- Test email auto-sent after push

### 7. Session Continuity
- `get_context` returns full user state on reconnect
- MCP remembers everything by user_id/token
- No hardcoded state between sessions

---

## Scoring (Layer 2 only)

| Dimension | Weight |
|-----------|--------|
| Correct tools called | 25% |
| Response structure (must_contain) | 25% |
| Dedup accuracy | 20% |
| Source detection | 15% |
| No errors | 15% |

**Pass**: 95% | **God**: 100%

## Scoring (Layer 3)

Manual checklist:
- [ ] Agent selected correct tools for each user prompt
- [ ] Pipeline completed without errors
- [ ] UI shows correct state at each checkpoint
- [ ] Dedup counts match expected
- [ ] Campaign created as DRAFT (never auto-activated)
- [ ] Screenshots match expected layout
- [ ] Conversation visible in Conversations page
