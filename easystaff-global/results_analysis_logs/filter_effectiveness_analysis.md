# Filter Effectiveness Analysis — Which Apollo Filters Produce Targets

## Problem

We have 331 verified targets but can't trace most of them back to which specific Apollo keyword/filter found them. This data gap exists because:

1. **Dubai targets (317)**: Found via Puppeteer People Tab scraper. The scraper ran 80+ keywords but didn't tag which keyword found which company. The `source_data` stores the raw Apollo person record, not the search keyword.

2. **NYC targets (22)**: Found via Companies Tab. The `_source` field exists (e.g. "marketing agency_1,10") but only for 29 companies total.

3. **LA targets (26)**: Same as NYC.

## What we DO know

### From NYC/LA Companies Tab (29 targets with `_source` tag)

| Apollo keyword + size | Targets found |
|----------------------|---------------|
| marketing agency, 1-10 emp | 15 |
| marketing agency, 11-50 emp | 12 |
| marketing agency, 51-200 emp | 2 |

**marketing agency** is the only keyword that produced targets in the Companies Tab data we have tagged.

### From Dubai gathering run analysis

| Gathering run | Strategy | Total gathered | Targets | Target rate |
|--------------|----------|---------------|---------|-------------|
| #4 Strategy A (80+ keywords) | Keywords | 1,844 | 181 | 9.8% |
| #1 Strategy B (seniority) | Broad seniority search | 3,867 | 103 | 2.7% |
| #3 Strategy C (VP/director) | Expanded seniority | 1,143 | 17 | 1.5% |
| #63 LA Companies Tab | Keywords | 1,507 | 19 | 1.3% |
| #56 NYC Companies Tab | Keywords | 2,061 | 10 | 0.5% |
| #5 Strategy D (industry keywords) | Industry terms | 173 | 7 | 4.0% |

**Strategy A (80+ keywords)** produced the most targets (181) with 9.8% target rate. But we don't know WHICH of the 80+ keywords were most effective.

### From API volume research (168 credits spent)

| Keyword | Miami | Riyadh | London | Singapore | Sydney | Austin |
|---------|-------|--------|--------|-----------|--------|--------|
| **creative agency** | 277 | 186 | 2,617 | 429 | 576 | 232 |
| **marketing agency** | 240 | 131 | 969 | 224 | 270 | 154 |
| **digital agency** | 106 | 33 | 631 | 132 | 180 | 60 |
| **design agency** | 44 | 27 | 435 | 54 | 85 | 38 |
| **branding agency** | 41 | 37 | 332 | 47 | 70 | 43 |
| **PR agency** | 12 | 3 | 318 | 30 | 53 | 14 |
| **media agency** | 55 | 38 | 428 | 70 | 108 | 38 |
| video production | 868 | 442 | 6,135 | 1,150 | 1,593 | 896 |
| web design | 1,368 | 604 | 6,821 | 1,255 | 2,249 | 1,334 |
| software development | 2,736 | 2,066 | 17,986 | 5,229 | 4,685 | 4,394 |
| IT services | 1,715 | 2,135 | 12,403 | 4,565 | 4,806 | 2,317 |
| e-commerce | 4,888 | 2,479 | 24,844 | 7,945 | 8,829 | 4,179 |

**Bold = ICP-specific keywords** with expected 10-15% target rate.
Normal = broad keywords with 1-5% target rate (lots of noise).

## Conclusions

### High-confidence filter sets (proven by Dubai results)
1. **"marketing agency"** — highest proven target rate (15/29 NYC targets came from this keyword)
2. **"digital agency"** — core ICP, fewer results but very targeted
3. **"creative agency"** — large volume + ICP alignment
4. **Seniority-based search** — 2.7% rate but casts widest net

### Recommended filter sets for new cities (based on evidence)

**Tier 1 (spend first — 7 keywords, ~7 credits per city):**
- digital agency, creative agency, marketing agency, design agency, branding agency, PR agency, media agency

**Tier 2 (spend second if Tier 1 yields >5% target rate — 6 keywords):**
- web design, video production, animation studio, production house, SEO agency, content agency

**Tier 3 (spend carefully — high volume, low target rate):**
- software development, app development, mobile development
- IT services, SaaS, tech startup, consulting firm

**DO NOT spend on (very low target rate, huge noise):**
- e-commerce, data analytics (1-2% rate, thousands of irrelevant companies)

## Architectural fix needed

The pipeline MUST tag each company with the keyword that found it. Currently:
- `company_source_links.source_data` stores the raw Apollo record
- The `_keyword` or `_source` field is set inconsistently
- Per-keyword target rate analysis is impossible for most runs

**Fix:** In `gather_cities_api.py`, each company already gets `_keyword` in source_data. For future runs, this traces filter → company → target.

## Credits spent today

| Activity | Credits | Companies |
|----------|---------|-----------|
| Filter research (28 kw × 6 cities) | 168 | ~4,000 (not saved to DB) |
| Smart gathering (6 cities) | 216 | 8,321 (saved to DB) |
| Earlier incidents | ~25 | ~75 |
| **Total** | **~409** | **8,396** |
