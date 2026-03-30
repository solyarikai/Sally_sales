# CRITICAL ARCHITECTURE FIX — MCP Must Be Fully Independent

## The Problem

MCP currently proxies `/api/replies/` to the main backend (172.17.0.1:8000).
This violates the core requirement: **MCP must be fully independent.**
The main backend will be killed. MCP cannot depend on it.

## What Must Change

### 1. Remove nginx proxy to main backend
- Delete `/api/replies/` proxy from `mcp/frontend/nginx.conf`
- Delete `/api/contacts/projects/` proxy from `mcp/frontend/nginx.conf`
- MCP must serve ALL data from its OWN database

### 2. MCP must own reply processing
Reuse the SAME CODE from the main backend but run it in MCP:
- SmartLead webhook receiver → `POST /api/smartlead/webhook`
- SmartLead polling (sync) → background task
- Reply classification (GPT-4o-mini) → same prompt as main app
- Draft generation (Gemini 2.5 Pro) → same logic
- Thread caching → same pattern
- Store in MCP's own `ProcessedReply` table (create if not exists)

### 3. MCP must own reply UI data
- `/api/replies/` served from MCP's own DB
- Tasks page reads from MCP's own replies
- No proxy, no dependency on main backend

### 4. Campaign reply tracking (listen/unlisten)
- Each campaign has a `tracking_enabled` boolean
- MCP-created campaigns: tracking ON by default
- Imported campaigns: tracking OFF by default
- User can toggle via MCP tool: `enable_reply_tracking`
- Campaigns page shows tracking status indicator

### 5. Telegram notifications for replies
- Reuse same notification format as main app
- User connects Telegram bot token in Project settings
- New replies → Telegram message with link to Replies page

### 6. Code reuse strategy
- COPY reply processing code from main backend (don't import at runtime)
- Same classification prompt, same draft generation logic
- Different DB, different tables, independent deployment
- When fixing a bug: fix in both places (or extract to shared package later)

## Migration Plan

1. Create `ProcessedReply` model in MCP DB (migration)
2. Copy `reply_processor.py` core functions to MCP backend
3. Add SmartLead webhook endpoint to MCP
4. Add polling scheduler for reply sync
5. Implement `/api/replies/` in MCP backend (replace stub)
6. Remove nginx proxy rules
7. Add campaign tracking toggle
8. Add Telegram notification support
9. Test with real SmartLead campaign replies

## Timeline Estimate
This is a significant change — needs a dedicated session to implement properly.
