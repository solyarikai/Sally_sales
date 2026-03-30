# Telegram Bot → MCP — Architecture

## How it works

```
┌──────────┐    ┌─────────────────┐    ┌──────────────┐
│ Telegram  │───▶│  AI Router      │───▶│  MCP Server  │
│ User      │◀───│  (GPT-4o-mini)  │◀───│  :8002       │
└──────────┘    └─────────────────┘    └──────────────┘
                       │
                  ┌────┴────┐
                  │  Redis  │ (session state)
                  └─────────┘
```

1. User sends message to Telegram bot
2. Bot loads user's session (MCP token, active project, conversation history)
3. Bot sends message + 30 tool definitions to OpenAI function calling API
4. GPT-4o-mini returns a `tool_call` (or plain text if no tool needed)
5. Bot sends the tool call to MCP server via HTTP POST to `/mcp/messages`
6. MCP returns result
7. Bot sends GPT-4o-mini the result → GPT formats a human response
8. Bot sends response to Telegram

## Model choice

| Model | Cost per 1K interactions | Tool routing quality | Multi-step context |
|-------|------------------------|---------------------|--------------------|
| **GPT-4o-mini** | ~$0.50 | Good (90%+ accuracy on clear intents) | Needs session state help |
| GPT-4o | ~$5.00 | Excellent | Excellent |
| Claude Haiku | ~$1.00 | Good | Good |
| Claude Sonnet | ~$8.00 | Excellent | Excellent |

**Recommendation: GPT-4o-mini** for 90% of interactions. It handles:
- "Find IT companies in US" → `tam_gather` ✓
- "What's my pipeline status?" → `pipeline_status` ✓
- "Connect my SmartLead" → `configure_integration` ✓
- "Approve the checkpoint" → `tam_approve_checkpoint` ✓

Where it struggles (fallback to GPT-4o):
- Complex multi-turn flows where context from 5+ messages ago matters
- Ambiguous requests that need reasoning about which of 30 tools to use
- Situations where multiple tools must be chained

**Solution**: Use GPT-4o-mini always, but include session state (last 5 tool calls + current pipeline phase) in the system prompt. This gives it the context it needs without upgrading the model.

## Session State (Redis)

```json
{
  "telegram_user_id": 12345,
  "mcp_token": "mcp_abc...",
  "active_project_id": 1,
  "active_project_name": "EasyStaff Global - US IT",
  "active_run_id": 8,
  "current_phase": "awaiting_targets_ok",
  "pending_gate_id": 15,
  "last_tool_calls": [
    {"tool": "tam_gather", "result_summary": "50 companies found"},
    {"tool": "tam_blacklist_check", "result_summary": "CP1 created, gate #15"}
  ],
  "conversation_history": [
    {"role": "user", "content": "Find IT companies in US, 50-200"},
    {"role": "assistant", "content": "Found 50 companies. Review scope?"},
    {"role": "user", "content": "Approve"}
  ]
}
```

This session state is injected into GPT's system prompt so it knows where the user is in the flow.

## System Prompt for GPT-4o-mini

```
You are a lead generation assistant. You help users find companies and create campaigns.

Current state:
- User: {name} (token: {mcp_token})
- Project: {active_project_name} (ID: {active_project_id})
- Pipeline: Run #{active_run_id}, phase: {current_phase}
- Pending approval: Gate #{pending_gate_id}

Use the provided tools to execute user requests. Never make up data.
If the user says "approve" or "yes", call tam_approve_checkpoint with the pending gate.
Always share the pipeline link after tool calls: http://46.62.210.24:3000/pipeline/{run_id}
```

## Cost estimate

- Average interaction: ~800 tokens input (system + tools + message), ~200 tokens output
- GPT-4o-mini: $0.15/M input + $0.60/M output
- Per interaction: ~$0.0003 (0.03 cents)
- 1000 interactions/day: ~$0.30/day
- 10 users × 50 interactions/day: ~$1.50/month

Essentially free.

## What needs to be built

| Component | Technology | Effort |
|-----------|-----------|--------|
| Telegram bot | Python `aiogram` v3 | 200 lines |
| OpenAI function calling | `openai` Python SDK | 100 lines |
| MCP HTTP client | `httpx` (call /mcp/messages) | 50 lines |
| Session manager | Redis | 80 lines |
| Deployment | Docker container in mcp-network | Dockerfile + compose |

Total: ~500 lines of Python. One file. One container.

## Files

```
mcp/telegram/
├── bot.py          # Main bot: Telegram + OpenAI + MCP client
├── Dockerfile
├── requirements.txt
└── .env            # TELEGRAM_BOT_TOKEN, OPENAI_API_KEY
```
