# MCP LeadGen — Connection Guide

Server URL: `http://46.62.210.24:8002/mcp/sse`

27 tools for lead gathering, campaign generation, and pipeline management. See `tools.md` for the full list.

---

## Claude Code (CLI)

```bash
claude mcp add leadgen --transport sse http://46.62.210.24:8002/mcp/sse
```

Then restart Claude Code. Verify:

```bash
claude mcp list
```

## Claude Desktop (Mac/Windows)

Edit the config file:

- **Mac**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "leadgen": {
      "url": "http://46.62.210.24:8002/mcp/sse"
    }
  }
}
```

Restart Claude Desktop. The toolbox icon should show 27 tools.

## Cursor

Settings → MCP Servers → Add Server:

- **Name**: `leadgen`
- **Type**: `sse`
- **URL**: `http://46.62.210.24:8002/mcp/sse`

## VS Code (Claude Code Extension)

Same as Claude Code CLI — the extension reads `~/.claude/settings.json`.

---

## CLAUDE.md for your project

Create a `CLAUDE.md` in your project directory so Claude Code automatically uses MCP tools:

```markdown
# LeadGen Operator

You are a lead generation assistant. Use the **leadgen** MCP tools for everything.
Never write code or scripts.

You can: set up accounts, manage projects, gather companies from Apollo,
run pipeline (blacklist, scrape, analyze), create campaigns, check status.

Rules:
- Always ask before gathering: keywords, locations, company size, max pages
- Always confirm project first
- Never skip checkpoints — ask user to approve
- Campaigns are always DRAFT
- Share UI links: http://46.62.210.24:3000/pipeline/{runId}
```

With this file, you just talk naturally:
- "Find IT companies in US, 50-200 employees" → calls `tam_gather`
- "What's my pipeline status?" → calls `pipeline_status`
- "Create a campaign" → calls `god_generate_sequence`

No need to mention "MCP" or tool names.

---

## First-Time Setup

Once connected, just talk:

1. **"Set up my account as Marina, marina@easystaff.io"**
   → Creates account, returns API token. Save it.

2. **"Connect SmartLead with key eaa086b6-..."**
   → Tests connection, shows "47 campaigns found"

3. **"Create a project for EasyStaff targeting US IT companies"**
   → Creates project with ICP

4. **"Find IT consulting companies in US, 50-200 employees, 4 pages"**
   → Runs pipeline, stops at checkpoints for your approval

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Tools not loading after `mcp add` | Restart Claude Code (`exit` then `claude`) |
| Tools still not loading | Check: `curl http://46.62.210.24:8002/mcp/sse` should return `event: endpoint` |
| "Invalid session" | Reconnect — SSE session expired |
| "Missing API token" | Say "set up my account" first |
| "Integration not connected" | Say "connect my SmartLead with key ..." |
| Connection refused | Server down — check `curl http://46.62.210.24:8002/api/health` |

## Running Locally

```bash
cd mcp
docker-compose -f docker-compose.mcp.yml up --build -d
```

Then use `http://localhost:8002/mcp/sse` instead of the Hetzner URL.
