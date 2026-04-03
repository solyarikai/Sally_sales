# AU-PH Diaspora Pipeline — Status & Lessons

## Hard Numbers (2026-03-17)

| Metric | Count |
|--------|-------|
| Raw contacts gathered (all JSONs) | 44,579 |
| Unique by LinkedIn | 44,579 |
| **Located in Australia** | **10,908** (24%) |
| With domain | 29,816 (67%) |
| **Scored (AU + domain + clean)** | **6,163** |
| After 3/company cap | 6,163 |

**Sheet**: https://docs.google.com/spreadsheets/d/1D__hmuskt6AsCakhZaRS8zaQy2cYCldHii3_VsyoiEY
- Tab `AU-Philippines`: raw 15K contacts (sheet row limit)
- Tab `AU-PH Scored v2 0317_1827`: 6,163 scored contacts
- CSV: `/tmp/au_ph_scored.csv` on Hetzner

## Why Only 24% in Australia (THE PROBLEM)

University search finds alumni **worldwide**, not just in Australia:
- "University of the Philippines" alumni → 80% still in Philippines, 10% in AU, 10% elsewhere
- "UNSW" alumni → 70% in AU, but the non-Filipino alumni also show up
- Clay's `countries=["Australia"]` filter is applied but **university filter overrides location** — Clay returns anyone who went to that school, ignoring country

**Root cause**: Clay's people search with `--schools` flag treats school as primary filter and country as secondary/loose. It finds school alumni first, then loosely matches country.

## Scoring v2 — Algorithm, No GPT

Script: `easystaff-global/score_au_ph_v2.py`

### Hard Reject (removed before scoring):
| Reason | Count | % of 44K |
|--------|-------|----------|
| Not in Australia (location) | 19,877 | 45% |
| No domain | 14,763 | 33% |
| Truncated name (S., C., GAICD) | 2,139 | 5% |
| Blacklisted domain/company | 816 | 2% |
| Company regex (gov, uni, hospital) | 389 | 1% |
| Title regex (nurse, teacher, intern) | 207 | 0.5% |
| .ph domain (PH-based company) | 12 | 0.03% |

### Scoring Formula (0-100):
- **Domain quality (0-25)**: .com.au=25, .au=20, .com/.io=15, .ph=5
- **Role tier (0-25)**: CFO=25, COO=22, CHRO=20, CEO/Founder=18, CTO=15, Director=12, Manager=8
- **Search signal (0-25)**: PH university=23, AU university=22, Extended uni=20, Language=12
- **Data completeness (0-15)**: company_size=+5, industry=+5, phone=+5
- **Name penalty (-10 to 0)**: truncated=-10, short=-5

### Score Distribution:
| Range | Count |
|-------|-------|
| 80-100 | 0 |
| 60-79 | 40 |
| 40-59 | 4,877 |
| 20-39 | 1,245 |
| 0-19 | 1 |

## Critical Lessons (Don't Repeat These Mistakes)

### 1. ALWAYS output to CSV, not just Google Sheets
Google Sheets has a ~15K row limit for API writes. The pipeline exported 23K contacts in memory but only 15K made it to the sheet. 8K contacts were silently lost. **Always write CSV to disk first, then upload to sheet.**

### 2. University search returns GLOBAL alumni, not country-specific
Clay's `--schools` filter overrides `--countries`. A search for "UP alumni in Australia" returns UP alumni everywhere with loose AU matching. Only 24% of results are actually in Australia.

**Fix**: Post-filter by location OR use city-specific searches (university + city) instead of country.

### 3. City-split language skip was correct
Broad language search found 860 Tagalog speakers (under 5K cap). City splits would only return subsets = 100% dupes. Skip saved 2+ hours.

### 4. Status endpoint must be lightweight
The `/api/diaspora/status` endpoint returned the full progress array including all contact data. At 15K+ contacts, it timed out (>30s). Fixed by trimming to last 100 lines. **But the in-memory progress buffer still holds all contact data = OOM risk.**

### 5. Container restarts kill running pipelines
Backend container restarts every ~10-30 minutes (health check? memory?). Pipeline dies. Watcher script + sheet-based resume handles this, but each restart loses the in-memory dedup set → duplicate searches.

### 6. Credential suffixes as last names
Clay sometimes puts credentials (CPEng, GAICD, FCPA) as the last name. These need to be caught in scoring.

## Files
- Raw JSONs: `/scripts/data/raw_contacts/australia-philippines_*.json` (85 files, 112MB)
- Scoring script: `easystaff-global/score_au_ph_v2.py`
- Enterprise blacklist: `scripts/data/enterprise_blacklist.json`
- Pipeline service: `backend/app/services/diaspora_service.py`
- Pipeline API: `backend/app/api/diaspora.py`

## Next Steps to Get 20K+ Scored AU Contacts
1. The current 6,163 scored contacts are the cream — real AU-based decision-makers
2. To get more: need industry-based search (find AU companies, then find Filipino employees)
3. Or: surname search with AU city enforcement (Santos in Sydney, Reyes in Melbourne)
4. Pipeline is still running and adding contacts — check watcher
