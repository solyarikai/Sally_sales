# EasyStaff Global — 10K Apollo Credits Blitz Plan

**Created**: 2026-03-22 01:45 UTC
**Last updated**: 2026-03-22 02:20 UTC
**DEADLINE**: 2 hours — billing resets tomorrow, 9,149 credits must be spent
**Status**: EXECUTING — Steps 1-5 DONE, Step 5 (people search) RUNNING, Step 6 (blacklist) QUEUED

---

## CREDIT BUDGET: 9,149 remaining (40,055 total - 30,906 used)

| Phase | Credits needed | Purpose |
|-------|---------------|---------|
| Phase 1: 4 new cities (DONE) | ~132 | Doha, Jeddah, Berlin, Amsterdam |
| Phase 2: Deep pagination existing cities | ~2,000 | Pages 2-10 for high-volume keywords |
| Phase 3: New cities (Melbourne, Abu Dhabi + more) | ~1,500 | Exhaust all target cities |
| Phase 4: People search (3 contacts per target) | ~4,000 | 1 credit per company, get 3 decision-makers |
| Reserve / additional expansion | ~1,500 | Any remaining cities or deeper pagination |
| **TOTAL** | **~9,149** | |

---

## EXECUTION ORDER (strict sequence)

### Step 1: Finish 4-city pipeline — DONE
- [x] Apollo extraction: Doha (736), Jeddah (851), Berlin (1,316), Amsterdam (1,364) — 132 credits
- [x] Website scraping: 2,533/4,267 succeeded
- [x] GPT-4o-mini V8 analysis: 2,524 done, **935 targets** at 37.0% rate
- [x] Opus review: 935 reviewed, **858 OK, 77 FP** (91.8% accuracy)
- [x] FPs removed: 77 domains set is_target=false → **4,000 verified targets**

### Step 2: Opus review ALL new targets (BEFORE spending more credits)
- [ ] Export all new targets from Step 1 (~600+ expected)
- [ ] Opus review in parallel batches (4 agents)
- [ ] Remove false positives from DB
- [ ] Confirm >= 90% accuracy
- **ETA**: ~5 min

### Step 3: Deep pagination — SKIPPED (better ROI from new cities)
Skipped in favor of Step 4 — new cities yield ~1,000 unique companies per 33 credits. Deep pagination would give diminishing returns (page 2+ = lower quality).

### Step 3 (original): Deep pagination on high-yield cities (~2,000 credits)
Paginate pages 2-10 for P1/P2 keywords that returned 100+ results on page 1.

| City | High-volume keywords | Est. pages | Est. credits |
|------|---------------------|-----------|-------------|
| Berlin | digital agency (3,100), marketing agency (2,800), design agency (1,500) | 30 | 30 |
| Amsterdam | digital agency (2,500), marketing agency (2,200) | 25 | 25 |
| London (run 77) | digital agency (5,000+), marketing (4,000+) | 50 | 50 |
| NYC (run 56) | digital agency (8,000+) | 50 | 50 |
| LA (run 63) | digital agency (4,000+) | 40 | 40 |
| Sydney (run 79) | digital agency (2,000+) | 25 | 25 |
| Singapore (run 78) | digital agency (1,500+) | 20 | 20 |
| Riyadh (run 76) | digital agency (800+) | 15 | 15 |
| Miami (run 75) | digital agency (1,000+) | 15 | 15 |
| Austin (run 80) | digital agency (800+) | 10 | 10 |
| Doha (run 81) | marketing agency (500+) | 10 | 10 |
| Jeddah (run 82) | marketing agency (600+) | 10 | 10 |
| **Subtotal** | | | **~300** |

Then scrape + GPT analyze + Opus review all new companies.

### Step 4: 15 new cities — IN PROGRESS (13/15 gathered)

| City | Run | Unique | New | Credits | Status |
|------|-----|--------|-----|---------|--------|
| San Francisco | #85 | 1,090 | 1,086 | 34 | GATHERED |
| Chicago | #86 | 1,331 | 1,328 | 35 | GATHERED |
| Boston | #87 | 948 | 944 | 32 | GATHERED |
| Seattle | #88 | 1,106 | 1,100 | 33 | GATHERED |
| Denver | #89 | 1,131 | 1,124 | 33 | GATHERED |
| Portland | #90 | 973 | 971 | 32 | GATHERED |
| Toronto | #91 | 1,687 | 1,680 | 36 | GATHERED |
| Melbourne | #92 | 1,597 | 1,591 | 34 | GATHERED |
| Dublin | #93 | 927 | 925 | 32 | GATHERED |
| Stockholm | #94 | 1,242 | 1,239 | 33 | GATHERED |
| Mumbai | #95 | 1,712 | 1,701 | 39 | GATHERED |
| Bangalore | #96 | 736 | 735 | 30 | GATHERED |
| Cape Town | #97 | 1,318 | ~1,310 | 35 | GATHERED |
| Sao Paulo | #98 | ~1,600 | ~1,600 | ~36 | SAVING |
| Abu Dhabi | — | — | — | — | QUEUED |
| Sao Paulo | #97 | ~1,600 | ~1,600 | ~36 | GATHERED |
| Abu Dhabi | #98 | ~800 | ~800 | ~33 | GATHERED |
| **TOTAL** | | **~18,210** | **~18,100** | **~530** | ALL GATHERED |

**Current**: ALL 15 cities gathered. Scraping phase: 2,361/18,210 at 344/min (~46 min remaining).
After scrape: auto-GPT-analyze → then Opus review new targets (only ones without `opus_verified_at`).

### Opus Verification Tracking (NEW)
- Added `opus_verified_at` column to `discovered_companies` table
- **4,120 targets** marked as Opus-verified in DB
- Future Opus reviews only check `WHERE is_target = true AND opus_verified_at IS NULL`
- No duplicate verification work

### Step 5: People search for ALL verified target companies — IN PROGRESS

**Running since**: 2026-03-22 05:20 UTC
**Script**: `find_contacts_v2.py` on Hetzner
**Progress**: 911/7,919 companies enriched (12%), 1,284 contacts found
**Rate**: 83 companies/min, ~84 min remaining
**Credits**: 1,284 used (of ~8,295 available)
**Avg contacts per company**: 1.41
**Method**: `apollo_service.enrich_by_domain(domain, limit=3, titles=[CEO,Founder,Co-Founder,Owner,COO,CFO,MD,Head of Finance,VP Ops,VP Finance,GM])`
**Storage**: contacts saved in `company_info.contacts` JSON on each `discovered_company`

### Step 5 (original): People search for ALL verified target companies (~4,000 credits)

**ONLY AFTER Opus review confirms targets.**

For each verified target company (expected ~4,000-5,000 total after all expansions):
1. Apollo People Search: filter by company domain + decision-maker titles
2. Titles priority: CEO > Founder > Co-Founder > COO > CFO > Head of Finance > Managing Director > VP Operations > Owner
3. Take top 3 contacts per company
4. Store: name, email, title, LinkedIn URL in DB
5. Cost: 1 credit per company (search returns up to 100 people, we pick 3)

| Metric | Value |
|--------|-------|
| Target companies (current) | ~3,142 |
| Expected from 4 new cities | ~600 |
| Expected from deep pagination | ~500 |
| Expected from new cities | ~1,000 |
| **Total expected targets** | **~5,000** |
| Credits for people search | **~5,000** |

**Optimization**: batch by city to reuse Apollo session. Search by domain, filter by title seniority.

### Step 6: Documentation & keyword analysis
- [ ] Keyword effectiveness report: target rate per keyword per city
- [ ] GPT prompt accuracy: total on all thousands
- [ ] City-by-city breakdown: targets, rates, segments
- [ ] Contact enrichment stats
- [ ] Blacklist documentation (how project-scoped blacklisting works)

---

## COMPLETED CITIES (before this blitz)

| City | Run IDs | Raw | Scraped | Targets | Credits |
|------|---------|-----|---------|---------|---------|
| Dubai (UAE) | 1-5, 54-55 | ~12,000 | ~8,000 | ~835 | 0 (Puppeteer) |
| New York | 56 | 2,061 | 1,244 | ~220 | 0 (Puppeteer) |
| Los Angeles | 58, 63 | 1,507 | 884 | ~130 | 0 (Puppeteer) |
| Miami | 75 | 783 | ~600 | ~60 | 34 |
| Riyadh | 76 | 1,139 | ~800 | ~100 | 33 |
| London | 77 | 2,326 | ~1,500 | ~250 | 44 |
| Singapore | 78 | 1,257 | ~900 | ~120 | 34 |
| Sydney | 79 | 1,782 | ~1,200 | ~160 | 37 |
| Austin | 80 | 1,165 | ~800 | ~100 | 34 |

## NEW CITIES (this blitz)

| City | Run ID | Raw | Unique | New | Credits | Status |
|------|--------|-----|--------|-----|---------|--------|
| Doha | 81 | 1,212 | 741 | 736 | 31 | SCRAPED + ANALYZING |
| Jeddah | 82 | 1,334 | 852 | 851 | 32 | SCRAPED + ANALYZING |
| Berlin | 83 | 1,681 | 1,322 | 1,316 | 33 | SCRAPED + ANALYZING |
| Amsterdam | 84 | 1,803 | 1,371 | 1,364 | 36 | SCRAPED + ANALYZING |

---
REREAD 
## KPIs

| # | KPI | Target | Current | Status |
|---|-----|--------|---------|--------|
| 1 | All target websites scraped | 0 remaining | 0 targets without text | ACHIEVED |
| 2 | All scraped analyzed by GPT | 0 remaining | ~1,200 pending (4 new cities) | IN PROGRESS |
| 3 | All GPT targets Opus-reviewed | 100% | ~600+ new pending | BLOCKED on Step 2 |
| 4 | GPT accuracy >= 90% | >= 90% | 95.1% on 2,782 | ACHIEVED (pending new) |
| 5 | Exhaust target cities | All done | 4 running + 15 planned | IN PROGRESS |
| 6 | 3 contacts per target | Coverage | NOT STARTED | BLOCKED on Step 5 |
| 7 | Keyword effectiveness doc | Report | NOT STARTED | BLOCKED on Step 6 |
| 8 | Blacklist vs campaigns | All checked | NOT STARTED | BLOCKED on Step 6 |
| 9 | Spend 9,149 credits efficiently | 0 remaining | ~132 spent | IN PROGRESS |

---

## BLACKLISTING (how it works)

**Built into the pipeline** at `gathering_service.run_blacklist_check()`:

1. **Data sources**: SmartLead campaigns (via API) + GetSales flows (via API)
2. **Materialized view**: `active_campaign_domains` — refreshed on startup + after each sync
3. **Project-scoped**: only campaigns from project 9 (EasyStaff Global) auto-reject
4. **Other projects**: show as warnings (different product = OK to contact same company)
5. **Enterprise blacklist**: `enterprise_blacklist.json` — permanently banned
6. **Result**: stored in `approval_gates` table with per-campaign rejection counts

**To run**: `POST /api/pipeline/gathering/runs/{id}/blacklist-check`

All data stored in DB: `gathering_runs`, `discovered_companies`, `analysis_results`, `approval_gates`, `company_source_links`.
