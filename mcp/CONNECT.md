# MCP LeadGen — Connection Guide

Server URL: `http://46.62.210.24:8002/mcp/sse`

26 tools for lead gathering, campaign generation, and pipeline management. See `tools.md` for the full list.

---

## Claude Code (CLI)

```bash
claude mcp add leadgen --transport sse http://46.62.210.24:8002/mcp/sse
```

Or manually edit `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "leadgen": {
      "type": "sse",
      "url": "http://46.62.210.24:8002/mcp/sse"
    }
  }
}
```

Restart Claude Code. Verify with:

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

Restart Claude Desktop. The toolbox icon should show 26 tools.

## Cursor

Settings → MCP Servers → Add Server:

- **Name**: `leadgen`
- **Type**: `sse`
- **URL**: `http://46.62.210.24:8002/mcp/sse`

## VS Code (Claude Code Extension)

Same as Claude Code CLI — the extension reads `~/.claude/settings.json`.

---

## First-Time Setup

Once connected, run these in order:

### 1. Create your account

> "Set up my MCP account with email yourname@company.com and name Your Name"

This calls `setup_account` and returns an API token. **Save it** — it's shown once.

### 2. Connect your API keys

> "Connect my SmartLead with key eaa086b6-..."
> "Connect my Apollo with key ..."

This calls `configure_integration` for each service. It tests the connection automatically.

### 3. Create a project

> "Create a project called 'My Company - DACH SaaS' targeting Series A-B SaaS in Germany, 50-500 employees, sender Marina from easystaff.io"

### 4. Run the pipeline

> "Gather companies from Apollo for my DACH project — SaaS keywords, Germany, 50-200 employees, max 4 pages"

The pipeline stops at 3 mandatory checkpoints for your approval:
- **CP1**: Project scope + blacklist review
- **CP2**: Target list review (after AI analysis)
- **CP3**: FindyMail cost approval (before spending credits)

---

## Authentication

All tool calls (except `setup_account`) require your API token. The MCP client passes it automatically via the `Authorization: Bearer` header on the SSE connection.

If you need to pass it manually in tool arguments, use `_token`:

```json
{"name": "list_projects", "arguments": {"_token": "mcp_a1b2c3..."}}
```

## Running Locally

If you want to run the MCP server on your own machine:

```bash
cd mcp
docker-compose -f docker-compose.mcp.yml up --build -d
```

Then use `http://localhost:8002/mcp/sse` instead of the Hetzner URL.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| No tools showing | Check the URL ends with `/mcp/sse`, restart your client |
| "Invalid session" | Reconnect — SSE session may have timed out |
| "Missing API token" | Run `setup_account` first, then pass the token |
| "Integration not connected" | Run `configure_integration` with your API key |
| Connection refused | Verify server is running: `curl http://46.62.210.24:8002/api/health` |
