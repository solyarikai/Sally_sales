# UAE Agency Search — Full Analysis

**KPI: 5,000 target companies**

UAE has 400,000+ registered businesses in Dubai alone. ~10% are digital/service businesses = ~40,000.
Apollo indexes maybe 50-100K of these. 5,000 is very achievable with the right search approach.

---

## Execution Log

### Run 1: Original keyword search (Mar 18, 2026)
- **Script**: `scripts/apollo_companies_god.js`
- **Method**: `qOrganizationName` (company name contains keyword) + `personLocations[]=Dubai`
- **Filters applied**: company name keyword only. NO seniority, NO company size, NO industry
- **Keywords**: 32 (marketing agency, digital agency, media production, etc.)
- **Pages per search**: up to 10
- **Cities**: Dubai only
- **Result**: 295 unique companies, 184 with domains
- **Problem**: Only finds companies with "agency/studio/production" literally in name

### Run 2: God-mode Strategy B (Mar 19, 2026 ~1:30 AM)
- **Script**: `scripts/apollo_god_search.js --strategy B`
- **Method**: Broad seniority search — ALL founders/CEOs/owners at small companies
- **Filters applied via URL params**:
  - `personLocations[]` = Dubai, Abu Dhabi, Sharjah (3 cities)
  - `personSeniorities[]` = founder, c_suite, owner (one per search)
  - `organizationNumEmployeesRanges[]` = 1-10, 11-20, 21-50, 51-100, 101-200 (one per search)
  - NO `qOrganizationName` (no company name constraint)
  - NO industry filter
- **Total search configs**: 45 (3 cities × 5 size ranges × 3 seniority levels)
- **Pages per search**: 10 (250 people max per search)
- **Status**: RUNNING on Hetzner (PID tracked)

**Live results (after 5/45 searches completed)**:
- 2,600 people scraped
- **1,320 unique companies** (already 4.5x the original 295!)
- Title distribution confirms filters work: 1,069 founders, 518 CEOs, 519 owners
- Companies include: trading, freight, fintech, AI, recruitment — NOT just agencies
- Need post-filtering to remove offline businesses (restaurants, construction, trading, etc.)
- Every search maxes out at 250 (10 pages full) = Apollo has WAY more results per config
- **Projected at 45 searches: 5,000-8,000+ unique companies before filtering**

**Update (1:40 AM)**: Resumed from saved progress (10/45 done).
**Update (2:20 AM)**: COMPLETED. All 45 searches done.

**Final results**:
- 12,201 people scraped across 3 UAE cities
- **6,520 raw unique companies** (6,048 after name dedup)
- **5,602 after offline filtering** (excluded 918 restaurants, construction, trading, etc.)
- **5,150 with valid names** (452 had empty/junk names from DOM)
- **3,873 with website domains**
- Title mix: 3,650 founders, 2,553 owners, 1,794 CEOs, 817 CTOs, 681 directors
- Size: 1,598 (1-10 emp), 1,706 (11-50), 592 (51-100), 404 (101-200)
- **KPI: 5,000 target → ACHIEVED (5,150 real companies)**

### Run 3: Apollo Companies Tab — API Discovery (Mar 19, 2026 ~1:35 AM)
- **Script**: `scripts/apollo_companies_search.js --discover --screenshot`
- **Method**: Direct API calls to `POST /api/v1/mixed_companies/search`
- **Discovery results**:
  - Apollo has **155,419+ companies** in UAE with 1-50 employees indexed
  - 124,723 with 1-10 emp, 17,155 with 11-20, 13,541 with 21-50, 5,238 with 51-100, 2,635 with 101-200
  - API returns structured data: `accounts[]` with name, domain, linkedin, phone, industry, city, employees
  - Supplementary endpoint: `POST /api/v1/organizations/load_snippets` for industry/keywords/location
- **Problem**: Direct API only returns companies user has "accessed" (free plan limitation)
  - "agency" keyword: 291 total, but only 9 returned in API
  - Broad (no keyword): 124K total for 1-10 emp, only 11 returned
  - DOM shows all 25/page but API returns subset
- **Conclusion**: Must use DOM scraping (like People tab) for volume. Direct API only for enrichment.

### Run 4: Companies Tab Search Params Tested

| Param | Works? | Notes |
|-------|--------|-------|
| `q_keywords` | YES but broad | Matches company name + description, 163K results for "agency" |
| `q_organization_name` | YES, targeted | Matches company name only, 291 for "marketing agency" |
| `organization_locations` | YES | `["United Arab Emirates"]` |
| `organization_num_employees_ranges` | YES | `["1,10"]`, `["11,20"]`, etc. |
| `sort_by_field` | YES | `"[none]"` or field name |
| `finder_version` | Required | Integer `2` (not string) |
| `search_session_id` | Required | UUID, must be unique per search to avoid caching |
| `cacheKey` | Helps | Timestamp, prevents cached responses |
| `fields` | YES | Specify which account fields to return |
| `display_mode` | YES | `"explorer_mode"` for full data |

### Pending: Strategy A (expanded keywords)
- **Script**: `scripts/apollo_god_search.js --strategy A`
- **Method**: Same as Run 1 but with 80+ keywords across 3 UAE cities
- **New keyword categories**: recruitment, HR, IT outsourcing, consulting, fintech, edtech, healthtech, media subtypes, broader digital terms
- **Total search configs**: 321 (107 keywords × 3 cities)
- **Expected yield**: +1,500-2,000 unique companies
- **Status**: NOT YET STARTED (will run after Strategy B completes)

### Run 5: Companies Tab God Search (Mar 19, 2026 ~1:10 AM)
- **Script**: `scripts/apollo_companies_god.js --max-pages 100`
- **Method**: Companies tab DOM scraping with industry tag IDs + keyword search
- **KPI**: 20,000 companies

**Discovered Apollo industry tag IDs**:
| Industry | Tag ID | Total in UAE |
|----------|--------|-------------|
| information technology & services | `5567cd4773696439b10b0000` | 20,550 |
| marketing & advertising | `5567cd467369644d39040000` | TBD |
| retail | `5567ced173696450cb580000` | TBD (not ICP) |

**Search configs**: 2 industry tags + 60+ keyword searches
- Tags: IT, Marketing (URL param: `organizationIndustryTagIds[]=`)
- Keywords: software, digital marketing, design, media production, consulting, recruitment, fintech, edtech, etc.
- Location: `organizationLocations[]=United Arab Emirates`
- Size: `organizationNumEmployeesRanges[]=1,10&...11,20&...21,50&...51,100&...101,200`
- Max 100 pages per search (2,500 companies max per search)

**Key findings**:
- `organizationIndustryTagIds[]` works as URL param — filters accurately
- `qKeywords=` does NOT filter in Companies tab URL (returns all 163K companies regardless)
- DOM selector: `a[data-to*="/organizations/"]` (not `/companies/`!)
- DOM captures 13-22 companies per page (not always full 25)
- IT & Services alone has 20,550 companies in UAE → 100 pages would give ~2,000
- **Projected: 5,000-20,000+ unique companies from all searches combined**

**Status**: RUNNING on Hetzner

### Post-processing plan
1. Merge Strategy B + Strategy A results
2. Filter out offline companies (60+ exclusion keywords: restaurant, construction, trading, hotel, etc.)
3. Deduplicate against existing campaigns
4. Score remaining companies (digital service businesses get highest score)
5. Enrich with Clay for employee locations (who's in which country)
6. FindyMail for email discovery

---

## Current State: 295 Companies (6% of KPI)

### What Was Done (Mar 18)
- **Method**: `qOrganizationName` filter + `personLocations[]=Dubai` (People tab)
- **Script**: `scripts/apollo_companies_god.js` (32 keywords × up to 10 pages each)
- **Result**: 295 unique companies, 184 with domains
- **Problem**: Only searched company NAME containing "agency/studio/production" — misses 90%+ of service businesses

### Why 295 Is So Low

| Problem | Impact | Fix |
|---------|--------|-----|
| Company name search too literal | "Frizzon Studios" wouldn't match any keyword | Use seniority + size filters (no name constraint) |
| Only 32 keywords | Missed entire categories (HR, IT outsourcing, fintech, etc.) | Expanded to 80+ keywords |
| No seniority filter | Got random employees, not decision-makers | Filter: founder, c_suite, owner |
| No company size filter | No size constraint | Filter: 1-200 employees |
| Only Dubai searched | Missed Abu Dhabi, Sharjah | Search all 3 UAE cities |
| Industry filter not used | Can't find companies without "agency" in name | Use Apollo industry categories |

---

## God-Mode Search Plan

### Script: `scripts/apollo_god_search.js`

Two complementary strategies to exhaust Apollo's UAE coverage:

### Strategy A: Expanded Keywords (80+ queries × 3 cities)

32 original keywords PLUS 50+ new ones:

**New — Professional Services:**
recruitment agency, recruitment consultancy, HR consultancy, HR outsourcing,
management consulting, business consulting, outsourcing, BPO,
IT outsourcing, IT consulting, accounting firm, bookkeeping services,
translation services, localization, architecture firm, interior design,
engineering consultancy, legal services

**New — Digital/Tech (broader):**
digital marketing, performance marketing, growth agency, data analytics,
AI consulting, cloud consulting, cybersecurity, DevOps, mobile development,
mobile app, product design, UI design, web agency, ecommerce,
PPC agency, email marketing, automation agency, CRM consulting,
ERP consulting, software house

**New — Tech Verticals:**
fintech, edtech, healthtech, proptech, martech, insurtech,
logistics tech, regtech, legaltech

**New — Media & Entertainment:**
podcast production, music production, recording studio, VFX studio,
CGI, 3D studio, audio production, content creation, live streaming, broadcast

**New — Broader Service Terms:**
digital solutions, tech solutions, creative studio, innovation lab,
digital transformation, development studio, digital studio, media agency,
communications agency, integrated agency, strategy consulting,
research firm, market research, training company, coaching firm,
development company, technology company

**Expected yield**: 80+ keywords × 3 cities × ~8 companies avg = ~1,500-2,000 unique companies

### Strategy B: Broad Seniority Search (no keyword constraint)

Search for ALL founders/CEOs at small companies in UAE — **no company name or industry filter**.

| Search | Combinations | Max Results per Search |
|--------|-------------|----------------------|
| 3 UAE cities × 5 size ranges × 3 seniorities | 45 searches | 2,500 each |
| **Theoretical max** | | **112,500 people** |
| **Realistic unique companies** | | **3,000-5,000+** |

This captures companies that don't have "agency" in their name — which is most of them.

Post-filtering removes offline businesses (restaurants, construction, trading, etc.) using 60+ exclusion keywords.

### Combined Target

| Strategy | Est. Companies | Status |
|----------|---------------|--------|
| Previous (32 keywords, Dubai only) | 295 | Done |
| Strategy A (80+ keywords × 3 cities) | +1,500 | Ready |
| Strategy B (broad seniority × size × city) | +3,000 | Ready |
| **Total after dedup** | **~4,000-5,000+** | |

---

## All Search Filters Tested

### Filters That Work (URL params in People tab)

| Filter | URL Param | Status |
|--------|-----------|--------|
| Person location | `personLocations[]=Dubai, United Arab Emirates` | Proven |
| Company name keyword | `qOrganizationName=marketing agency` | Proven |
| Seniority | `personSeniorities[]=founder` | Testing |
| Company size | `organizationNumEmployeesRanges[]=1,50` | Testing |

### Filters Not Yet Tested

| Filter | How to Access | Expected Impact |
|--------|--------------|-----------------|
| Industry category | Apollo sidebar / API | HIGH — finds companies without "agency" in name |
| Revenue | Apollo sidebar | Medium — filters out micro-businesses |
| Technologies used | Apollo sidebar | Low — useful for tech stack targeting |
| Department size | Apollo sidebar | Low |

### Alternative Search Approaches

| Approach | Platform | Expected Yield | Effort |
|----------|----------|---------------|--------|
| Companies tab + industry filter | Apollo | +2,000 | Low (modify scraper) |
| LinkedIn Sales Navigator | LinkedIn | +3,000 | Medium (new scraper) |
| Google Maps scraping | Google | +1,000 | Medium (new scraper) |
| Clutch.co / GoodFirms directories | Web | +500 | Low (simple scrape) |
| Dubai Chamber / DED registry | Gov | +5,000 | High (may need API) |
| Crunchbase | Web | +1,000 | Medium |

---

## Original 32 Keywords (Mar 18 Results)

| # | Keyword | Companies |
|---|---------|-----------|
| 1 | software development | 19 |
| 2 | design agency | 17 |
| 3 | branding agency | 16 |
| 4 | creative agency | 15 |
| 5 | production house | 15 |
| 6 | SEO agency | 14 |
| 7 | digital agency | 14 |
| 8 | marketing agency | 14 |
| 9 | web design | 14 |
| 10 | talent management | 13 |
| 11 | advertising agency | 12 |
| 12 | media production | 12 |
| 13 | PR agency | 11 |
| 14 | film production | 11 |
| 15 | social media agency | 11 |
| 16 | IT services | 10 |
| 17 | animation studio | 10 |
| 18 | game studio | 9 |
| 19 | video production | 7 |
| 20 | consulting firm | 6 |
| 21 | content agency | 6 |
| 22 | influencer agency | 5 |
| 23 | app development | 4 |
| 24 | e-commerce | 4 |
| 25 | event production | 4 |
| 26 | photography studio | 4 |
| 27 | post production | 4 |
| 28 | staffing agency | 4 |
| 29 | SaaS | 3 |
| 30 | tech startup | 3 |
| 31 | motion graphics | 2 |
| 32 | web development agency | 2 |

**Total: 295 unique companies across 32 queries**

---

## Execution

```bash
# Deploy to Hetzner
scp scripts/apollo_god_search.js hetzner:~/magnum-opus-project/repo/scripts/

# Dry run — see all search configs
ssh hetzner 'cd ~/magnum-opus-project/repo && node scripts/apollo_god_search.js --dry-run'

# Run Strategy A only (keywords — faster, ~1hr)
ssh hetzner 'cd ~/magnum-opus-project/repo && node scripts/apollo_god_search.js --strategy A'

# Run Strategy B only (broad seniority — ~30min)
ssh hetzner 'cd ~/magnum-opus-project/repo && node scripts/apollo_god_search.js --strategy B'

# Run everything (2-3 hrs)
ssh hetzner 'cd ~/magnum-opus-project/repo && node scripts/apollo_god_search.js'

# Resume after interruption
ssh hetzner 'cd ~/magnum-opus-project/repo && node scripts/apollo_god_search.js --resume'

# Dubai only
ssh hetzner 'cd ~/magnum-opus-project/repo && node scripts/apollo_god_search.js --city Dubai'
```

## Data Files

| File | Records | Description |
|------|---------|-------------|
| `data/dubai_agency_companies_full.json` | 295 | Run 1: keyword search (32 keywords, Dubai only) |
| `data/dubai_companies_with_domains.json` | 184 | Run 1: companies with extractable domains |
| `data/uae_god_search_companies.json` | 5,602 | **Run 2: God search — filtered companies** |
| `data/uae_god_search_people.json` | 12,201 | Run 2: all people records (founders/CEOs/owners) |
| `data/uae_god_search_progress.json` | 45/45 | Run 2: completed search progress |
| `data/uae_companies_api_results.json` | varies | Run 3: Companies tab API test results |
| `data/apollo_companies_api_discovery.json` | — | Run 3: API format discovery data |
| `data/apollo_companies_tab.png` | — | Run 3: Companies tab UI screenshot |
