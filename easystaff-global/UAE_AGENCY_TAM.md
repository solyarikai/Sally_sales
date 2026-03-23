# UAE Agency Segment — TAM Gathering Status

## ICP Definition

**Target**: Small digital service businesses (agencies) in UAE
- **Employee count**: 1-100 (sweet spot: 5-50)
- **Business model**: Digital services, NOT offline (no construction, hospitality, F&B, real estate, trading)
- **Structure**: HQ/client-facing in UAE business hub, remote team in talent countries
- **Pain point**: Paying contractors across multiple countries (not simple UAE→India bank transfers)
- **Validated**: 44% of 25 qualified leads are service/agency/digital businesses

## Data Collected (as of Mar 19, 2026)

### Dataset 1: Keyword Search (People Tab)
- **File**: `data/dubai_agency_companies_full.json`
- **Script**: `scripts/apollo_companies_god.js` (original 32 keywords)
- **Method**: `qOrganizationName` filter + `personLocations[]=Dubai`
- **Result**: **295 companies**
- **Limitation**: Only finds companies with "agency/studio/production" literally in name

### Dataset 2: God-Mode Strategy B (People Tab)
- **File**: `data/uae_god_search_companies.json`
- **Script**: `scripts/apollo_god_search.js --strategy B`
- **Method**: ALL founders/CEOs/owners at 1-200 emp companies in 3 UAE cities (no keyword constraint)
- **Filters**: 3 cities × 5 size ranges × 3 seniority levels = 45 search configs
- **Result**: **5,602 companies** (12,201 people scraped)
- **Has**: domain (3,875), linkedin (4,302), employee count, people names/titles
- **Size**: 1,599 (1-10), 1,706 (11-50), 593 (51-100), 404 (101-200), 1,298 unknown

### Dataset 3: Companies Tab (Industry Tags + Keywords)
- **File**: `data/uae_20k_companies.json`
- **Script**: `scripts/apollo_companies_god.js`
- **Method**: Industry tags (IT Services, Marketing & Advertising) + 60+ keyword searches
- **Result**: **7,782 companies**
- **Has**: linkedin (7,554), employee count, company name
- **Missing**: NO domains (Companies tab DOM doesn't expose them)
- **Size**: 3,389 (1-10), 2,007 (11-50), 488 (51-100), 272 (101-200), 1,625 unknown

### NOT YET RUN: Strategy A (Expanded Keywords, People Tab)
- **Script**: `scripts/apollo_god_search.js --strategy A`
- **Method**: 80+ keywords × 3 UAE cities = 321 search configs
- **Expected**: +1,500-2,000 unique companies
- **Advantage**: Gets domain + people data (unlike Companies tab)

## Merged Totals

| Metric | Count |
|--------|-------|
| **Total unique companies (all datasets)** | **12,889** |
| Filtered to ≤100 employees | **12,268** |
| — Size 1-10 | 4,952 |
| — Size 11-50 | 3,601 |
| — Size 51-100 | 1,038 |
| — Size unknown | 2,677 |
| With domain | 3,502 |
| With LinkedIn URL | 10,975 |
| Overlap between god + tab (by name) | 277 |

## What's Missing

1. **Domains** — 8,766 companies have no domain. Companies tab doesn't provide them. Need:
   - Strategy A search (People tab → gets domains) for +1,500 companies
   - LinkedIn → domain resolution via Clay or manual for the rest
2. **Offline filtering** — the 12,268 includes restaurants, construction, trading. Need to filter with 60+ exclusion keywords
3. **Scoring** — no quality scoring applied yet to merged dataset
4. **FindyMail enrichment** — need domains first, then email discovery
5. **Dedup against existing campaigns** — need to check against enterprise blacklist + active campaigns

## Pipeline Next Steps

1. Run Strategy A (People tab, 80+ keywords) — fills domain gap
2. Merge all 3 datasets + Strategy A results
3. Filter offline businesses (60+ exclusion keywords)
4. Dedupe against enterprise blacklist (1,004 domains)
5. Score: digital service businesses with 5-50 emp get highest score
6. Clay enrichment for employee location validation
7. FindyMail for email discovery
8. Upload to SmartLead campaign

## Scripts Reference

| Script | Tab | What it does |
|--------|-----|-------------|
| `scripts/apollo_god_search.js --strategy A` | People | 80+ keywords × 3 cities, gets domains+people |
| `scripts/apollo_god_search.js --strategy B` | People | Broad seniority search, gets domains+people. DONE. |
| `scripts/apollo_companies_god.js` | Companies | Industry tags + keywords, gets linkedin only |

## Apollo Search Filters Available

| Filter | URL Param | Used? |
|--------|-----------|-------|
| Person location | `personLocations[]=Dubai, United Arab Emirates` | Yes |
| Company name keyword | `qOrganizationName=marketing agency` | Yes (Strategy A) |
| Seniority | `personSeniorities[]=founder` | Yes (Strategy B) |
| Company size | `organizationNumEmployeesRanges[]=1,10` | Yes |
| Industry tag | `organizationIndustryTagIds[]=5567cd4773696439b10b0000` | Yes (Companies tab) |

Size ranges: `1,10` / `11,20` / `21,50` / `51,100` / `101,200`
