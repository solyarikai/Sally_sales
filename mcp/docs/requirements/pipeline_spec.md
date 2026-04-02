# Pipeline Specification — How It Must Work

## Overview

One pipeline run. One approval from user. Everything else is automatic.
Pipeline NEVER changes user's filters (location, size) without approval.

---

## Pre-Pipeline (User Approval Flow)

```
1. Probe Apollo: 1 page (per_page=100) = 1 credit
   - Gets total_entries (e.g. 8,127) and total_pages (e.g. 82)
   - Gets 100 companies from page 1 — SAVED to DB immediately
   - These 100 companies are REUSED when pipeline starts (not thrown away)
   
   Shows user:
   - Total companies in Apollo matching these filters (e.g. 8,127)
   - Total pages available (e.g. 82 pages)
   - Strategy: keywords + industry in parallel (both always used)
   - ALL generated keywords (from document extraction or filter_mapper)
   - KPIs: 100 people, max 3/company
   - Estimated cost: 10 pages search + ~100 enrichment = ~$1.10
   - Pipeline link (pending_approval state, already shows 100 probe companies)

2. User approves → pipeline starts automatically
```

---

## Pipeline Execution — Business Logic

**ONE PIPELINE. Probe data reused. Everything overlaps.**

### Step 1: Pipeline starts — probe companies + Apollo pages IN PARALLEL
```
Immediately on user approval:
  - 100 probe companies (already in DB) → fed to scrape queue INSTANTLY
  - Scraping starts on probe companies while Apollo fetches pages 2-10
  - Apollo fetches pages 2-10 in parallel (10 concurrent)
  - Each page's companies → fed to scrape queue AS THEY ARRIVE
  - Scraping, classification, people extraction all running simultaneously

Timeline:
  0s: 100 probe companies start scraping (100 concurrent)
  1s: Apollo pages 2-10 requested in parallel
  2s: First 20 probe sites scraped → classification starts
  3s: Pages 2-5 return → 400 more companies fed to scrape queue
  4s: First 10 classifications done → 7 targets → people search starts
  5s: Pages 6-10 return → scraper has 300+ in queue
  
NOTHING WAITS. Probe data gives 2-3 second head start on scraping.
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

## When KPI Not Met — Parallel Streams + Regen

All streams launch simultaneously. No sequential fallback — maximum parallelism.
`_kpi_met` flag stops everything when target reached.

### Phase 1: All Streams in Parallel (via asyncio.gather)

4 streams launch at once — funded and unfunded, keywords and industry:

| Stream | Apollo Filter | Pages | Purpose |
|--------|-------------|-------|---------|
| L0_kw_funded | keywords + funding + geo + size | 25 | Best companies: funded + keyword match |
| L0_ind_funded | industry + funding + geo + size | 25 | Highest target rate (90%) + funded |
| L1_keywords | keywords + geo + size (no funding) | 25 | Full keyword pool without funding restriction |
| L1_industry | industry + geo + size (no funding) | 25 | Full industry pool without funding restriction |

Each stream stops independently when:
- 10 consecutive Apollo-empty pages (stream exhausted), OR
- `_kpi_met = True` (people_worker hit 100 people), OR
- max_pages (25) reached

All 4 run simultaneously via `asyncio.gather(*streams)`.
Total: up to 100 pages in ~30-60 seconds.

### Phase 2: Keyword Regeneration (only if KPI not met after Phase 1)

Sequential — each cycle uses previous results to avoid keyword duplication:
```
for cycle in range(1, 6):
    GPT generates 20-30 NEW keywords (excluding all previously tried)
    Each cycle: up to 20 pages, stop on 10 consecutive empty
    if _kpi_met: break
Max 5 cycles = up to 100 more pages
```

### Exhaustion Detection
```
10 consecutive pages where Apollo returns 0 organizations = stream exhausted.
NOT 0 after dedup — Apollo itself returns nothing = pool truly empty.
10 is safe because Apollo pagination is inconsistent (sometimes 0 on one
page then results on the next).
```

### What's HARD vs SOFT
- **Geo + Size: HARD** — never dropped, applied to ALL streams always
- **Funding: SOFT** — applied to L0 streams only. L1 streams run without it simultaneously.
- **Keywords vs Industry: both always run** — no classifier decides which goes first

### No Classifier Needed for Strategy
Both keywords AND industry streams always run in parallel.
The A11 classifier's "industry_first" vs "keywords_first" label is informational
only — shown in the UI filters modal but does NOT change execution order.
Industry IDs always resolved from filter_mapper (even if classified as "too broad").
Keywords always available from document extraction or filter_mapper.

### Max Pages Per Pipeline Run
```
Phase 1: 4 × 25 = 100 pages (parallel)
Phase 2: 5 × 20 = 100 pages (regen, sequential)
Total maximum: ~200 pages = ~200 credits ($2.00 search)
Typical run hits KPI in 30-50 pages.
```

---

## Industry Map — Building the Full 112

### Current State — MAP IS COMPLETE
```
Apollo has 112 industry NAMES in their taxonomy.
But many names share the same underlying tag_id:
  - "banking" + "financial services" + "capital markets" → same tag_id
  - "entertainment" + "music" + "computer games" → same tag_id
  - "cosmetics" + "health, wellness & fitness" → same tag_id

Our map has 79 unique tag_ids — this IS the full set.
Verified by enriching companies from "missing" industries: 
all resolved to tags already in our map.
```

### How the 79 Were Built
```
Method: /organizations/bulk_enrich endpoint
  - Called during pipeline runs when companies are enriched
  - Each enriched company returns industry_tag_id (singular field)
  - _extend_industry_map() auto-saves new tag_id → industry_name mappings
  - Accumulated 79 unique tags over multiple pipeline runs

The map continues to auto-extend during normal usage.
No manual backfill needed — 79 tags covers all 112 industry names.
```

### How Industry Lookup Works
```
1. User query: "fashion brands in Italy"
2. A11 classifier: maps to "apparel & fashion"
3. DB lookup: SELECT tag_id FROM apollo_industry_map WHERE industry_name = 'apparel & fashion'
4. Found: tag_id = '5567cd82736964540d0b0000'
5. Apollo search: organization_industry_tag_ids = ['5567cd82736964540d0b0000']
6. Result: 90% target rate
```

---

## MCP-Specific Implementation — Methods to Call

**CRITICAL: The MCP streaming pipeline must use its OWN Apollo service directly.
NEVER import from main app's `GatheringService` or its adapter pattern.**

### Apollo Search (per page)
```python
# In streaming_pipeline.py — use self.apollo directly
data = await self.apollo.search_organizations(
    keyword_tags=keywords,           # OR industry_tag_ids (NEVER both)
    industry_tag_ids=industry_ids,   # 
    num_employees_ranges=emp_ranges, # ALWAYS applied
    locations=locations,             # ALWAYS applied if user specified
    latest_funding_stages=funding,   # Level 0 priority (dropped when exhausted)
    page=page_num,
    per_page=100,
)
orgs = data.get("organizations", [])
total = data.get("pagination", {}).get("total_entries", 0)
```

### Apollo Search (multi-page parallel)
```python
# Fetches up to max_pages in parallel batches of batch_size
all_orgs = await self.apollo.search_organizations_all_pages(
    keyword_tags=keywords,
    num_employees_ranges=emp_ranges,
    latest_funding_stages=funding,
    max_pages=25,
    per_page=100,
    batch_size=10,  # 10 pages fetched in parallel
)
```

### People Enrichment
```python
# FREE search by seniority
search_data = await self.apollo._api_call("POST", "/mixed_people/api_search", {
    "q_organization_domains": domain,
    "person_seniorities": ["owner", "founder", "c_suite", "vp", "head", "director"],
    "page": 1, "per_page": 25,
})

# PAID enrichment (1 credit per person)
enriched = await self.apollo.enrich_people_emails(people_ids)
```

### Company Enrichment (for seed-based search)
```python
data = await self.apollo.enrich_organization(domain)
# Returns: industry, industry_tag_id, estimated_num_employees, etc.
```

### What NOT to use
```
NEVER: from app.services.gathering_service import GatheringService
NEVER: svc._get_adapter(source_type)
NEVER: adapter.gather(filters)

These are main app code. MCP pipeline uses self.apollo directly.
```

### Funding Filter in Parallel Streams
```
Funding is applied to L0 streams, NOT to L1 streams.
Both run simultaneously — no sequential "drop funding when exhausted":

  L0_kw_funded:  keywords + funding + geo + size → 25 pages (parallel)
  L0_ind_funded: industry + funding + geo + size → 25 pages (parallel)
  L1_keywords:   keywords + geo + size            → 25 pages (parallel)
  L1_industry:   industry + geo + size            → 25 pages (parallel)

Funding narrows Apollo results = funded companies first (higher quality).
Unfunded streams run at the same time = full pool coverage.

Geo + size are HARD (always applied, never dropped).
Funding is a quality filter, not a gate.
```

### Exhausted — All Streams + Regen Done, KPI Not Met
```
Pipeline marks "completed" (not "insufficient" — always show as completed).
Auto-pushes whatever was gathered to SmartLead.

Message to user:
  - "{N}/100 people found. All Apollo streams exhausted for these filters."
  - "{T} target companies found, {P} have verified email contacts."
  - Auto-pushed to SmartLead DRAFT with {P} leads.
  
User can then:
  - Accept what was gathered
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

### Concurrency Limits (max concurrent requests):

| Service | Max Concurrent | Why this limit |
|---------|---------------|----------------|
| Apollo page fetch | 10 parallel | Rate limited, 1 credit/page |
| Apify website scraping | **100 concurrent** | Residential proxy, no rate limit |
| OpenAI classification | **100 concurrent** | gpt-4o-mini, high rate limit |
| Apollo people search | 20 concurrent | Seniority search is FREE but rate limited |
| Apollo bulk_match (email) | 20 concurrent | 1 credit/person, rate limited |
| DB writes | unlimited | Each worker uses OWN session (no conflicts) |

All limits enforced via `asyncio.Semaphore(N)` per worker.

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
  RUNNING / KPI MET / COMPLETED badge
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
3. Filter mapper resolves industry names → tag_ids (ALWAYS included, never blocked)
4. Industry stream runs in parallel with keywords stream — both always active
5. Industry gives 90% target rate; keywords gives 10-40% but covers niche segments

### How Keyword Tags Work:
1. Filter mapper generates 20-30 keywords from user's query via GPT
2. Keywords matched against Apollo's taxonomy DB (2,356 known tags)
3. Unverified keywords added if < 20 verified ones found
4. Keywords search company PROFILES — what companies tag themselves as
5. Less precise than industry IDs but covers niche segments industry doesn't

### People Extraction — Detailed Flow Per Target Company

```
For each target company (e.g. agnona.com):

Step 1: FREE search — POST /mixed_people/api_search
  Payload: {q_organization_domains: "agnona.com", person_seniorities: ["owner","founder","c_suite","vp","head","director"], per_page: 25}
  Returns: 3-25 people with partial profiles (name, title, seniority)
  Cost: FREE (0 credits)

Step 2: Filter has_email=true only
  Apollo marks which people have email in their database
  Typically 30-60% of results have email

Step 3: Rank by seniority + role match
  Priority: owner > founder > c_suite > vp > head > director
  Boost: if title matches target_roles from offer analysis (e.g. "Head of E-commerce")

Step 4: Take top 3 (max_people_per_company default)

Step 5: Bulk email enrichment — POST /people/bulk_match
  Payload: {details: [{id: "person_id_1"}, {id: "person_id_2"}, {id: "person_id_3"}]}
  Returns: verified emails for each person
  Cost: 1 credit per person = 3 credits per company
  THIS is a BULK endpoint — sends all 3 IDs in ONE API call, not 3 separate calls

Step 6: RETRY if <3 verified emails returned
  If bulk_match returns <3 verified:
    - Go back to Step 3 candidates (25 total from seniority search)
    - Pick NEXT best candidates that match target_roles (skip already tried)
    - Prioritize by role match: exact title match > seniority match > any
    - bulk_match the next batch (up to 3 more)
    - Repeat until 3 verified OR all candidates exhausted
  
  Selection priority for retry:
    1. Exact target_role title match (e.g. "VP Sales" when doc says VP Sales)
    2. Same seniority level but different title (e.g. "VP Revenue" when doc says VP Sales)
    3. Lower seniority with exact role match (e.g. "Director of Sales")
    4. Skip: never enrich someone with no role relevance
  
  Cost: worst case 6-9 credits per company (2-3 retry rounds)
  But: each company reliably produces 3 contacts → fewer companies needed for KPI
```

### People Search Fields:

| Field | What it does | Used? |
|-------|-------------|-------|
| `person_seniorities` | Filter by seniority level (owner, c_suite, vp, director) | **YES — always** |
| `person_titles` | Filter by exact title — USELESS, returns 0-1 per company | **NO — tested, broken** |
| `q_organization_domains` | Search people at specific company domain | **YES — per target** |

**People search (`/mixed_people/api_search`) is FREE** (0 credits).
**Email enrichment (`/people/bulk_match`) costs 1 credit/person** — bulk endpoint, one call per company.

### Email Verification Logic
```
Step 2 filter: has_email=true (from FREE search)
  Apollo docs: "has_email indicates whether Apollo has a VERIFIED email"
  BUT: bulk_match may return email_status != "verified" (guessed/unavailable)

Step 5 filter: email_status == "verified" (from bulk_match response)
  ONLY verified emails are saved to DB and count toward KPI.
  Unverified/guessed emails are DROPPED — never sent to SmartLead.

KPI counts ONLY verified email contacts.
```

### What "20 concurrent people" means:
```
20 target companies processed IN PARALLEL, each running the 5-step flow above.
  - Step 1 (FREE search): 20 parallel HTTP calls to /mixed_people/api_search
  - Step 5 (bulk_match): 20 parallel HTTP calls to /people/bulk_match
  
NOT 20 individual person lookups. Each of the 20 parallel calls handles
one COMPANY (up to 3 people per company in a single bulk_match call).

Why 20 and not 100: Apollo rate limits on /people/bulk_match are stricter
than on /mixed_people/api_search. 20 concurrent avoids 429 errors.
```

---

---

## All OpenAI API Calls — Models & Purposes

### Pipeline Calls (during execution)

| # | Where | Model | Purpose | Tokens | Cost/call |
|---|-------|-------|---------|--------|-----------|
| 1 | streaming_pipeline.py (classifier) | **gpt-4o-mini** | Classify company as target/rejected from scraped website | ~800 in, ~50 out | ~$0.0003 |
| 2 | streaming_pipeline.py (regen keywords) | **gpt-4.1-mini** | Generate 20 fresh keywords when strategy exhausted | ~500 in, ~300 out | ~$0.0004 |

### Pre-Pipeline Calls (during setup)

| # | Where | Model | Purpose | Tokens | Cost/call |
|---|-------|-------|---------|--------|-----------|
| 3 | dispatcher.py (create_project) | **gpt-4.1-mini** | Extract offer/value prop/target roles from website | ~2000 in, ~500 out | ~$0.001 |
| 4 | dispatcher.py (confirm_offer feedback) | **gpt-4.1-mini** | Re-analyze offer based on user feedback | ~1500 in, ~500 out | ~$0.001 |
| 5 | filter_mapper.py (pick_industries) | **gpt-4.1-mini** (fallback: gpt-4o-mini) | Select 2-3 matching Apollo industries from 112 | ~300 in, ~100 out | ~$0.0002 |
| 6 | filter_mapper.py (map_filters) | **gpt-4.1-mini** (fallback: gpt-4o-mini) | Pick 20-30 keywords + employee size ranges | ~800 in, ~400 out | ~$0.0005 |
| 7 | industry_classifier.py (A11) | **gpt-4.1-mini** | Label strategy (informational only — both always run in parallel) | ~300 in, ~50 out | ~$0.0002 |
| 8 | people_mapper.py (infer_people_filters) | **gpt-4o-mini** | Infer target roles/seniorities from offer | ~300 in, ~100 out | ~$0.0002 |

### Embedding Calls

| # | Where | Model | Purpose |
|---|-------|-------|---------|
| 9 | taxonomy_service.py | **text-embedding-3-small** | Embed query for pgvector keyword similarity search |

### Sequence Generation (post-pipeline)

| # | Where | Model | Purpose |
|---|-------|-------|---------|
| 10 | campaign_intelligence.py | **gpt-4o** (fallback: gpt-4o-mini) | Generate email sequence (3-5 steps) personalized by geo/segment |

### Prompt Tuning (manual)

| # | Where | Model | Purpose |
|---|-------|-------|---------|
| 11 | prompt_tuner.py | **gpt-4.1-mini** | Auto-tune classification prompt from mismatches |

### Total OpenAI Cost Per Pipeline Run (typical 300 companies)
```
Classification: 300 × $0.0003 = ~$0.09
Keyword regen: 0-5 × $0.0004 = ~$0.002
Filter mapping: 1 × $0.0007 = ~$0.001
Sequence gen: 1 × $0.01 = ~$0.01
Total: ~$0.10 per pipeline run
```

---

## What Must NEVER Happen
- Pipeline NEVER changes user's location filter without approval
- Pipeline NEVER changes user's company size filter without approval
- Pipeline NEVER asks questions during execution
- Pipeline NEVER blocks waiting for user input after approval
- Pipeline NEVER uses shared DB session across workers
- Pipeline NEVER skips website scraping (every company must be scraped before classification)
- Classification NEVER uses Apollo industry label (it's always wrong)
