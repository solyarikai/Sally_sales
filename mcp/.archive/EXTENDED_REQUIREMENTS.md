# MCP System — Extended Requirements

## MCP UI Pages (Final List)

The MCP frontend has **6 pages only**. No bloat, no unused pages. Each page serves one purpose.

| # | Page | Route | Purpose |
|---|------|-------|---------|
| 1 | **Setup** | `/setup` | Account creation, token login, API key connections |
| 2 | **Pipeline** | `/pipeline/:runId` | Live pipeline progress — phase stepper, SSE updates, checkpoint approvals |
| 3 | **Targets** | `/pipeline/:runId/targets` | Target company review table — sortable, approve/reject, export |
| 4 | **Replies** | `/replies` | Task queue — reply cards with AI drafts, approve/dismiss/regenerate, category tabs |
| 5 | **Projects** | `/projects` | Project list + project detail (ICP, sender, campaigns, knowledge) |
| 6 | **Learning** | `/projects/:id/learning` | Operator correction history — what the AI suggested vs what the operator changed, patterns learned |

### Pages NOT included (moved to main product only)
- Analytics/monitoring dashboard
- CRM contact management
- Campaign list/detail
- GTM strategy pages
- Telegram DM management
- Godpanel

### Page Details

#### 1. Setup (`/setup`)
- New account → email + name → get API token
- Existing account → paste token to login
- Connect integrations: SmartLead, Apollo, FindyMail, OpenAI, Gemini
- Shows connection status (green/red) with info (e.g. "47 campaigns found")

#### 2. Pipeline (`/pipeline/:runId`)
- Vertical phase stepper: gather → blacklist → CP1 → filter → scrape → analyze → CP2 → verify → CP3 → complete
- SSE-powered real-time progress (scrape X/Y, analyze X/Y)
- Checkpoint panels: show scope, ask for approval
- Filter summary: what keywords, locations, size ranges were applied
- Credit tracker: estimated vs actual credits used

#### 3. Targets (`/pipeline/:runId/targets`)
- Sortable table: domain, company, confidence, segment, reasoning, employee count, country
- Bulk approve/reject checkboxes
- Borderline filter (0.4-0.6 confidence) for manual review
- Export to CSV
- Refinement history panel (if auto_refine was used): iteration accuracy chart

#### 4. Replies (`/replies`)
- Same UX as main product replies — category tabs (All, Meetings, Interested, Questions, etc.)
- Reply card: lead info, message, AI draft, approve/dismiss/regenerate buttons
- Conversation thread view
- Deep link support (`?lead=email&project=name`)
- Follow-up drafts tab

#### 5. Projects (`/projects`)
- Project list with key metrics (contacts, campaigns, target rate)
- Project detail: ICP definition, sender identity, connected campaigns
- Knowledge tab: ICP, outreach templates, examples
- Campaign list for this project

#### 6. Learning (`/projects/:id/learning`)
- Operator correction log: what the AI drafted vs what the operator actually sent
- Pattern extraction: "Operator always shortens the pricing section" → learned pattern
- Quality metrics: approve rate, edit rate, regenerate rate over time
- Reference examples: golden examples with quality scores

---

## Shared Code Strategy

See `SHARED_CODE_STRATEGY.md` for full architecture.

**Summary**: `shared/` directory contains models, services, and UI components used by BOTH the main product and MCP system. Fix once → fixed everywhere. Separate databases, shared logic.

---

## Operator Interaction Tracking

Every interaction between an operator and the MCP system MUST be logged for:
1. Training data collection — improve AI prompts based on real operator patterns
2. Usage analytics — who uses what, how often, where they get stuck
3. Billing (future) — charge based on tool calls / pipeline runs

### What gets logged

| Field | Description |
|-------|-------------|
| `user_id` | Which operator |
| `session_id` | MCP session (groups related calls) |
| `tool_name` | Which MCP tool was called |
| `tool_arguments` | What the operator/AI requested (JSONB) |
| `tool_result` | What the system returned (JSONB, truncated to 10KB) |
| `latency_ms` | How long the tool call took |
| `created_at` | Timestamp |

### Implementation

The MCP dispatcher wraps every tool call with logging:

```python
async def dispatch_tool(tool_name, args, token, request):
    start = time.monotonic()
    try:
        result = await _dispatch(tool_name, args, token, session)
        latency = int((time.monotonic() - start) * 1000)
        # Log success
        session.add(MCPUsageLog(
            user_id=user.id, action="tool_call",
            tool_name=tool_name,
            extra_data={"args": args, "result_preview": str(result)[:10000], "latency_ms": latency},
        ))
        return result
    except Exception as e:
        # Log failure
        session.add(MCPUsageLog(
            user_id=user.id, action="tool_error",
            tool_name=tool_name,
            extra_data={"args": args, "error": str(e)},
        ))
        raise
```

---

## Pipeline Test Scenario: EasyStaff Global — US IT Companies

### Filters (from Global Growth Strategy doc)

```json
{
  "source_type": "apollo.companies.api",
  "filters": {
    "q_organization_keyword_tags": ["IT services", "software consulting", "technology staffing"],
    "organization_locations": ["United States"],
    "organization_num_employees_ranges": ["51,200", "201,500"],
    "max_pages": 4,
    "per_page": 25
  }
}
```

### Expected flow

1. `tam_gather` → ~100 companies gathered
2. `tam_blacklist_check` → CP1: review scope
3. `tam_approve_checkpoint` → approve
4. `tam_pre_filter` → remove trash domains
5. `tam_scrape` → scrape websites
6. `tam_analyze` with prompt: "Target: US-based IT services / consulting companies, 50-500 employees, that likely hire remote contractors or freelancers internationally. Look for signals: offshore development, nearshore teams, global workforce, distributed engineering. Exclude: pure product companies with no services arm, local-only MSPs, hardware companies."
7. Self-refinement until 90% accuracy
8. `tam_approve_checkpoint` → CP2: review targets
9. `tam_prepare_verification` → CP3: cost estimate
10. `god_generate_sequence` → 5-step sequence using EasyStaff knowledge:
    - Sender: Marina Mikhaylova, easystaff.io
    - Angle: payroll/contractor management for international remote teams
    - Proof: companies like [prospect] save 30-40% on contractor payments
11. `god_approve_sequence` → approve
12. `god_push_to_smartlead` → DRAFT campaign

---

## Authentication Flow for New Users

### Via MCP Client (Claude Desktop / Claude Code)

1. User connects MCP client to `http://46.62.210.24:8002/mcp/sse`
2. User says: "Hello" or "Set up my account"
3. AI calls `setup_account` → user gets API token
4. AI tells user to save the token
5. For subsequent sessions, user's MCP client sends token via `Authorization: Bearer`

### Via Web UI

1. User opens `http://46.62.210.24:3000`
2. Sees "New Account" / "I Have a Token" buttons
3. New: enters email + name → gets token → auto-logged in
4. Existing: pastes token → verified → logged in
5. Connects integrations via the UI form

### Via Claude Code CLI

```bash
# Add MCP server
claude mcp add leadgen --transport sse --url http://46.62.210.24:8002/mcp/sse

# First conversation
> "Set up my account as Marina, marina@easystaff.io"
# AI calls setup_account, returns token
# User saves token for future sessions
```

---

## Password Authentication (Future)

Current auth is API token only (no password). Future: add password auth for the web UI:
- `POST /api/auth/login {email, password}` → returns API token
- Password stored as bcrypt hash in `mcp_users.password_hash`
- Web UI stores token in localStorage after login
- MCP clients continue using token auth (no change)
