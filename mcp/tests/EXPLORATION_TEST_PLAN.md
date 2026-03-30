# Exploration Phase Test Plan

## Test Structure

```
tests/
├── EXPLORATION_TEST_PLAN.md          ← this file
├── HOW_TO_TEST.md                    ← existing, for conversation tests
│
├── exploration/                       ← NEW: isolated module tests
│   ├── test_step1_initial_filters.py  ← user query → Apollo filters (no API calls)
│   ├── test_step2_search_classify.py  ← filters → Apollo → scrape → classify (real API)
│   ├── test_step3_enrich_update.py    ← enrich targets → update keyword map → verify map grew
│   ├── test_step4_optimized_filters.py← improved filters → Apollo → higher target rate
│   └── test_full_exploration.py       ← all 4 steps end-to-end
│
├── conversations/                     ← existing: real MCP conversation tests
│   └── 01_new_user_easystaff.json     ← full user flow including exploration
│
└── tmp/                               ← test results with timestamps
    ├── GOLDEN_FILTERS.md              ← expected correct outputs
    └── suck.md                        ← what NOT to do
```

## Step 1: Initial Apollo Filters

**What**: user query + offer → industry selection + keyword selection + size + location
**Module**: `filter_mapper.py` (calls `_pick_industries` + `_gpt_pick_filters` + `_extract_locations`)
**Test type**: Isolated (calls GPT but NOT Apollo API)

### Input
```python
query = "IT consulting companies in Miami"
offer = "EasyStaff payroll platform"
```

### Expected output (from golden validation set)
```python
{
    "industries": ["information technology & services", "management consulting"],
    "keywords": ["it consulting", "technology consulting", "it services & it consulting", ...],
    "locations": ["Miami"],
    "employee_ranges": ["11,50", "51,200"],
}
```

### What to verify
- All industries exist in taxonomy map (no hallucinated values)
- All keywords exist in taxonomy map (except max 2 unverified for cold start)
- No broad catch-all industries (internet, information services)
- Golden must-have industries present
- Golden must-have keywords present
- Location extracted correctly
- Size ranges are valid Apollo values

### 3 test segments
1. EasyStaff IT consulting Miami → IT&S + management consulting
2. TFP Fashion brands Italy → apparel & fashion + luxury goods & jewelry
3. OnSocial Creator platforms UK → marketing & advertising

---

## Step 2: Apollo Search + Scrape + Classify

**What**: filters → real Apollo API → scrape websites → GPT classifies targets
**Module**: `exploration_service.py` (calls Apollo search, scraper, classifier)
**Test type**: Integration (real API calls, real scraping)

### Input
Step 1 output (the assembled filters)

### Expected output
```python
{
    "total_available": 3908,       # Apollo total
    "companies_returned": 25,       # first page
    "scraped": 11,                  # successful scrapes
    "targets": 6,                   # classified as target
    "target_rate": 0.55,            # targets / scraped
    "target_domains": ["synergybc.com", ...],
}
```

### What to verify
- Apollo returns >0 companies (filters are valid)
- Scraping succeeds for >50% of companies
- Target rate >30% (filters are relevant)
- Target domains are real companies matching the segment
- No competitors in targets (classification working)

### KPIs
- EasyStaff: ≥3 targets from 25 companies (≥20% rate)
- Fashion: ≥5 targets from 25 companies (≥30% rate)
- OnSocial: ≥2 targets from 25 companies (≥10% rate)

---

## Step 3: Enrich Top Targets + Update Map

**What**: top 5 target companies → Apollo enrichment → extract keywords/industry → update taxonomy map
**Module**: `taxonomy_service.py` + enrichment logic
**Test type**: Integration (real Apollo enrichment API)

### Input
Top 5 target domains from Step 2

### Expected output
```python
{
    "enriched": 5,
    "new_keywords_added": 50,       # new keyword tags discovered
    "new_industries_added": 0,      # usually 0 (we know most already)
    "keyword_map_before": 2014,
    "keyword_map_after": 2064,      # grew by ~50
    "embeddings_rebuilt": 50,       # new embeddings computed
}
```

### What to verify
- Enrichment API returns data for ≥3 of 5 domains
- New keywords are added to the map
- New keywords have embeddings computed (not None)
- Map is persisted (cache file updated)
- Subsequent keyword shortlist query finds the new keywords

### Critical test: does the map actually grow and persist?
```python
# Before enrichment
assert taxonomy_service.stats()["keywords"] == N

# Enrich
taxonomy_service.add_from_enrichment(org_data, "segment")
await taxonomy_service.rebuild_embeddings_if_needed(openai_key)

# After enrichment
assert taxonomy_service.stats()["keywords"] > N
assert taxonomy_service.stats()["keywords_with_embeddings"] == taxonomy_service.stats()["keywords"]
```

---

## Step 4: Optimized Filters + Re-search

**What**: original filters + enrichment data → GPT selects new keywords → improved filters → Apollo re-search
**Module**: `exploration_service.py` (filter optimizer) + `filter_mapper.py`
**Test type**: Integration (real API)

### Input
- Original filters from Step 1
- Enriched keyword data from Step 3
- User's segment query

### Expected output
```python
{
    "original_keyword_count": 7,
    "optimized_keyword_count": 12,  # added 5 from enrichment
    "added_keywords": ["managed services", "outsourcing", ...],
    "original_total_available": 3908,
    "optimized_total_available": 5200,  # more companies with better keywords
    "original_target_rate": 0.55,
    "optimized_target_rate": 0.60,      # same or higher
}
```

### What to verify
- Optimized filters have MORE keywords than original
- Added keywords are from enrichment (real Apollo tags, not GPT-invented)
- Apollo returns ≥ as many companies as original (broader search)
- Target rate stays same or improves (not worse)
- No tech stacks / irrelevant keywords added (via negativa filter working)

### The key comparison
```
Step 1 filters → Apollo → X targets at Y% rate
Step 4 filters → Apollo → X' targets at Y'% rate

Assert: X' >= X (more targets)
Assert: Y' >= Y * 0.8 (rate doesn't drop dramatically)
```

---

## Full Exploration E2E Test

Runs all 4 steps in sequence for each test segment. Logs everything to `tests/tmp/`.

```python
async def test_full_exploration(query, offer):
    # Step 1: Generate initial filters
    filters = await map_query_to_filters(query, offer, openai_key)
    log(filters)

    # Step 2: Search + scrape + classify
    companies = await apollo_search(filters)
    targets = await scrape_and_classify(companies, query, offer)
    log(targets)

    # Step 3: Enrich top 5 + update map
    map_before = taxonomy_service.stats()
    for domain in targets[:5]:
        org = await apollo_enrich(domain)
        taxonomy_service.add_from_enrichment(org, query)
    await taxonomy_service.rebuild_embeddings_if_needed(openai_key)
    map_after = taxonomy_service.stats()
    log(map_before, map_after)

    # Step 4: Optimize filters + re-search
    optimized = await optimize_filters(filters, enrichment_data, query, openai_key)
    companies2 = await apollo_search(optimized)
    targets2 = await scrape_and_classify(companies2, query, offer)
    log(targets2)

    # Verify improvement
    assert len(targets2) >= len(targets)
    assert map_after["keywords"] > map_before["keywords"]
```

---

## What's NOT wired yet (must be built)

1. **taxonomy_service.add_from_enrichment() not called from gathering_service.py** — enrichment happens but keywords aren't fed back to the map
2. **rebuild_embeddings_if_needed() not called after enrichment** — new keywords have no embeddings until explicitly triggered
3. **Step 4 (filter optimization) doesn't use taxonomy_service** — the exploration_service._build_optimized_filters() works independently from the shared map
4. **No "iteration" entity in the pipeline** — iteration 1 (explore) and iteration 2 (scale) not formalized

## Questions for user

1. Should iteration 1 (explore, 25 companies) and iteration 2 (scale, 100+ companies) be separate GatheringRuns or two iterations within one run?
2. Should the keyword map be per-user or global? Currently designed as global (all users benefit from each other's enrichments).
