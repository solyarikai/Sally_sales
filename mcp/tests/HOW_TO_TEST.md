# How to Test MCP — Real World

## The Only Valid Test

Connect a REAL Claude agent to the MCP server via SSE and have a conversation.

### Option 1: Claude Code CLI
```bash
# Add MCP server to Claude Code config
claude mcp add magnum-opus http://46.62.210.24:8002/mcp/sse

# Start conversation
claude

# Then type as a real user:
> "My website is https://easystaff.io/. I'm Eleonora from EasyStaff."
> "Find IT consulting companies in Miami"
> "Use Eleonora's email accounts from the petr campaigns"
> "Which leads need follow-ups?"
```

### Option 2: Claude Desktop
Add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "magnum-opus": {
      "url": "http://46.62.210.24:8002/mcp/sse",
      "headers": {
        "X-MCP-Token": "your_token_here"
      }
    }
  }
}
```

### Option 3: Cursor IDE
Add MCP server in Cursor settings → MCP Servers

## What to Verify During Real Conversation

While the agent converses with MCP, watch these pages:

1. **http://46.62.210.24:3000/conversations** — every tool call appears in real-time
2. **http://46.62.210.46:3000/pipeline** — pipeline runs appear as gathering starts
3. **http://46.62.210.24:3000/campaigns** — campaigns appear when created
4. **http://46.62.210.24:3000/crm** — contacts appear after import

## Test Conversations

Load test files from `mcp/tests/conversations/*.json`. Each has:
- User prompts (with shuffled variants)
- Expected tool calls
- Expected MCP behavior
- UI verification points

## REST /tool-call Endpoint (Fallback)

When real agent testing isn't possible, use `POST /api/pipeline/tool-call`:
```bash
curl -X POST http://46.62.210.24:8002/api/pipeline/tool-call \
  -H "X-MCP-Token: your_token" \
  -H "Content-Type: application/json" \
  -d '{"tool_name": "create_project", "arguments": {...}}'
```

This uses the SAME backend logic and logs to conversations.
It does NOT test the agent's decision-making (which tools to call when).
