# Exploration Phase — Implementation Plan
**Date**: 2026-03-30
**Status**: Plan (not started)

## Current State

### What works ✅
- `filter_mapper.py` — generates initial Apollo filters from user query using taxonomy maps + embedding pre-filter
- `taxonomy_service.py` — stores 112 industries + 2,014 keywords + embeddings, provides similarity search
- `exploration_service.py` — searches Apollo, scrapes websites, classifies targets, enriches top 5
- `_pick_industries()` — separate gpt-4o-mini agent, 100% accuracy on 6 test segments
- `_gpt_pick_filters()` — picks keywords from embedding-ranked shortlist + size from offer
- `dispatcher.py` line 502 — `filter_mapper` is called when `tam_gather` has no explicit filters
- `dispatcher.py` line 846 — partial taxonomy update after exploration (buggy)

### What's broken/missing ❌

#### Gap 1: Taxonomy update from enrichment is buggy
**File**: `dispatcher.py:846-857`
**Problem**: Creates a NEW `TaxonomyService()` instance instead of using the singleton `taxonomy_service`. The new instance loads from disk, adds keywords, saves — but the singleton in memory still has the old data. Next query uses the stale singleton.
**Also**: Only adds `common_labels.keywords` (aggregated top keywords), not the FULL `keyword_tags` from each enriched company. Loses 80% of the vocabulary.
**Fix**:
```python
# Replace dispatcher.py:846-857 with:
from app.services.taxonomy_service import taxonomy_service
for enriched_company in exploration_result.get("enriched_companies", []):
    taxonomy_service.add_from_enrichment(enriched_company, segment=query)
await taxonomy_service.rebuild_embeddings_if_needed(openai_key)
```
**Requires**: `run_exploration()` must return `enriched_companies` (the full org data from enrichment, not just common_labels).

#### Gap 2: exploration_service doesn't return enriched company data
**File**: `exploration_service.py:68-73`
**Problem**: `_enrich_targets()` returns enriched data but `run_exploration()` only stores stats. The actual enriched org data (with keyword_tags) is lost after the function returns.
**Fix**: Add `enriched_companies` to the result dict:
```python
result["enriched_companies"] = [e.get("enriched", {}) for e in enriched]
```

#### Gap 3: Embeddings not rebuilt after enrichment
**File**: `taxonomy_service.py`
**Problem**: `add_from_enrichment()` adds keywords to the cache but new keywords have no embeddings. `rebuild_embeddings_if_needed()` exists but is never called from the pipeline.
**Fix**: Call it from dispatcher after taxonomy update (see Gap 1 fix).

#### Gap 4: _build_optimized_filters doesn't use taxonomy map
**File**: `exploration_service.py:303-370`
**Problem**: The filter optimizer selects keywords from enrichment data using GPT, but doesn't check if those keywords already exist in the taxonomy map. It also doesn't ADD newly discovered keywords from enrichment to the Apollo search — it only checks if they're "relevant to the segment."
**Fix**: After enrichment, the taxonomy map already has the new keywords. The optimized filters should be built by re-running `filter_mapper.map_query_to_filters()` — now with a richer keyword map (from enrichment). This replaces the custom `_build_optimized_filters()` entirely.
```python
# Instead of custom optimization:
# Step 1: enrich top 5 → taxonomy_service.add_from_enrichment()
# Step 2: rebuild embeddings
# Step 3: re-call filter_mapper.map_query_to_filters() → new shortlist includes enriched keywords
# The embedding pre-filter automatically picks up the new keywords
```

#### Gap 5: No iteration model in the pipeline
**File**: gathering models + gathering_service.py
**Problem**: No concept of iteration 1 (explore, draft filters) vs iteration 2 (scale, optimized filters) within a GatheringRun. The current pipeline does: gather → blacklist → scrape → analyze. There's no "gather again with better filters."
**Current workaround**: Dispatcher returns optimized filters and tells user to call `tam_gather` again manually. This works but is not automated.
**Design decision needed**: Two options:
  - **Option A**: Two separate GatheringRuns — run1 = exploration (25 companies), run2 = scale (optimized filters, 100+ companies). Simple, uses existing model.
  - **Option B**: Add `iteration` field to GatheringRun or create `PipelineIteration` model. More structured but requires migration.
**Recommendation**: Option A — simpler, no migration, exploration is just a small GatheringRun that feeds into the real one.

#### Gap 6: Apollo API key location in exploration_service
**File**: `exploration_service.py:95-118`
**Status**: Fixed on 2026-03-30 (switched from body to X-Api-Key header)
**But**: The test `test_e2e_real.py` has its own `apollo_search()` function that also uses the header. These should use the same code — currently duplicated.

---

## Implementation Order

### Phase 1: Wire the feedback loop (Gaps 1-4)
**Goal**: After exploration, new keywords flow into the shared map and improve the next query.
**Files to change**: `exploration_service.py`, `dispatcher.py`, `taxonomy_service.py`
**Test**: Run exploration for segment A → verify keyword map grew → run exploration for segment B → verify segment B's keyword shortlist includes keywords from segment A's enrichment.

#### 1.1 Return enriched companies from exploration (Gap 2)
```
exploration_service.py: add result["enriched_companies"]
```

#### 1.2 Fix taxonomy update in dispatcher (Gap 1)
```
dispatcher.py: use singleton taxonomy_service, add full enrichment data
```

#### 1.3 Rebuild embeddings after update (Gap 3)
```
dispatcher.py: call taxonomy_service.rebuild_embeddings_if_needed()
```

#### 1.4 Replace _build_optimized_filters with re-call to filter_mapper (Gap 4)
```
exploration_service.py: after enrichment, call map_query_to_filters() again
```

### Phase 2: Automate iteration 2 (Gap 5)
**Goal**: After exploration finishes, automatically launch the scale search with optimized filters.
**Approach**: Option A — exploration creates a small GatheringRun (25 companies), then automatically creates a second GatheringRun with optimized filters and higher max_pages.
**Files to change**: `dispatcher.py` (suggest_apollo_filters or tam_gather tool handler)

### Phase 3: Tests
**Goal**: Isolated tests for each step + full E2E test.
**Structure**:
```
tests/exploration/
  test_step1_initial_filters.py    ← golden validation (no API calls except GPT)
  test_step2_search_classify.py    ← real Apollo + scrape + classify
  test_step3_enrich_update.py      ← real enrichment + verify map grew + embeddings rebuilt
  test_step4_optimized_filters.py  ← re-run filter_mapper with enriched map → compare
  test_full_exploration.py         ← all steps + verify targets ≥30
```

---

## Detailed Changes Per File

### `exploration_service.py`
1. `run_exploration()` — add `result["enriched_companies"] = [e.get("enriched", {}) for e in enriched]`
2. Remove `_build_optimized_filters()` function entirely — replaced by re-calling `filter_mapper.map_query_to_filters()` after enrichment
3. `run_exploration()` — after enrichment, call:
   ```python
   from app.services.taxonomy_service import taxonomy_service
   for e in enriched:
       taxonomy_service.add_from_enrichment(e.get("enriched", {}), segment=query)
   await taxonomy_service.rebuild_embeddings_if_needed(openai_key)
   # Re-generate filters with enriched map
   from app.services.filter_mapper import map_query_to_filters
   optimized = await map_query_to_filters(query, offer_text, openai_key)
   result["optimized_filters"] = optimized
   ```

### `dispatcher.py`
1. Lines 846-857 — replace with:
   ```python
   from app.services.taxonomy_service import taxonomy_service
   enriched_companies = exploration_result.get("enriched_companies", [])
   for org in enriched_companies:
       taxonomy_service.add_from_enrichment(org, segment=project.target_segments or "")
   await taxonomy_service.rebuild_embeddings_if_needed(openai_key)
   ```

### `taxonomy_service.py`
1. `add_from_enrichment()` — already works, no changes needed
2. `rebuild_embeddings_if_needed()` — already works, just needs to be called
3. Consider: add a `last_updated` timestamp to the cache for debugging

### `filter_mapper.py`
1. No changes needed — it already uses the taxonomy_service singleton. When the map grows, the next call automatically benefits.

---

## Test-Driven Implementation

### For each phase, the flow is:
1. Write the test FIRST (expected inputs/outputs)
2. Run the test → it fails (feature not wired)
3. Wire the feature
4. Run the test → it passes
5. Run ALL tests → no regressions

### Step 1 test already exists (golden validation)
```python
# test_step1: verify industries + keywords match golden set
# Already passing: EasyStaff ✅, Fashion ✅, OnSocial ✅
```

### Step 3 test (KEY new test):
```python
async def test_enrich_updates_map():
    before = taxonomy_service.stats()["keywords"]

    # Simulate enrichment
    org = await apollo_enrich("synergybc.com")
    taxonomy_service.add_from_enrichment(org, "IT consulting")
    await taxonomy_service.rebuild_embeddings_if_needed(key)

    after = taxonomy_service.stats()
    assert after["keywords"] > before
    assert after["keywords_with_embeddings"] == after["keywords"]

    # Verify new keywords appear in shortlist
    shortlist = await taxonomy_service.get_keyword_shortlist("IT consulting", key)
    new_kw = org.get("keyword_tags", [])
    overlap = set(shortlist) & set(k.lower() for k in new_kw)
    assert len(overlap) > 0, "New keywords should appear in shortlist"
```

### Step 4 test (KEY new test):
```python
async def test_optimized_filters_use_enriched_keywords():
    # Generate initial filters
    r1 = await map_query_to_filters("IT consulting in Miami", "payroll", key)
    kw_before = set(r1["mapping_details"]["keywords_selected"])

    # Enrich 5 companies → update map
    for domain in ["synergybc.com", "koombea.com", ...]:
        org = await apollo_enrich(domain)
        taxonomy_service.add_from_enrichment(org, "IT consulting")
    await taxonomy_service.rebuild_embeddings_if_needed(key)

    # Re-generate filters (map is now richer)
    r2 = await map_query_to_filters("IT consulting in Miami", "payroll", key)
    kw_after = set(r2["mapping_details"]["keywords_selected"])

    new_keywords = kw_after - kw_before
    assert len(new_keywords) > 0, "Enrichment should add new keywords to filters"
```

---

## Credits Impact

No additional Apollo credits. The enrichment already happens in exploration (5 credits). We're just wiring the data from enrichment into the taxonomy map (free) and re-running the filter mapper (1 GPT call, ~$0.0003).

## Timeline Estimate
- Phase 1 (wire feedback loop): 4 changes across 3 files
- Phase 2 (automate iteration 2): 1 change in dispatcher
- Phase 3 (tests): 5 test files

All changes are wiring — no new algorithms, no new models, no new API calls.
