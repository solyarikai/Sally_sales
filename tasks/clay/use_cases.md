# Clay Integration — How to Clay

## Golden Rule

**NEVER use Clay API directly (curl, httpx, etc.) for search or data retrieval.**
**ALWAYS use Clay UI via Puppeteer stealth browser for ALL actions.**

The only exception: reading table data AFTER a table is created via the UI (because Clay's virtual grid DOM can't be scraped — must use internal API endpoints from within the browser context via `page.evaluate()`).

---

## Overview

Clay.com automation via Puppeteer stealth browser. Session-based auth (cookie).
- Clay API key (`f301ebf87260c1ea6686`) is ONLY for webhook/table enrichment — NOT for search
- Company search and people search are **UI-only** features
- Table creation via "Save to new workbook and table" is free (0 credits)
- Enrichments (emails, phone numbers) cost credits — we SKIP them
- Session cookie expires ~weekly → auto-refresh via browser re-login

---

## What is the Inxy Gaming ICP

**Inxy** sells crypto payment gateway for gaming digital goods.

**Target companies** (ICP = Ideal Customer Profile):
- Companies that **sell** gaming skins, virtual items, loot boxes, cases, keys, coins, gift cards
- **Games**: CS2, CSGO, Dota2, Roblox, WoW, FIFA, Rust, TF2, Fortnite, Valorant, PUBG, Minecraft, Path of Exile, League of Legends
- **Company types**: Skin marketplaces, gambling/betting sites (skin-based), trading platforms, case/box opening sites, top-up services, boosting services, account shops
- **Allowed geos**: Low risk only (AU, AT, BE, CA, DK, EE, FI, FR, DE, IS, IE, JP, LI, NZ, NO, SE, CH, AD, SM). NO UK, NO US

**NOT ICP**: Game developers, esports teams, gaming hardware, game studios, blockchain/DeFi protocols, fintech companies, investment funds, legal/migration services

**Ground truth**: Team's 87 companies in `tasks/inxy/skin_sites_all.xlsx`

### All Data Sources for Inxy Gaming ICP

| Source | Count | File/Location | ICP Quality | Description |
|--------|-------|---------------|-------------|-------------|
| Team's xlsx | 87 | `tasks/inxy/skin_sites_all.xlsx` | Highest (manual) | Manually curated by team |
| Data pipeline (Yandex + Google) | 308 | `scripts/clay/inxy_gaming_companies.csv` | High (filtered) | Found by Yandex/Google search, filtered via `inxy_clean_export.py` to remove non-gaming |
| Clay TAM (Find Companies) | 871 (721 with domain) | `scripts/clay/exports/tam_companies.json` | Medium (has noise) | Clay company search with gaming filters — includes some non-ICP companies |

**Important**: Project 48 in the DB contains targets from multiple approaches (Yandex, Google SERP, Apollo org search). Apollo broad search contaminated results with fintech/crypto/legal companies. The pipeline CSV (`inxy_gaming_companies.csv`) has already been filtered to include ONLY actual gaming-item-selling companies. The Clay TAM has noise and should be cross-checked.

When building the people list, priority order for matching is:
1. Team xlsx domains (100% ICP)
2. Pipeline CSV domains (verified gaming ICP)
3. Clay TAM domains (need post-filtering — some are gaming companies but not selling items)

**DB query** for pipeline targets (Hetzner):
```sql
SELECT dc.domain, dc.name, dc.confidence, dc.matched_segment
FROM discovered_companies dc
WHERE dc.project_id = 48 AND dc.is_target = true
ORDER BY dc.confidence DESC;
```

**Export script** (runs on Hetzner): `scripts/inxy_clean_export.py` — filters out non-gaming contamination from Apollo broad search results using keyword matching.

---

## Use Case 1: Find Companies by ICP Filter (TAM)

**Purpose**: Discover total addressable market — all companies matching ICP filters.

**Flow**: ICP text → GPT maps to Clay filters → Puppeteer applies filters in UI → creates table → reads data → exports to Google Sheets

**Steps**:
1. GPT-4o-mini maps ICP description to Clay filter params (industries, keywords, size, geo)
2. Puppeteer opens Clay "Find leads" → "Companies" tab
3. Types each filter value into the UI inputs (with human-like delays)
4. Clicks Continue dropdown → "Save to new workbook and table"
5. On "Enrich Companies" page: skips all enrichments → clicks "Create table"
6. Waits for table to load, reads all records from within browser context using Clay internal API
7. Exports to Google Sheets on Shared Drive

**Output**: Google Sheet with: Name, Domain, Description, Industry, Size, Type, Location, Country, LinkedIn URL

**Limitations**:
- Max ~5000 per search. For larger TAMs → geo-split strategy (7 regional batches)
- Filter inputs match by Clay's taxonomy — keywords must match what's in Clay's DB
- Some results won't match ICP (Clay's filtering is broad) — post-filtering needed

**Script**: `node scripts/clay/clay_tam_export.js "ICP description"`

**Cost**: 0 credits

---

## Use Case 2: Find People Directly from Search

**Purpose**: Find decision-makers at gaming companies without an intermediate company table.

**Flow**: Puppeteer → Clay "Find leads" → "People" tab → apply company+title filters → create table → read people data

**Steps**:
1. Puppeteer opens Clay "Find leads" → clicks "People" tab
2. Applies filters:
   - Company industries: Online gaming, Computer games, E-commerce
   - Company description keywords: skins, CS2, CSGO, Dota2, gaming marketplace, virtual items, etc.
   - Job titles: CEO, Founder, CTO, CFO, VP, Director, Head of, etc.
3. Clicks Continue → "Save to new workbook and table"
4. Skips enrichments → "Create table"
5. Reads all people records from table
6. Cross-matches against known ICP domains (xlsx + pipeline + Clay TAM)
7. Exports to Google Sheets: matched people (at known companies) + unmatched (new discoveries)

**Output**: Name, Title, Company, Domain, LinkedIn URL, Location

**People search returns**: up to 5000 people per search, 0 credits for the search itself

**Why this is better than Companies → then People**:
- Single step instead of two
- Gets people directly with their titles and LinkedIn URLs
- Can filter by job title/seniority (not available in company search)

**When to use Companies (UC1) instead**:
- When you need company-level data (industry, size, revenue, description)
- When ICP requires niche description keywords that people search doesn't support well

**Script**: `node scripts/clay/clay_find_people.js`

**Cost**: 0 credits (search + table creation). Emails would cost credits (we don't enrich).

---

## Use Case 3: Find People by Company List Upload

**Purpose**: Get contacts at SPECIFIC known companies (from xlsx, pipeline, or Clay TAM).

**Flow**: Upload CSV of domains → Clay creates table → add "Find People" enrichment → read results

**Status**: NOT YET IMPLEMENTED (Puppeteer automation needed for upload flow)

**Planned approach**:
1. Prepare CSV with all known ICP domains (757 merged domains)
2. Puppeteer: Import data → upload CSV → map columns → create table
3. Add "Find People at Company" enrichment column
4. Read enriched results

**Cost**: 1 credit per person found (Clay enrichment) — this COSTS credits unlike UC1/UC2

**When to use**: When you need people at SPECIFIC companies (not just any gaming companies)

---

## Session Management

**File**: `scripts/clay/clay_session.json` (auto-created on first successful run)

**How it works**:
1. On startup: loads cookie from file (or falls back to hardcoded default)
2. Navigates to Clay home, calls `/v3/subscriptions/889252` to validate
3. If 401/403: opens Clay login page, waits for manual login (polls every 3s, up to 5min)
4. On successful auth: saves new cookie to file
5. At end of each run: saves latest cookie (keeps it fresh)

**Commands**:
```bash
cd scripts/clay

# Refresh session only (no export)
node clay_tam_export.js --login-only

# Test run (gaming ICP, max 5 results)
node clay_tam_export.js --test

# Full export with auto-close
node clay_tam_export.js --auto "Companies selling gaming skins for CS2, Dota2, Roblox"

# People search
node clay_find_people.js
node clay_find_people.js --auto
```

---

## Architecture

```
Operator in Chat UI
  → POST /search/chat with message like "export TAM from Clay for gaming skins"
  → GPT parses intent → action: "clay_export"
  → _handle_clay_export():
    1. GPT-4o-mini maps ICP to Clay filter params (immediate)
    2. Returns response with filter summary + loading state
    3. Background task:
       a. Writes filters to exports/filters_input.json
       b. Runs `node clay_tam_export.js` as subprocess
       c. Reads exports/tam_companies.json
       d. Exports to Google Sheets (Shared Drive, with debug tab)
       e. Saves completion message with sheet URL to chat DB
    4. SSE pushes update to frontend → user sees Google Sheet link
```

**Files**:
| File | Purpose |
|------|---------|
| `scripts/clay/clay_tam_export.js` | Puppeteer: company search + table creation |
| `scripts/clay/clay_find_people.js` | Puppeteer: people search + table creation |
| `scripts/clay/clay_session.json` | Persistent session cookie |
| `scripts/clay/exports/` | Output JSONs + screenshots |
| `scripts/clay_people_export.py` | Cross-match people with known domains |
| `scripts/clay_export_sheet.py` | Standalone Google Sheets export |
| `backend/app/services/clay_service.py` | Python service: TAM export + Sheets |
| `backend/app/api/search_chat.py` | Chat handler: `_handle_clay_export()` |
| `frontend/src/components/chat/ChatMessage.tsx` | UI: loading spinner + Sheet link |

---

## Clay Internal API (for reading table data only)

These are called from WITHIN the Puppeteer browser context via `page.evaluate()`.
**Never call them directly via curl/httpx.**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/v3/subscriptions/{workspaceId}` | GET | Credit balances (validation) |
| `/v3/tables/{tableId}` | GET | Table metadata + field ID→name map |
| `/v3/tables/{tableId}/count` | GET | Record count |
| `/v3/tables/{tableId}/views/{viewId}/records/ids` | GET | All record IDs in view |
| `/v3/tables/{tableId}/bulk-fetch-records` | POST | Fetch records by ID array (200/batch) |

---

## Important Constraints

1. **Clay search = UI only** — no public API, must use Puppeteer
2. **Preview endpoint (run-enrichment) is limited to 50 results** — for full results, MUST create a table via UI
3. **Offset/pagination doesn't work** on preview endpoint — always returns same 50
4. **Credits**: search + table creation = free. Enrichments (emails/phones) = paid
5. **Session expires ~weekly** — auto-refresh handles this
6. **Continue button has a dropdown** — must click the right-side arrow to reveal "Save to new workbook and table" option
7. **Table records are keyed by field IDs** (like `f_0tbi6fcdinveGvsgFrn`) — must fetch table metadata first to map field IDs → human-readable names
8. **peopleSearchLimit = 5000** per search on current plan
