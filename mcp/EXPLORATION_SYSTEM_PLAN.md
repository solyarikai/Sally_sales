# God-Level MCP Exploration System — Plan v2

## KPI
**Maximize target companies at the end of the pipeline.**
Target company = company that would BUY our product, confirmed by website analysis.

More promising companies in the initial Apollo search → more targets after scrape+classify → more contacts → better campaign.

---

## Lessons (suck.md + real API tests)

1. Never test GPT output in isolation. Test real Apollo results + real scraping + real classification.
2. Apollo filters have FIXED vocabularies. Passing GPT-invented values = 0 results or wrong results.
3. Industry names as keyword tags give 8.5x more results than specific terms.
4. Keywords are OR (more = broader). Size is AND (narrows). Location is AND (narrows).
5. Search results DON'T include keywords/industry fields. Only enrichment reveals them (1 credit each).
6. The keyword map is the #1 gap — we don't know Apollo's keyword vocabulary.

---

## 3 Maps = The Foundation

Everything depends on knowing Apollo's EXACT vocabulary. No guessing. No GPT hallucinations.

### Map 1: Industries (classification)
- **Type**: Fixed closed list
- **Current state**: 112 known values in `apollo_taxonomy.json`
- **Apollo probably has**: ~200-300 total
- **How to complete**: Every enrichment returns `industry` field → add to map if new
- **Storage**: `apollo_taxonomy` table, `type='industry'`
- **GPT task**: Pick 2-4 from the list. Pure classification. Zero hallucination risk.

### Map 2: Keywords (the big one)
- **Type**: Semi-controlled vocabulary, thousands of values
- **Current state**: EMPTY — we have 0 known Apollo keyword tags
- **How to build**: Every enrichment returns `keyword_tags` array (5-20 tags per company)
- **Growth rate**: 5 enrichments × 10 unique tags = ~50 new keywords per exploration run
- **After 20 runs**: ~500-1000 keywords covering major segments
- **Storage**: `apollo_taxonomy` table, `type='keyword'`, with `segments[]` tracking which business segments this keyword appeared for
- **GPT task**: Pick keywords from the map that match user's segment. If map has <10 matches for this segment, GPT can suggest new ones (flagged as "unverified").
- **Cold start problem**: First run for a brand new segment has no keyword map → must rely on industry names (which always work) + GPT's best guesses for keywords

### Map 3: Employee Ranges (trivial)
- **Type**: Fixed, 8 values
- **Current state**: COMPLETE
- **Values**: `1,10 | 11,50 | 51,200 | 201,500 | 501,1000 | 1001,5000 | 5001,10000 | 10001,`
- **GPT task**: Pick 1-3 ranges based on offer text. Already works (offer_analyzer.py).

### Location: No map needed
- Apollo normalizes internally. "UK" = "United Kingdom" = same results.
- Simple extraction from query. Rules/regex, no GPT needed for the mapping itself.

---

## Critical Optimization: What Goes Into Apollo's `q_organization_keyword_tags`?

This is the ONLY filter that controls which companies we find (location and size just narrow the geo/size, they don't change the business segment).

**The array sent to Apollo should contain:**
1. **Industry names** (from Map 1) — broad, 8-50x more results than specific keywords, guaranteed to exist in Apollo
2. **Known keyword tags** (from Map 2) — precise, proven to exist in Apollo, directly match company profiles
3. **NO GPT-invented keywords** unless the map has <10 matches for this segment (cold start fallback)

**Why this order matters:**
- Industry names cast the wide net (e.g., "information technology & services" = 17K companies)
- Known keywords add precision within that net (e.g., "it services & it consulting" specifically matches consulting firms)
- Together via OR = maximum coverage of relevant companies

**Why GPT-invented keywords are dangerous:**
- "IT consulting" (GPT guess) → 2,063 results
- "it services & it consulting" (actual Apollo tag) → probably much more
- GPT doesn't know Apollo's exact vocabulary → suboptimal or zero matches

---

## Agent Chain — v2

```
User: "Gather IT consulting in Miami and video production in London"
                              │
                              ▼
              ┌───────────────────────────────┐
              │  AGENT 0: Intent Splitter      │  gpt-4o-mini
              │                                │
              │  Input: raw user message        │
              │  Output: [                      │
              │    {segment: "IT consulting",   │
              │     geo: "Miami"},              │
              │    {segment: "video production",│
              │     geo: "London"}              │
              │  ]                              │
              │                                │
              │  Simple. One task. Parse query  │
              │  into segments + geo.           │
              └──────────┬───────┬──────────────┘
                         │       │
            ┌────────────┘       └────────────┐
            ▼                                  ▼
    SEGMENT 1 CHAIN                    SEGMENT 2 CHAIN
    (runs in parallel)                 (runs in parallel)
            │                                  │
            ▼                                  ▼

        PER-SEGMENT FILTER MAPPING
        ───────────────────────────

              ┌───────────────────────────────┐
              │  STEP A: EMBEDDING PRE-FILTER  │  no GPT
              │  (runs before GPT agent)       │
              │                                │
              │  1. Embed user query with      │
              │     OpenAI text-embedding-3    │
              │     (cheap: $0.02/1M tokens)   │
              │                                │
              │  2. Compare against ALL keyword │
              │     embeddings in DB            │
              │     (pre-computed, stored in    │
              │      apollo_taxonomy table     │
              │      as pgvector column)       │
              │                                │
              │  3. Take top 30-50 nearest     │
              │     keywords by cosine         │
              │     similarity                 │
              │                                │
              │  Result: shortlist of 30-50    │
              │  keywords that are semantically │
              │  closest to the user's query.  │
              │  Works at any map size          │
              │  (5K, 50K keywords — same       │
              │   speed via pgvector index).    │
              │                                │
              │  Industries: 112 is small,      │
              │  always send full list.         │
              │  No pre-filter needed.          │
              └──────────────────┬──────────────┘
                                 │
                                 ▼
              ┌───────────────────────────────┐
              │  STEP B: GPT FILTER MAPPER     │  gpt-4o-mini
              │  ONE agent, structured output  │
              │                                │
              │  Input:                        │
              │   - segment query              │
              │   - offer text                 │
              │   - INDUSTRY MAP (112 items,   │
              │     full list — always fits)   │
              │   - KEYWORD SHORTLIST (30-50   │
              │     items, pre-filtered by     │
              │     embedding similarity)      │
              │   - EMPLOYEE RANGES (8 fixed)  │
              │                                │
              │  Prompt:                        │
              │   "You map business queries to  │
              │    Apollo.io search filters.    │
              │    Select ONLY from the lists   │
              │    provided. Never invent.      │
              │                                │
              │    STEP 1 — INDUSTRIES          │
              │    Pick 2-4 from this list:     │
              │    [112 industries]             │
              │                                │
              │    STEP 2 — KEYWORDS            │
              │    Pick 3-7 from this list:     │
              │    [30-50 pre-filtered keywords]│
              │    These are real Apollo tags    │
              │    ranked by relevance to your  │
              │    query. Pick the best matches.│
              │    If none match, you may       │
              │    suggest up to 2 new ones     │
              │    (mark as unverified).        │
              │                                │
              │    STEP 3 — EMPLOYEE SIZE       │
              │    Pick 1-3 ranges based on     │
              │    the offer:                   │
              │    [8 fixed ranges]             │
              │                                │
              │    Return JSON:                 │
              │    {industries: [...],          │
              │     keywords: [...],            │
              │     unverified_keywords: [...], │
              │     employee_ranges: [...]}     │
              │   "                             │
              │                                │
              │  Total prompt: ~800 tokens.     │
              │  GPT picks from small lists.    │
              │  No attention problems.         │
              │  No hallucination.              │
              └──────────────────┬──────────────┘
                                 │
                                 ▼
              ┌───────────────────────────────┐
              │  STEP C: LOCATION EXTRACTOR    │  no GPT
              │  Regex/rules from query         │
              │  "in Miami" → ["Miami"]         │
              │  "in UAE and Saudi" →            │
              │    ["United Arab Emirates",      │
              │     "Saudi Arabia"]              │
              └──────────────────┬──────────────┘
                                 │
                                 ▼
              ┌───────────────────────────────┐
              │  STEP D: FILTER ASSEMBLER      │  no GPT
              │                                │
              │  q_organization_keyword_tags =  │
              │    StepB.industries             │  ← broad net (2-4)
              │    + StepB.keywords             │  ← precision (3-7)
              │    + StepB.unverified_keywords  │  ← cold start (0-2)
              │                                │
              │  organization_locations =       │
              │    StepC.locations              │
              │                                │
              │  organization_num_employees_    │
              │  ranges =                       │
              │    StepB.employee_ranges        │
              │                                │
              │  VALIDATION:                   │
              │   - ≥1 industry in keyword_tags│
              │   - location non-empty         │
              │   - size non-empty             │
              │   - all industries exist in map│
              │   - all keywords exist in map  │
              │     (except unverified, max 2) │
              └──────────────────┬──────────────┘
                                 │
                                 ▼

        EXPLORATION PHASE (Iteration 1)
        ────────────────────────────────

              ┌───────────────────────────────┐
              │  APOLLO SEARCH (1 credit)      │
              │  25 companies returned          │
              │                                │
              │  Log: exact filters sent,       │
              │  total_available, companies     │
              └──────────────────┬──────────────┘
                                 │
                                 ▼
              ┌───────────────────────────────┐
              │  SCRAPE TOP 15 (free)          │
              │  httpx + Apify proxy           │
              │  BeautifulSoup extraction      │
              └──────────────────┬──────────────┘
                                 │
                                 ▼
              ┌───────────────────────────────┐
              │  CLASSIFY TARGETS              │
              │  gpt-4o-mini, via negativa     │
              │  v9 prompt (96% accuracy)      │
              │                                │
              │  Output: X/15 targets          │
              │  Target rate = X/15            │
              └──────────────────┬──────────────┘
                                 │
                                 ▼
              ┌───────────────────────────────┐
              │  ENRICH TOP 5 TARGETS          │
              │  5 credits                     │
              │                                │
              │  For each enriched company:    │
              │   → extract keyword_tags[]     │
              │   → extract industry           │
              │   → extract sic_codes[]        │
              │   → UPSERT into apollo_taxonomy│
              │     table (shared, permanent)  │
              │                                │
              │  THIS IS WHERE THE MAP GROWS.  │
              │  Every enrichment teaches us   │
              │  Apollo's real vocabulary.     │
              └──────────────────┬──────────────┘
                                 │
                                 ▼
              ┌───────────────────────────────┐
              │  FILTER OPTIMIZER (gpt-4o-mini)│
              │                                │
              │  Input:                        │
              │   - original keyword_tags      │
              │   - NEW keywords from enriched │
              │     companies (real Apollo     │
              │     vocabulary, just learned)  │
              │   - segment query              │
              │                                │
              │  Task: Which new keywords to   │
              │  ADD? Via negativa — exclude    │
              │  tech stacks, keep industry    │
              │  terms.                        │
              │                                │
              │  Output: optimized keyword_tags│
              │  (original + selected new ones)│
              └──────────────────┬──────────────┘
                                 │
                                 ▼

        SCALE PHASE (Iteration 2)
        ──────────────────────────

              ┌───────────────────────────────┐
              │  APOLLO SEARCH WITH OPTIMIZED  │
              │  FILTERS                       │
              │                                │
              │  Multiple pages until ≥30      │
              │  target companies found        │
              │  (= ≥100 contacts at 3/co.)   │
              │                                │
              │  Cost: 1-4 credits             │
              └──────────────────┬──────────────┘
                                 │
                                 ▼
              ┌───────────────────────────────┐
              │  SCRAPE ALL + CLASSIFY ALL     │
              │  gpt-4o-mini via negativa      │
              │                                │
              │  Target rate measured           │
              │  30+ targets confirmed          │
              └──────────────────┬──────────────┘
                                 │
                                 ▼
              ┌───────────────────────────────┐
              │  USER REVIEW (Opus/Claude Code)│
              │                                │
              │  If accuracy < 95%:            │
              │   → feedback adjusts prompt    │
              │   → re-classify                │
              │   → loop until aligned         │
              │                                │
              │  If target rate too low:       │
              │   → adjust Apollo keywords     │
              │   → re-search with new filters │
              │   → new iteration              │
              └──────────────────┬──────────────┘
                                 │
                                 ▼
              ┌───────────────────────────────┐
              │  PEOPLE ENRICHMENT             │
              │  Apollo people search (FREE)   │
              │  3 contacts per target company │
              │  C-level (or offer-adjusted)   │
              └──────────────────┬──────────────┘
                                 │
                                 ▼
              ┌───────────────────────────────┐
              │  SMARTLEAD CAMPAIGN            │
              │  Create + sequence + accounts  │
              │  + test email + approve        │
              └──────────────────────────────┘
```

---

## Why ONE Agent for Filter Mapping (not 3 separate)

Considered splitting into 3 agents (industry picker, keyword picker, size picker). Decided against:

1. **Coherence**: Industry + keyword selection must be coherent. If industry = "marketing & advertising", keywords should be marketing-related. Separate agents might produce contradictory outputs.
2. **Context**: The offer text informs ALL three choices. "Payroll platform" → size=10-200, industry=IT, keywords=consulting. One prompt with full context makes better joint decisions.
3. **Latency**: 1 API call vs 3.
4. **Structured output**: One prompt with "STEP 1... STEP 2... STEP 3..." forces sequential reasoning within a single call. Each step has its own constrained list. No hallucination because every value comes from a provided list.

**The key constraint**: GPT SELECTS from provided lists, never INVENTS. The prompt includes the complete industry map and relevant keyword map from DB. If it's not in the list, it can't be in the output (except cold-start unverified keywords, which are explicitly flagged).

---

## Cold Start Strategy

First run for a brand new segment where keyword map has 0 matches:

1. **Industries still work** — 112 industry names always available, guaranteed results
2. **GPT generates "unverified" keywords** — best guesses, clearly flagged
3. **Iteration 1 enrichment** — 5 credits → reveals 30-50 real keyword tags → map populated
4. **Iteration 2 uses real keywords** — from enrichment, not GPT guesses
5. **Future runs for similar segments** — map already populated, no cold start

After ~20 exploration runs across different segments, the keyword map covers most B2B verticals. New users benefit from previous users' enrichment data.

---

## apollo_taxonomy Table Schema

```sql
CREATE TABLE apollo_taxonomy (
    id SERIAL PRIMARY KEY,
    type VARCHAR(20) NOT NULL,          -- 'industry' | 'keyword' | 'employee_range'
    value VARCHAR(200) NOT NULL,         -- exact Apollo string
    embedding vector(1536),              -- OpenAI text-embedding-3-small vector
    apollo_result_count INT,             -- last known count from Apollo search
    seen_on_companies INT DEFAULT 1,     -- how many enriched companies had this tag
    segments TEXT[],                      -- which user segments this appeared for
    verified BOOLEAN DEFAULT TRUE,       -- false for GPT-guessed keywords not yet confirmed
    first_seen TIMESTAMP DEFAULT NOW(),
    last_seen TIMESTAMP DEFAULT NOW(),
    UNIQUE(type, value)
);

-- pgvector index for fast similarity search on keywords
CREATE INDEX idx_taxonomy_embedding ON apollo_taxonomy
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 20);

-- Seed: 112 industries + 8 employee ranges (embed on insert)
-- Grows: every enrichment call UPSERTs keyword_tags + industry + computes embedding
```

### Embedding flow:
1. On INSERT/UPDATE of a keyword: call OpenAI `text-embedding-3-small` ($0.02/1M tokens, ~$0.00002 per keyword)
2. Store 1536-dim vector in `embedding` column
3. On user query: embed the query → `SELECT * FROM apollo_taxonomy WHERE type='keyword' ORDER BY embedding <=> query_embedding LIMIT 50`
4. pgvector handles the similarity search — works at any scale

### Cost of embeddings:
- 5000 keywords × ~5 tokens each = 25K tokens = $0.0005 total to embed entire map
- Each user query = 1 embedding call = ~10 tokens = $0.0000002
- Negligible. Not even worth tracking.

---

## Credit Budget Per Segment

| Phase | Action | Credits |
|-------|--------|---------|
| Iteration 1 | Apollo search (1 page, 25 co.) | 1 |
| Iteration 1 | Enrich top 5 targets | 5 |
| Iteration 2 | Apollo search optimized (1-4 pages, 25-100 co.) | 1-4 |
| People | mixed_people/search | FREE |
| **TOTAL** | | **7-10** |

---

## What Gets Logged (every run, to files)

```
{timestamp}_exploration_{segment}.json:
{
  "segment": "IT consulting Miami",
  "offer": "EasyStaff payroll...",

  "agent1_output": {
    "industries_selected": ["information technology & services", ...],
    "keywords_selected": ["it services & it consulting", ...],
    "unverified_keywords": [],
    "employee_ranges": ["11,50", "51,200"],
    "source_maps": {
      "industry_map_size": 112,
      "keyword_map_matches": 47
    }
  },

  "filters_sent_to_apollo": {
    "q_organization_keyword_tags": [...exact array sent...],
    "organization_locations": ["Miami"],
    "organization_num_employees_ranges": ["11,50", "51,200"]
  },

  "iteration_1": {
    "total_available": 2063,
    "returned": 25,
    "scraped": 12,
    "targets": 8,
    "target_rate": "67%",
    "target_domains": ["synergybc.com", ...],
    "enrichment": {
      "new_keywords_discovered": ["it services & it consulting", "managed services", ...],
      "new_industries_discovered": [],
      "keywords_added_to_map": 23
    }
  },

  "optimized_filters": {
    "added_keywords": ["managed services", "outsourcing"],
    "removed_keywords": []
  },

  "iteration_2": {
    "total_available": 3408,
    "pages_searched": 2,
    "total_companies": 50,
    "scraped": 45,
    "targets": 31,
    "target_rate": "69%",
    "credits_used": 2
  },

  "total_credits": 8,
  "total_targets": 31,
  "total_contacts_expected": 93
}
```

---

## Test Plan (E2E only, no isolated bullshit)

One test function. Runs full chain. Measures target companies found.

```
test_e2e("IT consulting in Miami", "EasyStaff payroll") → assert targets >= 30
test_e2e("Fashion brands in Italy", "TFP resale")       → assert targets >= 30
test_e2e("Creator platforms in UK", "OnSocial data API") → assert targets >= 20
```

Each test logs everything above to `tests/tmp/{timestamp}_{segment}.json`.

No fake ground truth. No GPT-output-format checks. The test either finds 30+ target companies through real Apollo + real scraping + real classification, or it fails.
