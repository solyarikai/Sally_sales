# MCP LeadGen — Getting Started

## 1. Sign up

Go to http://46.62.210.24:3000 and create an account.

## 2. Connect API keys

At http://46.62.210.24:3000/setup connect:

| Service | Key | What for |
|---------|-----|----------|
| **Apollo** | `9yIx2mZegixXHeDf6mWVqA` | Company & people search |
| **OpenAI** | `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` | AI analysis |
| **SmartLead** | `eaa086b6-b7c0-4b2f-a6e9-b183c81122d5_638f7e5` | Email campaigns |
| **Apify** | `apify_proxy_zZ12PNY7illL44MXT8Cf3vKetkI5I62Oupn2` | Website scraping |

## 3. Copy your MCP token

On the Setup page, click **Show** then **Copy** next to your token.

## 4. Add MCP server

Paste your token into `.mcp.json` in this directory (replace `<PASTE_YOUR_MCP_TOKEN_HERE>`).

Or via CLI:
```bash
claude mcp add leadgen --transport sse "http://46.62.210.24:8002/mcp/sse?token=YOUR_TOKEN"
```

## 5. Start

```bash
cd ~/Desktop/mcp_test
claude
```

Say what you need:
```
Find IT consulting companies in Miami
```

MCP handles everything — no manual steps needed.

---

## What to expect

```
You: "Find IT consulting companies in Miami"
MCP: Shows Apollo filters + cost estimate → asks to confirm
You: "yes"
MCP: Gathers → scrapes → classifies → extracts contacts → creates campaign
```

Everything visible at http://46.62.210.24:3000

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| "MCP server failed" | Restart Claude Code |
| "Offer not confirmed" | Confirm your product description first |
| Empty pipeline page | Select project in top-left dropdown |
