# EasyStaff Global — Next Steps Plan

## Current State (Mar 15, 2026)

| Corridor | Scored | Clay enriched | Total | Companies |
|----------|--------|--------------|-------|-----------|
| UAE-Pakistan | 575 | +237 | **812** | 534 |
| AU-Philippines | 310 | +306 | **616** | 302 |
| Arabic-SouthAfrica | 149 | +3 | **152** | 147 |
| **TOTAL** | **1,034** | **546** | **1,580** | **983** |

Algorithm: 95%+ accuracy after 3 iterations (300 companies verified).
All output in separate Google Sheet tabs: `{Corridor} v8 Scored`.

## Problem: AU-Philippines Has Wrong Origin Data

The AU-Philippines source tab has Pakistani-origin contacts (Urdu speakers), NOT Filipino-origin.
Clay searches used the same PK-origin filters across all corridors.
**FIX NEEDED:** New Clay searches with Filipino-origin filters (Tagalog, PH universities, Filipino surnames) for contacts in Australia.

## Scaling to 2,000+ Contacts Per Corridor

### Approach 1: Apollo Scraper (runs on Hetzner)

**What:** Chrome extension that scrapes Apollo.io search results page by page. Gets full contact details without spending API credits.

**Access:** `danila@getsally.io` / `UQdzDShCjAi5Nil!!`

**How to run on Hetzner:**
1. Install Chrome + extension on Hetzner (headless Chromium + Puppeteer to load extension)
2. Login to Apollo with the credentials
3. Set search filters for each corridor
4. Run scraper — exports CSV with full contact data

**Search configs per corridor:**

**UAE-Pakistan (find decision-makers at target companies):**
- Organization: domains from scored list (534 companies)
- Person location: United Arab Emirates
- Titles: CEO, CFO, COO, VP, Director, Head, Founder, Managing Director, Owner
- NOT: Manager, Senior, Entry, Intern

**AU-Philippines (NEW Filipino-origin contacts):**
- Person location: Australia
- Person titles: CEO, CFO, COO, VP, Director, Head, Founder
- Company size: 1-200
- Need Filipino-origin filter — Apollo doesn't have language filter, but can search by:
  - Filipino universities (Ateneo, De La Salle, UP Diliman, UST, etc.)
  - Filipino surnames (common Filipino surnames list)

**Arabic-SouthAfrica (SA-origin contacts in Gulf):**
- Person location: Qatar, Saudi Arabia, UAE, Bahrain, Kuwait, Oman
- Person titles: CEO, CFO, COO, VP, Director, Head, Founder
- Company size: 1-200
- SA-origin filter:
  - South African universities (UCT, Wits, Stellenbosch, UP, UJ)
  - Common SA surnames

### Approach 2: Apollo API (partially free)

**What:** Apollo API returns search results with obfuscated last names (free). Full reveal costs credits.

**Free data from search:** first_name, last_name_obfuscated, title, organization.name, has_email, location indicators

**Approach:** Search → get company names and first names → cross-reference with Clay People Search (free) to get full details.

**API key:** `APOLLO_API_KEY` in `.env` on Hetzner

### Approach 3: Clay People Search (already working)

**Current Clay enrichment:** finds decision-makers at target companies.
Limited yield (237 UAE-PK, 306 AU-PH, 3 Arabic-SA) because:
- Many target companies are small (no LinkedIn-visible C-level)
- Clay free tier only returns people without emails

**To improve Clay yield:**
- Search without domain filter → broader results → filter by scored domains after
- Search by Filipino/SA university filters for AU-PH and Arabic-SA corridors

## Execution Order

### Phase 1: Fix AU-PH corridor data (TODAY)
1. Run Clay with Filipino-origin filters for Australia contacts
2. Score the new Filipino-origin contacts through the pipeline
3. Write to new output tab

### Phase 2: Apollo scraper on Hetzner (TONIGHT)
1. Convert Apollo Chrome extension to Puppeteer script (no manual Chrome needed)
2. Login with credentials, set search filters
3. Scrape decision-makers at scored target companies
4. Import results into scoring pipeline
5. Each corridor: scrape → score → write to sheet

### Phase 3: Iterate all corridors to 95%+ (ONGOING)
1. Score → verify 100 → fix algorithm → repeat
2. Each corridor gets independent verification
3. AU-PH and Arabic-SA need their own PK-neighborhood equivalent detections
   (Filipino neighborhoods for PH, SA neighborhoods for ZA)

## Infrastructure Notes

- ALL data persists in `/scripts/data/` (Docker mounted volume)
- Apollo scraper runs on Hetzner host (Node.js + Puppeteer + Chrome extension)
- Clay runs on Hetzner host (Node.js + Puppeteer)
- Scoring + GPT run inside Docker container
- NEVER use `/tmp/` in Docker containers
- NEVER overwrite existing Google Sheet tabs
