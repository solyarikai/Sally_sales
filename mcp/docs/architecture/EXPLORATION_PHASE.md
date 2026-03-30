# Exploration Phase Architecture

> User prompt → Apollo filters → search → scrape → classify → enrich → optimize → scale

## What This Does

Takes a user query like "IT consulting in Miami" and finds 30+ target companies from Apollo, ready for outreach. The exploration phase generates optimal Apollo search filters, not by guessing, but by using Apollo's own vocabulary.

## Proven Results (E2E test, 2026-03-30)

| Segment | Apollo total | Target rate | Targets found |
|---------|-------------|-------------|---------------|
| EasyStaff IT consulting Miami | 3,908 | 55% | 6/11 |
| TFP Fashion brands Italy | 18,394 | 100% | 7/7 |
| OnSocial Creator platforms UK | 16,676* | 50% | 5/10 |

*After fixing broad industry filters (was 46,942 with "internet" noise).

## 3 Maps — The Foundation

Apollo accepts ONLY specific values for its filters. No random strings. The system maintains maps of known valid values:

| Map | Size | Source | Storage |
|-----|------|--------|---------|
| **Industries** | 112+ | apollo_taxonomy.json, extended via enrichment | JSON file |
| **Keywords** | 2,014+ (growing) | Extracted from enriched company profiles | JSON + numpy embeddings |
| **Employee ranges** | 8 fixed | Apollo documentation | Hardcoded |
| Locations | No map needed | Apollo normalizes internally ("UK" = "United Kingdom") | — |

### Apollo API behavior (tested, 23 API calls)

- **Keywords = OR**: adding more keywords INCREASES results
- **Size = AND**: narrows results (ranges within size are OR)
- **Industry names work as keyword tags**: "information technology & services" returns 8.5x more than "IT consulting"
- **Search results DON'T return keyword/industry fields**: only enrichment (1 credit) reveals them
- **Location format doesn't matter**: "UK" = "United Kingdom" = same results

## Agent Chain

```
User: "Gather IT consulting in Miami and video production in London"
                              │
                              ▼
                 ┌──────────────────────┐
                 │  INTENT SPLITTER     │  gpt-4o-mini
                 │  Split into segments │
                 └──────┬────────┬──────┘
                        │        │
           ┌────────────┘        └────────────┐
           ▼                                   ▼
   Segment 1: "IT consulting, Miami"    Segment 2: "video production, London"
           │                                   │
           ▼ (same chain per segment)          ▼

    ┌────────────────────────────────────────────────┐
    │  STEP A: EMBEDDING PRE-FILTER (no GPT)         │
    │                                                │
    │  Embed user query → cosine similarity against  │
    │  2,014 keyword embeddings in map               │
    │  → top 50 most relevant keywords               │
    │                                                │
    │  Scales to any map size (pgvector-ready)        │
    │  Cost: $0.00002 per query                      │
    └────────────────────┬───────────────────────────┘
                         │
                         ▼
    ┌────────────────────────────────────────────────┐
    │  STEP B1: INDUSTRY SELECTION (gpt-4.1-mini)    │
    │  Separate focused call                         │
    │                                                │
    │  Input: query + offer + 112 industries         │
    │  Prompt: exclusion-first                       │
    │   "Eliminate wrong industries, then pick 2-4   │
    │    most directly relevant. Exclude generic     │
    │    catch-alls unless segment IS about them."   │
    │                                                │
    │  Output: ["marketing & advertising",           │
    │           "media production", "online media"]  │
    │                                                │
    │  Accuracy: 100% on all 3 test segments         │
    │  Tested: 20 model×prompt combos                │
    └────────────────────┬───────────────────────────┘
                         │
                         ▼
    ┌────────────────────────────────────────────────┐
    │  STEP B2: KEYWORDS + SIZE (gpt-4.1-mini)       │
    │                                                │
    │  Input: query + offer + 50 keyword shortlist   │
    │         + 8 employee ranges                    │
    │                                                │
    │  Keywords: picks from pre-filtered shortlist   │
    │  (real Apollo tags, not invented)              │
    │  Size: infers from offer text                  │
    │                                                │
    │  Cold start: if keyword map has <5 matches,    │
    │  GPT suggests "unverified" keywords (max 2)    │
    └────────────────────┬───────────────────────────┘
                         │
                         ▼
    ┌────────────────────────────────────────────────┐
    │  STEP C: LOCATION EXTRACTION (no GPT)          │
    │  Regex: "in Miami" → ["Miami"]                 │
    │  Handles multi-geo: "UAE and Saudi"            │
    └────────────────────┬───────────────────────────┘
                         │
                         ▼
    ┌────────────────────────────────────────────────┐
    │  STEP D: FILTER ASSEMBLER (no GPT)             │
    │                                                │
    │  q_organization_keyword_tags =                 │
    │    B1.industries + B2.keywords                 │
    │                                                │
    │  organization_locations = C.locations           │
    │  organization_num_employees_ranges = B2.ranges  │
    │                                                │
    │  Validation:                                   │
    │   - ≥1 industry in keyword_tags                │
    │   - all industries exist in map                │
    │   - all keywords exist in map (except max 2    │
    │     unverified for cold start)                 │
    └────────────────────┬───────────────────────────┘
                         │
                         ▼
    ┌────────────────────────────────────────────────┐
    │  ITERATION 1: EXPLORE (7 credits)              │
    │                                                │
    │  1. Apollo search with assembled filters (1cr) │
    │  2. Scrape top 15 websites (free, httpx+Apify) │
    │  3. Classify targets (gpt-4o-mini, via negativa│
    │     96% accuracy, exclude non-targets)         │
    │  4. Enrich top 5 targets (5 credits)           │
    │     → extract REAL keyword_tags + industry     │
    │     → UPSERT into taxonomy map (grows it)      │
    │  5. Filter optimizer (gpt-4o-mini)             │
    │     → select enriched keywords to ADD          │
    │     → via negativa: keep industry terms,       │
    │       exclude tech stacks                      │
    └────────────────────┬───────────────────────────┘
                         │
                         ▼
    ┌────────────────────────────────────────────────┐
    │  ITERATION 2: SCALE (1-4 credits)              │
    │                                                │
    │  Apollo search with optimized filters           │
    │  Multiple pages until ≥30 target companies      │
    │  Scrape all + classify all                      │
    │  Target rate should be higher than iteration 1  │
    └────────────────────┬───────────────────────────┘
                         │
                         ▼
    ┌────────────────────────────────────────────────┐
    │  PEOPLE ENRICHMENT (free)                      │
    │  Apollo mixed_people/search per target company │
    │  3 contacts per company, C-level default       │
    │  ≥100 contacts for campaign                    │
    └────────────────────┬───────────────────────────┘
                         │
                         ▼
    ┌────────────────────────────────────────────────┐
    │  SMARTLEAD CAMPAIGN                            │
    │  Create campaign + generate sequence            │
    │  + assign email accounts + send test email      │
    │  + wait for operator approval                   │
    └────────────────────────────────────────────────┘
```

## Self-Growing Keyword Map

Every enrichment call (5 per exploration run) extracts 10-50 real keyword tags from Apollo company profiles. These are UPSERTED into the shared taxonomy map.

```
Run 1 (cold start):  0 keywords → enrichment → +300 keywords
Run 2:             300 keywords → enrichment → +200 keywords
Run 3:             500 keywords → enrichment → +150 keywords
...
Run 20:          2,000 keywords → covers most B2B verticals
```

After seeding with 15 companies across 3 segments: **2,014 keywords** in the map.

New users benefit from previous users' enrichment. The map is shared across all users.

## Credit Budget Per Segment

| Phase | Action | Credits |
|-------|--------|---------|
| Iteration 1 | Apollo search (25 companies) | 1 |
| Iteration 1 | Enrich top 5 targets | 5 |
| Iteration 2 | Apollo search optimized (1-4 pages) | 1-4 |
| People | mixed_people/search | FREE |
| **TOTAL** | | **7-10** |

## Models Used

| Step | Model | Why | Cost |
|------|-------|-----|------|
| Intent splitting | gpt-4o-mini | Simple parsing task | $0.15/1M |
| Industry selection | gpt-4.1-mini | 100% accuracy, tested 20 combos | $0.40/1M |
| Keyword + size | gpt-4.1-mini | Picks from pre-filtered shortlist | $0.40/1M |
| Classification | gpt-4o-mini | Via negativa, 96% accuracy | $0.15/1M |
| Filter optimization | gpt-4o-mini | Keyword filtering after enrichment | $0.15/1M |
| Embeddings | text-embedding-3-small | Keyword pre-filter | $0.02/1M |

Total GPT cost per segment: ~$0.003

## Files

| File | Purpose |
|------|---------|
| `backend/app/services/filter_mapper.py` | Steps A-D: embedding pre-filter → GPT picker → assembler |
| `backend/app/services/taxonomy_service.py` | Self-growing keyword/industry map with embeddings |
| `backend/app/services/exploration_service.py` | Iteration 1: search → scrape → classify → enrich |
| `backend/app/services/offer_analyzer.py` | Employee size inference from offer text |
| `backend/app/services/intent_parser.py` | Intent splitting (multi-segment detection) |
| `apollo_filters/apollo_taxonomy.json` | 112 Apollo industry names (seed) |
| `apollo_filters/apollo_taxonomy_cache.json` | Growing keyword/industry map (metadata) |
| `apollo_filters/apollo_embeddings.npz` | Keyword embeddings (numpy, 5.3MB) |

## Test Results

All test results in `tests/tmp/` with timestamps. Key files:
- `GOLDEN_FILTERS.md` — expected correct filters per segment
- `APOLLO_FILTER_FINDINGS.md` — real Apollo API behavior (23 calls)
- `suck.md` — what NOT to do (test real pipeline, not GPT output format)
- `*_e2e_real.json` — full E2E results with real Apollo + scrape + classify
- `*_industry_selection.json` — 20 model×prompt combos for industry step
