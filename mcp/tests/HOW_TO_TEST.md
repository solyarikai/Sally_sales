# How to Test MCP

## ABSOLUTE RULES

1. **NEVER SSH into Hetzner to run tests.** Tests run FROM YOUR LOCAL MACHINE.
2. **NEVER `docker exec leadgen-backend`** or touch main app containers.
3. **NEVER SCP test files to Hetzner.**
4. Tests connect TO the MCP server at `http://46.62.210.24:8002/mcp/sse` FROM HERE.

---

## The ONLY Valid Test: Real Conversation via MCP SSE

A real Claude agent connects to MCP, receives natural language prompts, and DECIDES which tools to call. This tests the complete chain: user intent → agent reasoning → tool selection → MCP execution → response.

### How to Run: 2 Parallel Agents, 1 Per Test User

```bash
# 1. Ensure MCP server is configured for Claude Code
claude mcp add --transport sse magnum-opus-test http://46.62.210.24:8002/mcp/sse

# 2. Launch Agent 1 (pn@getsally.io) — full conversation test
echo 'You are testing the GTM MCP system as user pn@getsally.io.
Login with token: {TOKEN}. Then:
1. Call get_context to see your state
2. Create project EasyStaff-Global with website easystaff.io
3. Import SmartLead campaigns matching "petr"
4. Find IT consulting companies in Miami (10 targets)
5. Approve all checkpoints
6. List email accounts, use eleonora accounts
7. Generate sequence, approve, push to SmartLead (DRAFT only!)
8. Check reply summary
9. Verify session continuity with get_context
Report every tool call result.' | claude --print

# 3. Launch Agent 2 (services@getsally.io) — in parallel
echo 'You are testing the GTM MCP system as user services@getsally.io.
Login with token: {TOKEN}. Then:
1. Create project Result targeting LATAM fashion brands
2. Gather from CSV: /path/to/test_csv_source.csv
3. MCP should ask "new or existing pipeline?" — say "add to existing"
4. Gather from Google Sheet
5. Gather from Google Drive folder
6. Verify dedup: 110+70+35=215 unique companies
7. Create second project OnSocial UK
8. Switch between projects, verify data isolation
Report every tool call result.' | claude --print
```

### Why This Works

- `claude --print` starts a FRESH Claude Code session with MCP servers loaded
- The agent receives the prompt and DECIDES which MCP tools to call
- It's a real conversation — the agent reasons about each step
- Tool calls go through real SSE JSON-RPC 2.0 protocol
- Results are real, not mocked

### Why Other Approaches DON'T Work

| Approach | Problem |
|---|---|
| `test_real_mcp.py` (calling tools directly) | No agent decision-making. Just tool calls, not a conversation. |
| Subagents from existing session | MCP servers loaded at session init. Subagents don't inherit them. |
| SSH to Hetzner + run tests | Wrong machine. Touches main app. |
| REST `/tool-call` endpoint | Not real MCP protocol. No SSE, no JSON-RPC. |

### Automating It

The `tests/conversations/*.json` files define WHAT to test. The test runner builds prompts from them and pipes into `claude --print`:

```bash
# Full automated run (both users in parallel)
cd mcp && python3 tests/run_real_conversation_tests.py
```

This script:
1. Reads conversation JSON files grouped by user
2. Builds natural language prompts from the steps
3. Launches 2 `claude --print` processes in parallel (one per user)
4. Captures output, parses tool call results
5. Scores against expected behavior
6. Reports pass/fail

---

## State of the Art: How MCP Servers Are Tested (2026)

Based on research of industry practices, official docs, and real-world frameworks.

### What the industry actually does (not hallucinated)

**3 things must be tested** (per [Stainless](https://www.stainless.com/mcp/how-to-test-mcp-servers), [Merge](https://www.merge.dev/blog/mcp-server-testing)):

1. **Technical correctness** — does the server expose right tools, validate params, return valid responses?
2. **Behavioral correctness** — does an AI agent PICK the right tool for a given user prompt?
3. **UI correctness** — does the UI reflect the state after tool calls?

**Key metrics** (per [Merge's 6 best practices](https://www.merge.dev/blog/mcp-server-testing)):
- **Hit rate** = how often the agent calls the RIGHT tool for a prompt. Measures tool descriptions quality.
- **Success rate** = how often tool calls succeed. Measures auth, params, error handling.
- **Unnecessary calls** = extra calls that waste tokens/time. Measures prompt+tool design quality.

### Real tools that exist and work

| Tool | What it does | Reliable? |
|---|---|---|
| **[MCP Inspector](https://modelcontextprotocol.io/docs/tools/inspector)** | GUI to list tools, call them manually, see JSON-RPC logs | YES — official Anthropic tool |
| **[mcp-server-tester](https://github.com/r-huijts/mcp-server-tester)** | Config-driven: discovers tools, generates test cases via Claude, validates responses | YES — npm package |
| **[mcp Python SDK](https://github.com/modelcontextprotocol/python-sdk)** `call_tool()` | Programmatic tool calling via real SSE | YES — official SDK |
| **[Playwright MCP](https://github.com/microsoft/playwright-mcp)** | Browser automation + screenshots via MCP | YES — Microsoft official |
| **`claude --print`** | Pipe prompt → Claude reasons → calls MCP tools → outputs result | YES — built into Claude Code |

### What we use (3 layers, all proven)

#### Layer 1: Automated tool verification (CI/regression)
```bash
# MCP Python SDK — connects via SSE, calls tools, checks responses
pip install mcp httpx-sse
python3 tests/test_real_mcp.py
```
- Connects to `http://46.62.210.24:8002/mcp/sse` via real SSE
- Lists all tools, validates schemas
- Calls tools with known inputs, asserts outputs
- Measures success rate per tool
- Runs in CI, no human needed

#### Layer 2: Real conversation testing (behavioral)
```bash
# claude --print — real agent decides which tools to call
echo "Find IT consulting companies in Miami, 10 targets" | claude --print
```
- A real Claude agent receives natural language
- Agent DECIDES which MCP tools to call (tests hit rate)
- 2 parallel agents (1 per test user) run full conversation flows
- Prompts built from `tests/conversations/*.json` with shuffled variants
- Output captured, tool calls parsed, scored against expected behavior

#### Layer 3: UI screenshot verification
```bash
# Playwright — screenshots after MCP operations
npx playwright test tests/ui_verification.spec.ts
```
- After conversation tests complete, Playwright opens browser
- Screenshots pipeline page, CRM, campaigns, conversations
- Compares against expected state (companies visible, segments correct, etc.)

### Known Issues with Concurrent Sessions
When 2+ agents connect simultaneously:
- Token storage must be per-session (`contextvars.ContextVar`, not global dict)
- Active project must not drift between concurrent users
- Each SSE connection = independent session with own auth context

Sources:
- [How to Test MCP Servers — Stainless](https://www.stainless.com/mcp/how-to-test-mcp-servers)
- [6 Best Practices for MCP Testing — Merge](https://www.merge.dev/blog/mcp-server-testing)
- [MCP Inspector — Official](https://modelcontextprotocol.io/docs/tools/inspector)
- [MCP Python SDK — GitHub](https://github.com/modelcontextprotocol/python-sdk)
- [mcp-server-tester — GitHub](https://github.com/r-huijts/mcp-server-tester)
- [Playwright MCP — Microsoft](https://github.com/microsoft/playwright-mcp)
- [Claude Code Print Mode — Docs](https://code.claude.com/docs/en/cli-reference)
- [MCP Testing Framework — GitHub](https://github.com/haakco/mcp-testing-framework)

---

## Verify During Tests

Watch these pages IN A BROWSER while tests run:
1. `http://46.62.210.24:3000/conversations` — tool calls in real-time
2. `http://46.62.210.24:3000/pipeline` — pipeline runs
3. `http://46.62.210.24:3000/campaigns` — campaigns
4. `http://46.62.210.24:3000/crm` — contacts
