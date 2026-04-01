# Pipeline Specification — How It Must Work

## Overview

One pipeline run. One approval from user. Everything else is automatic.
Pipeline NEVER changes user's filters (location, size) without approval.

---

## Pre-Pipeline (User Approval Flow)

```
1. Probe Apollo: 1 page (per_page=100) = 1 credit
   Shows user:
   - Total companies in Apollo matching these filters (e.g. 8,127)
   - Total pages available (e.g. 82 pages)
   - Strategy: industry-first or keywords-first (and WHY)
   - ALL generated keywords (20+)
   - KPIs: 100 people, max 3/company
   - Estimated cost: 10 pages search + ~100 enrichment = ~$1.10
   - Pipeline link (pending_approval state)

2. User approves → pipeline starts automatically
```

---

## Pipeline Execution — Business Logic

### Step 1: Gather Companies (Apollo Search)
```
Fetch 10 pages in PARALLEL (10 concurrent requests)
  - per_page=100 → up to 1,000 companies
  - Dedup against project (skip already-known domains)
  - Save to DB immediately
  - Feed each company to scrape queue AS SOON AS fetched (don't wait for all 10 pages)
```

**Stats tracked:**
- Pages fetched: 10
- Apollo total_entries: 8,127 (how many Apollo says exist)
- Companies obtained: 306 (unique after dedup)
- Companies per page avg: 30.6

### Step 2: Scrape Websites (100 concurrent)
```
Each company from scrape_queue → Apify residential proxy → get website text
  - Timeout: 15s per site
  - Retry: 3 attempts with backoff
  - Success: save scraped_text (up to 50K chars) → feed to classify queue
  - Fail: mark scrape_failed, skip to next
  - NO WAITING: each scraped site goes to classifier IMMEDIATELY
```

**Stats tracked:**
- Scraped: 216/306 (70%)
- Failed: 90 (site down, blocked, timeout)

### Step 3: Classify Targets (100 concurrent)
```
Each scraped company → GPT-4o-mini:
  - Input: company name + domain + first 3000 chars of website text
  - Context: user's offer description
  - Output: is_target (true/false) + segment + reasoning
  - Target → feed to people queue IMMEDIATELY
  - Not target → mark rejected, skip
```

**Stats tracked:**
- Classified: 216
- Targets: 173 (80% target rate)
- Rejected: 43

### Step 4: Extract People (20 concurrent)
```
Each target company → Apollo people search:
  - Seniority filter: owner, founder, c_suite, vp, head, director (FREE)
  - Returns 4-25 candidates per company
  - Rank by: seniority match + role match to target_roles
  - Top 3 → bulk_match for email enrichment (1 credit each)
  - Only verified emails kept
  
KPI CHECK after each company's people saved:
  - If total_people >= 100 → KPI MET → stop pipeline → push to SmartLead
```

**Stats tracked:**
- People found: 86 (from 173 targets)
- Credits: 86 enrichment + 10 search = 96 total
- Companies with 0 contacts: 87 (Apollo has no verified emails for them)

---

## When KPI Not Met — Exhaustion Cascade

All within the SAME user-approved filters (location, size NEVER changed).

### Level 1: Primary Strategy (up to 25 pages)
```
A11 classifier chose industry-first or keywords-first.
NEVER combine industry + keywords in same API call (Apollo ANDs them → zero results).

Industry-first: use industry_tag_ids ONLY → fetch up to 25 pages
  - 25 pages × 100/page = up to 2,500 companies
  - 2 consecutive EMPTY pages (0 new after dedup) = this strategy exhausted
  - Move to Level 2

Keywords-first: use keywords ONLY → same logic, up to 25 pages
```

### Level 2: Backlog Strategy (up to 25 pages)
```
Switch to the OTHER approach (sequential, not parallel — saves credits):
  - Was industry → now keywords ONLY (drops industry_tag_ids)
  - Was keywords → now industry ONLY (drops keyword_tags)
  
Different API call = different companies. No AND logic.
Up to 25 more pages. Total so far: max 50 pages.
```

### Level 3: Regenerate Keywords (up to 5 cycles × 20 pages)
```
GPT generates 20 NEW keywords (excluding all previously tried).
Search with new keywords ONLY → fetch up to 20 pages per cycle.
If 0 new companies after 20 pages → regenerate again.
Max 5 regeneration cycles.
Total max: 50 + 100 = 150 pages absolute maximum.
```

### Level 5: Exhausted — Report to User
```
Pipeline marks "insufficient" with clear stats:
  - "86/100 people found. Apollo exhausted for these filters."
  - "173 target companies found but only 86 have verified email contacts."
  - "Suggestion: broaden to [Europe] or increase size to [1-500]"
  - Send what was gathered to SmartLead anyway.
  
User can then:
  - Accept 86 people
  - Adjust filters and re-run
  - Increase max_people_per_company from 3 to 5
```

---

## Parallelization — How Speed Works

```
Time 0s:   Apollo fetches 10 pages IN PARALLEL (10 concurrent)
Time 1s:   Page 1 returns 100 companies → immediately sent to scrape queue
           Pages 2-10 still loading
Time 1.5s: Scraper starts on first 100 companies (100 concurrent HTTP)
Time 2s:   Pages 2-10 return → 200 more companies sent to scrape queue
Time 3s:   First 20 websites scraped → sent to classifier
           Scraper working on remaining 280
Time 4s:   First 10 companies classified → 7 are targets → sent to people queue
           Classifier working on remaining scraped sites
Time 5s:   People search starts for first 7 targets (20 concurrent)
           Scraper/classifier still processing in parallel
Time 10s:  ~100 scraped, ~50 classified, ~15 targets, ~10 people found
Time 20s:  ~200 scraped, ~150 classified, ~100 targets, ~40 people found
Time 35s:  ~216 scraped, ~173 targets, ~86 people found
Time 40s:  Phase 2 starts (if KPI not met) — fetches more Apollo pages
           New companies flow through same scrape→classify→people pipeline

EVERYTHING OVERLAPS. No phase waits for another.
```

### Concurrency limits:
- Apollo page fetch: 10 parallel (rate limited)
- Website scraping: 100 concurrent (Apify proxy)
- GPT classification: 100 concurrent (gpt-4o-mini)
- People search: 20 concurrent (Apollo rate limit)
- DB writes: each worker uses OWN session (no conflicts)

---

## SmartLead Auto-Push

When pipeline completes (KPI met OR insufficient with contacts):
1. Generate email sequence via GPT
2. Create SmartLead campaign (DRAFT)
3. Upload all contacts with verified emails
4. Connect pre-selected email accounts
5. Set timezone from target geography
6. Notify user via Telegram + MCP

---

## Stats Shown in Pipeline UI

```
Header:
  RUNNING / COMPLETED / INSUFFICIENT badge
  People: 86/100 (86%) [progress bar]
  Companies: 173/34 target companies [progress bar]
  Time: 35s elapsed
  Credits: 96 used

Apollo Stats (new — must add):
  Total in Apollo: 8,127 companies matching filters
  Pages available: 82
  Pages fetched: 10
  Companies obtained: 306 (unique)

Scrape Stats:
  Scraped: 216/306 (70%)
  Failed: 90

Classification Stats:
  Targets: 173/216 (80% target rate)
  Rejected: 43

People Stats:
  With contacts: 86/173 targets (50%)
  Total people: 86
  Credits used: 96
```

---

---

## Apollo API Fields — Tested Results

### Endpoint: POST /api/v1/mixed_companies/search

### Company Search Fields (what we send):

| Field | What it does | Target rate | Volume | Used? |
|-------|-------------|-------------|--------|-------|
| `organization_industry_tag_ids` | Filter by Apollo's industry taxonomy IDs (e.g. "5567cd82..." = apparel & fashion) | **90%** | 100/page, best pagination | **YES — primary strategy** |
| `q_organization_keyword_tags` | Filter by keyword tags on company profile (e.g. "fashion brand italy") | **10-40%** | Inconsistent pagination | **YES — backup strategy** |
| `organization_keywords` | USELESS — Apollo ignores this field entirely | 0% | 0 | **NO — tested, broken** |
| `q_organization_name` | Text search by company name | N/A | OK pagination | **NO — too specific** |
| `organization_locations` | Filter by geography (e.g. ["Italy"]) | N/A | Narrows | **YES — always applied** |
| `organization_num_employees_ranges` | Filter by company size (e.g. ["1,200"]) | N/A | Narrows | **YES — always applied** |
| `organization_latest_funding_stage_cd` | Filter by funding stage | N/A | Narrows | **Optional** |

### CRITICAL RULE: Never combine `organization_industry_tag_ids` + `q_organization_keyword_tags`
Apollo treats all filter types as AND (intersection). Combining industry + keywords gives near-zero results.
Always use ONE OR THE OTHER per API call.

### Test Results (TFP Fashion Italy, 5 pages each):

| Approach | Field Used | Companies | Target Rate | Credits |
|----------|-----------|-----------|-------------|---------|
| A1: Industry IDs | `organization_industry_tag_ids` | 201 | **90%** | 5 |
| A2: Single keyword | `q_organization_keyword_tags: ["fashion design"]` | 261 | 10% | 5 |
| A3: Multi keyword | `q_organization_keyword_tags: ["fashion", "luxury"]` | 72 | 26% | 5 |
| A6: Parallel keywords | Multiple calls with different keywords | 336 | 15% | 12 |
| A8: Broad keywords | `q_organization_keyword_tags: ["apparel & fashion", ...]` | 22 | 10% | 5 |

**Winner: industry_tag_ids (A1)** — 9x better target rate than keywords.

### How Industry Tag IDs Work:
1. Apollo has ~112 industry categories, each with a hex ID
2. We maintain `apollo_industry_map` DB table (79 entries) mapping names → IDs  
3. A11 classifier (GPT) decides if user's query maps to a SPECIFIC industry or is too BROAD
4. Specific → use industry_tag_ids (90% target rate)
5. Broad → use keyword_tags (10-40% target rate, but more flexible)

### How Keyword Tags Work:
1. Filter mapper generates 20-30 keywords from user's query via GPT
2. Keywords matched against Apollo's taxonomy DB (2,356 known tags)
3. Unverified keywords added if < 20 verified ones found
4. Keywords search company PROFILES — what companies tag themselves as
5. Less precise than industry IDs but covers niche segments industry doesn't

### People Search Fields:

| Field | What it does | Used? |
|-------|-------------|-------|
| `person_seniorities` | Filter by seniority level (owner, c_suite, vp, director) | **YES — always** |
| `person_titles` | Filter by exact title — USELESS, returns 0-1 per company | **NO — tested, broken** |
| `q_organization_domains` | Search people at specific company domain | **YES — per target** |

**People search is FREE** (no credits). Only `bulk_match` for email enrichment costs 1 credit/person.

---

## What Must NEVER Happen
- Pipeline NEVER changes user's location filter without approval
- Pipeline NEVER changes user's company size filter without approval
- Pipeline NEVER asks questions during execution
- Pipeline NEVER blocks waiting for user input after approval
- Pipeline NEVER uses shared DB session across workers
- Pipeline NEVER skips website scraping (every company must be scraped before classification)
- Classification NEVER uses Apollo industry label (it's always wrong)
