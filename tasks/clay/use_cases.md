# Clay Integration — Use Cases & Architecture

## Overview

Clay.com automation via Puppeteer stealth browser. Session-based auth (no API key for search).
Clay API key (`f301ebf87260c1ea6686`) is only for webhook/table enrichment — NOT for company search.

**Key constraint**: Clay search is UI-only. No public API for company/people search.
Our approach: Puppeteer stealth → automate the UI → read results via internal API.

**Credits**: 0 spent on company search + table creation. Credits only used for enrichments (which we skip).

---

## Use Case 1: Find Companies by ICP Filter

**Flow**: ICP text → GPT maps to Clay filters → Puppeteer applies filters → creates table → reads via API → exports to Google Sheets

**Steps**:
1. GPT-4o-mini maps ICP description to Clay filter params (industries, keywords, size, geo, etc.)
2. Puppeteer opens Clay "Find leads" → "Companies" tab
3. Applies each filter (industries, description keywords, size, location, etc.)
4. Clicks Continue → "Save to new workbook and table"
5. Skips enrichments → clicks "Create table"
6. Reads all records via Clay internal API (`/v3/tables/{id}/bulk-fetch-records`)
7. Exports to Google Sheets on Shared Drive

**Output**: Google Sheet with columns: Name, Domain, Description, Industry, Size, Type, Location, Country, LinkedIn URL

**Limitations**:
- Max ~5000 per search. For larger TAMs, use geo-split strategy (7 regional batches)
- Session cookie expires ~weekly, auto-refresh prompts for re-login

**Script**: `node clay_tam_export.js "ICP description"`

**Cost**: 0 credits

---

## Use Case 2: Find People by Company List Upload

**Flow**: Upload CSV of domains/companies → Clay enriches with contacts → export

**Status**: NOT YET IMPLEMENTED

**Planned approach**:
1. Create Clay table via API (webhook push or CSV upload)
2. Push company domains to table
3. Add "Find people at company" enrichment column
4. Read enriched contacts via API

**Script**: Would use `clay_service.push_domains_to_table()` (webhook approach, already implemented)

**Cost**: 1 credit per person found (Clay enrichment)

---

## Use Case 3: Find People Directly from Search

**Flow**: ICP text → Clay "Find leads" → "People" tab → filter → export contacts directly

**Status**: INVESTIGATION NEEDED

**How it would work**:
1. Same as Use Case 1, but click "People" tab instead of "Companies"
2. Clay's People search filters: job titles, seniority, department, company filters (industry, size)
3. Results include: Name, Title, Company, LinkedIn URL
4. Emails require enrichment (costs credits)

**Key difference from Use Case 1+2 combined**:
- Skips the intermediate company table step
- Gets people directly matching job title + company criteria
- Useful when you know the persona (e.g., "CFOs at gaming companies")

**Trade-offs**:
- Fewer company-level filters available in People search vs Company search
- No company description keyword filtering in People tab
- Better for broad title-based searches, worse for niche ICP filtering

**Recommendation**:
- Use Case 1 (Companies) for niche ICPs with description keywords (e.g., "skin trading")
- Use Case 3 (People direct) for title-based searches at known industry/size segments

---

## Session Management

**File**: `scripts/clay/clay_session.json`
- Stores session cookie persistently
- Auto-validates on each run
- If expired: opens browser for manual re-login, polls until authenticated
- Saves refreshed cookie for future runs

**Commands**:
- `node clay_tam_export.js --login-only` — refresh session without running export
- `node clay_tam_export.js --test` — test run with gaming ICP (max 5 results)
- `node clay_tam_export.js --auto "ICP text"` — headless mode, closes browser after

---

## Architecture

```
Chat UI → POST /search/chat
  → GPT parses intent → action: "clay_export"
  → _handle_clay_export():
    1. Maps ICP to filters (GPT-4o-mini)
    2. Returns immediate response with filter summary
    3. Starts background task:
       a. Runs Node.js Puppeteer script (clay_tam_export.js)
       b. Reads results from exports/tam_companies.json
       c. Exports to Google Sheets (Shared Drive)
       d. Saves completion message to chat DB
    4. SSE pushes updates to frontend
```

**Files**:
- `scripts/clay/clay_tam_export.js` — Puppeteer automation (686 lines)
- `backend/app/services/clay_service.py` — Python service layer
- `backend/app/api/search_chat.py` — Chat handler (`_handle_clay_export`)
- `frontend/src/components/chat/ChatMessage.tsx` — UI (loading spinner, Sheet link button)

---

## Clay Internal API Endpoints (discovered)

All require session cookie (`claysession`) on `api.clay.com`:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/v3/subscriptions/{workspaceId}` | GET | Credit balances |
| `/v3/tables/{tableId}` | GET | Table metadata + field ID→name map |
| `/v3/tables/{tableId}/count` | GET | Record count |
| `/v3/tables/{tableId}/views/{viewId}/records/ids` | GET | All record IDs |
| `/v3/tables/{tableId}/bulk-fetch-records` | POST | Fetch records by IDs (200/batch) |
