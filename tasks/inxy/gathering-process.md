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

## Final Output

**Google Sheet**: https://docs.google.com/spreadsheets/d/1piVnDfhtgpqRv-Cq-5IepuFbAK4fDe7P9M7EurzZC5s

| Company | Domain | People found |
|---------|--------|-------------|
| MY.GAMES | my.games | 639 |
| Stake | stake.com | 98 |
| Gamdom | gamdom.com | 82 |
| Duelbits | duelbits.com | 63 |
| itemku (PT. Five Jack) | itemku.com | 54 |
| Sportcast | sportcast.com.au | 21 |
| Roobet | roobet.com | 19 |
| Rainbet | rainbet.com | 17 |
| SkinBaron GmbH | skinbaron.de | 14 |
| Moonrail Limited (CSGOEmpire) | csgoempire.com | 13 |
| Others (9 companies) | various | 20 |
| **Total** | **19 companies** | **1,040 people** |

**Credits spent**: 0

## What's Missing

### Coverage gaps
- Only 200 of 981 domains were successfully searched (batch 1 only)
- 781 domains in batches 2-5 were not searched due to automation bug
- Job title filter was not applied (input hidden after typing domains) — so results include all roles, not just decision-makers
- Many known gaming companies (CSFloat, DMarket, cs.money, CSGO500, etc.) may not have been in the first 200 domains

### Known issues to fix
1. **Batch navigation**: After completing one search, returning to People tab doesn't render the same way. Fix: open a fresh tab or fully reload the page between batches.
2. **Filter order**: Apply job titles FIRST (they use a visible input), THEN expand Companies section and type domains.
3. **CSV export**: The "Export" option in Actions menu was found and clicked, but the CSV file never appeared in the download directory. May need Chrome download path configuration or a different export flow.
4. **Domain input capacity**: 200 domains per search works but is slow (~2 min to type). Clay may support pasting comma-separated domains.

### Next steps to complete TAM
1. Fix batch navigation bug (fresh page per batch)
2. Run remaining 781 domains in 4 more batches
3. Apply job title filter to narrow to decision-makers
4. Merge all batches, dedup by LinkedIn URL
5. Re-export to Google Sheets with full coverage
