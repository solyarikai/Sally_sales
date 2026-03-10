# Inxy Gaming Shops — TAM Gathering Process

## Goal

Find all people (decision-makers) at companies that sell gaming skins, virtual items, loot boxes, cases, keys, coins — the Inxy ICP. Gather their names, titles, companies, LinkedIn URLs. Spend 0 Clay credits.

## Data Sources Used

### Source 1: Team's Manual List (87 companies)
- **File**: `tasks/inxy/skin_sites_all.xlsx`
- **What**: 87 companies manually curated by the team
- **Sheets**: "Все сайты (87)", "CS2 (68)", "Rust (12)", "Маркетплейсы (37)", "Мульти-игровые (29)", "Приоритет (19)"
- **Quality**: Highest — hand-picked, includes game type, company type, priority
- **Examples**: CSFloat, CSGO500, CSGOEmpire, DMarket, cs.money, Skinport

### Source 2: Data Pipeline — Yandex + Google Search (308 companies)
- **File**: `scripts/clay/inxy_gaming_companies.csv` (309 lines including header)
- **DB**: `discovered_companies` table, `project_id = 48`, `is_target = true`
- **How gathered**:
  1. GPT generated search queries for gaming skins ICP
  2. Yandex API + Google SERP (via Apify) ran queries
  3. Domains scraped via Crona API (JS-rendered scraping)
  4. GPT multi-criteria scoring (language, industry, service, company type, geography)
  5. Auto-review filtered results
  6. `inxy_clean_export.py` further filtered out non-gaming contamination (fintech, crypto, legal companies from Apollo broad search)
- **Quality**: High — automated discovery + GPT scoring + manual cleanup script
- **Note**: Apollo org search added ~140 contaminated domains (fintech/crypto/legal) that were removed by the cleanup script

### Source 3: Clay Find Companies (871 companies)
- **File**: `scripts/clay/exports/tam_companies.json`
- **How gathered**:
  1. GPT-4o-mini mapped ICP text to Clay search filters
  2. Puppeteer stealth browser opened Clay "Find leads" → "Companies" tab
  3. Applied filters: industries (Online gaming, Computer games, E-commerce), description keywords (skins, CS2, CSGO, Dota2, gaming marketplace, virtual items, loot boxes, skin trading)
  4. Clicked Continue → "Save to new workbook and table"
  5. Skipped enrichments → "Create table"
  6. Read 871 records via Clay internal API from browser context
  7. Exported to Google Sheet on Shared Drive
- **Quality**: Medium — Clay's filters are broad, includes non-gaming companies (game studios, esports orgs, gaming hardware)
- **721 of 871** have a domain field; rest have LinkedIn URL only

### Combined: 981 unique domains
- 86 from xlsx + 250 new from pipeline + 669 new from Clay TAM (after dedup)

## People Gathering Process

### Step 1: Clay People Search via Puppeteer (Hetzner server)

**Script**: `scripts/clay/clay_people_search.js --headless --auto`
**Server**: Hetzner (ssh hetzner), Node v22 + Chrome 144

**What happened**:
1. Script loaded 981 known gaming ICP domains from CSV + Clay TAM JSON
2. Split into 5 batches of 200 domains each (Clay UI can handle ~200 domains per search)
3. For each batch:
   - Navigated to Clay "Find leads" → clicked "People" tab
   - Found the "Companies" domain input (placeholder: `"amazon.com, microsoft.com"`)
   - Typed all 200 domains one by one (with Enter after each to add as tag)
   - Clicked Continue → "Save to new workbook and table" (from dropdown)
   - Skipped enrichments → "Create table" (0 credits)
   - Waited for table to populate
   - Read all records via Clay internal API from within browser context (`/v3/tables/{id}/bulk-fetch-records`)
   - Saved to JSON

**Batch results**:

| Batch | Domains typed | People found | Records read | Status |
|-------|--------------|-------------|-------------|--------|
| 1 | 200 | 4,574 (Clay count) | 4,559 (read) | Success |
| 2 | 200 | Failed — domain input not found on return to People tab | 4,981 (random people, no domain filter) | Partial fail — no domain filter applied |
| 3-5 | — | Browser crashed (timeout) | — | Not run |

**Why batch 2+ failed**: After batch 1, navigating back to Clay home → Find leads → People tab put the page in a different state. The domain input (`input[placeholder*="amazon"]`) was not found because Clay rendered the page differently on the second visit. The 61 empty-placeholder inputs visible were internal Clay UI elements.

### Step 2: Filter for Verified Gaming Companies

**Problem**: Batch 1 returned 4,559 people, but many were at non-gaming companies that happened to be in our domain list (pipeline CSV had some contamination from Apollo search).

**Filtering approach**: Keyword matching on domain + company name against gaming-related terms:
- Direct matches: `skin`, `csgo`, `cs2`, `dota`, `game`, `gambl`, `loot`, `bet`, `case`, `roll`, `trade`, `buff`, `steam`, `rust`, `clash`, `item`, etc.
- Known brand matches: `duelbits`, `stake`, `gamdom`, `hellcase`, `keydrop`, `dmarket`, `skinport`, etc.

**Result**: 1,040 people at 19 verified gaming companies (from 4,559 total)

### Step 3: Export to Google Sheets

- Created on Shared Drive (ID: `0AEvTjlJFlWnZUk9PVA`)
- Columns: Full Name, First Name, Last Name, Job Title, Company, Domain, LinkedIn, Location
- Public read access

## Step 4: Full TAM Search — All 981 Domains (5 Batches)

**Fixes applied** to `clay_people_search.js`:
1. **Fresh tab per batch** — opens a new browser tab for each batch, avoiding stale DOM
2. **Titles BEFORE domains** — applies job title filter first (typing 200+ domains hides other inputs)
3. **Dismiss dropdown** — presses Escape after typing titles to close suggestion menu
4. **Scroll to Companies** — sidebar "Companies" section is near bottom, needs scrolling
5. **Coordinate-based clicks** — uses `page.mouse.click(x,y)` instead of `ElementHandle.click()` to avoid detached node errors
6. **10-min timeout** — prevents timeout on large table reads

**Run 2: Title-filtered (--titles flag)**

| Batch | Domains | People found |
|-------|---------|-------------|
| 1 | 200 | 30 |
| 2 | 200 | 1 |
| 3 | 200 | 13 |
| 4 | 200 | 230 |
| 5 | 181 | 1 |
| **Total** | **981** | **275** |

**Run 3: All roles (no title filter)**

| Batch | Domains | People found |
|-------|---------|-------------|
| 1 | 200 | 137 |
| 2 | 200 | 8 |
| 3 | 200 | 18 |
| 4 | 200 | 1,275 |
| 5 | 181 | 3 |
| **Total** | **981** | **1,441** |

### Step 5: Merge + ICP Domain Filtering

**Problem**: Most people from new batches were at non-gaming companies (Clay TAM had noise — Code Ninjas, fintech, etc.)

**Approach**: Domain-based filtering against verified skin-selling domains:
- Pipeline CSV domains (309 verified gaming companies)
- Known brand domains (Stake, Gamdom, Duelbits, etc.)
- Keyword-in-domain match (skin, csgo, cs2, loot, case, etc.)

**Merged sources**:
1. Original Sheet data (1,040 people from first run's batch 1)
2. New batch data (1,441 people from 5 batches)
3. Dedup by LinkedIn URL → **2,476 unique people**
4. Filter by skin-selling domain → **1,026 people at 25 gaming companies**
5. Of those: **190 decision-makers**

## Final Output

**Google Sheet (Full TAM)**: https://docs.google.com/spreadsheets/d/1jNZVQF4bFl0bMn0fJgTeB60W068pX78HS870w67fJBY
- Tab "Decision Makers": 190 people (CEO, Founder, CTO, VP, Director, Head of...)
- Tab "All People": 1,026 people at gaming ICP companies
- Tab "Summary": company breakdown

**Previous Sheet (First Run)**: https://docs.google.com/spreadsheets/d/1piVnDfhtgpqRv-Cq-5IepuFbAK4fDe7P9M7EurzZC5s

| Company | Domain | People | Decision Makers |
|---------|--------|--------|----------------|
| MY.GAMES | my.games | 634 | 42 |
| Stake | stake.com | 98 | 25 |
| Gamdom | gamdom.com | 82 | 23 |
| Duelbits | duelbits.com | 63 | 22 |
| itemku (PT. Five Jack) | itemku.com | 42 | 12 |
| SportCast | sportcast.com.au | 18 | 8 |
| Roobet | roobet.com | 17 | 9 |
| Rainbet | rainbet.com | 16 | 8 |
| SkinBaron GmbH | skinbaron.de | 14 | 7 |
| Moonrail Limited (CSGOEmpire) | csgoempire.com | 13 | 8 |
| Others (15 companies) | various | 29 | 26 |
| **Total** | **25 companies** | **1,026** | **190** |

**Credits spent**: 0

**Clay tables created**: 11 (1 first run + 5 title-filtered + 5 all-roles)

## Key Findings

1. **Clay's People DB has limited coverage for niche gaming companies**. Of 981 domains searched, only ~25 had people in Clay's database. Major brands (MY.GAMES, Stake, Gamdom) are well-covered; small skin shops are not.
2. **The original first 200 domains** (batch 1, first run) contained most of the high-value companies.
3. **Domain filtering is essential** — Clay TAM + pipeline CSV have significant contamination (fintech, crypto, game dev studios, coding education).
4. **Fresh tab per batch** solves the navigation bug. Reusing the same tab after table creation causes Clay's UI to render differently.
5. **Title filter before domains** is critical — typing 200+ domains makes other inputs unreachable.

## Remaining Gaps

- **CSV export via UI still broken**: "Export" button is clickable but CSV file never downloads. Workaround: read table data via browser API.
- **Small gaming companies missing**: Companies like CSFloat, DMarket, cs.money, CSGO500 were in the domain list but had 0 people in Clay's database.
- **To find more people at small companies**: Need LinkedIn scraping, Apollo enrichment (when credits available), or Clay "Find People at Company" enrichment (costs credits).
