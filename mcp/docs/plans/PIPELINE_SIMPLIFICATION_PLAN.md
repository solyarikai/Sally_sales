# Pipeline Simplification Plan

**Date**: 2026-04-01
**Goal**: Remove deprecated exploration phase, simplify to single-iteration pipeline, optimize people search

---

## Current Flow (overcomplicated)

```
Iteration 1: 1 page (25 companies) → scrape → classify → exploration (enrich top 5, 5 credits)
  → optimize filters → improved GPT prompt
Iteration 2+: 4 pages with optimized filters → scrape → classify → extract people
  → loop until KPI
```

**Problems:**
- Exploration phase costs 5 credits for enrichment
- Filter optimization rarely helps (we now use industry_tag_ids from DB map)
- GPT prompt improvement from 1 page of data is unreliable
- Adds ~30s latency before real gathering starts

## Proposed Flow (simplified)

```
Single flow: 10 pages (up to 1000 companies) → scrape → classify → extract people
  → if KPI not met → 10 more pages → scrape → classify → extract more people
  → loop until KPI
```

**Why this is better:**
- No enrichment phase (0 credits saved, industry_tag_ids from DB map)
- GPT prompt quality comes from user feedback loop, not auto-tuning
- Faster: skip 30s exploration overhead
- Simpler: one iteration type, not exploration + scale

## People Search: Bulk vs Per-Company

### Current: Per company, sequential-ish (20 concurrent semaphore)
```python
for company in targets:
    people = await apollo.enrich_by_domain(company.domain, limit=3)
```

### Question: Can we use organization_ids in bulk?
Apollo /mixed_people/api_search accepts `q_organization_domains` as a single domain.
Does NOT appear to accept arrays or organization_ids for bulk search.

BUT: we already run 20 concurrent searches (semaphore=20). Each search is:
- 1 FREE API call (seniority search, per_page=25)
- 1 PAID bulk_match call (3 person IDs, 3 credits)

For 34 target companies:
- 34 seniority searches (FREE, 20 concurrent = ~2 seconds total)
- 34 bulk_match calls (3 IDs each = 102 credits, 20 concurrent = ~2 seconds total)
- Total: ~4 seconds for people extraction

### Can bulk_match be further optimized?
Yes — instead of 34 separate bulk_match calls (3 IDs each), we could:
1. Collect ALL person IDs from 34 seniority searches
2. Send ONE bulk_match with all ~102 IDs
3. Map results back to companies

This reduces 34 API calls to 1, saving ~3 seconds of network overhead.
BUT: need to handle Apollo's batch limits (unknown max per call).

### Test plan:
- Test bulk_match with 10 IDs → works?
- Test bulk_match with 50 IDs → works?
- Test bulk_match with 100 IDs → works?
- Compare timing: 34 calls × 3 IDs vs 1 call × 102 IDs

## Exploration Phase: What to Keep, What to Remove

### KEEP:
- Apollo industry map in DB (78 entries, auto-extends) — essential for filter strategy
- A11 industry specificity classifier — routes to industry or keywords
- pgvector keyword embeddings in taxonomy — may be useful later
- User feedback → tam_re_analyze flow — this IS the quality improvement mechanism

### REMOVE:
- Automatic exploration after iteration 1 (enrich top 5, optimize filters)
- The `skip_exploration` flag — no exploration to skip
- Exploration service calls from orchestrator

### KEEP BUT SIMPLIFY:
- Orchestrator: single iteration type, 10 pages, no exploration branch
- Filter strategy decision happens BEFORE gathering (in filter_mapper + A11)
- GPT prompt comes from project knowledge + offer, not from enrichment

## User Feedback for GPT Quality

Instead of auto-tuning from exploration, quality comes from:
1. **User reviews targets at CP2** → provides feedback → tam_re_analyze
2. **User's agent (Opus) reviews targets** → MCP provides website URLs for verification
3. **MCP shows target list with reasoning** → user says "this is wrong" → feedback loop

### For Opus agent verification:
MCP should provide in pipeline_status / checkpoint responses:
- Target company domains (for scraping)
- GPT classification reasoning per company
- So that user's Opus agent can independently verify quality

## Pipeline Timing Budget (target)

| Phase | Target | Notes |
|-------|--------|-------|
| Filter discovery | 3s | filter_mapper + A11 + Apollo probe |
| Gathering (10 pages) | 5s | Parallel page fetches |
| Scraping | 30s | 50 concurrent, Apify proxy |
| Classification | 10s | 50 concurrent GPT-4o-mini |
| People extraction | 5s | 20 concurrent seniority search + 1 bulk_match |
| **Total** | **~55s** | Down from 148s |

Main savings: drop exploration (30s), optimize people extraction (60s → 5s with bulk_match).

## Action Items

1. [ ] Remove exploration phase from orchestrator
2. [ ] Test bulk_match with 100 IDs in one call
3. [ ] Implement: collect all person IDs → single bulk_match → map back
4. [ ] Set default to 10 pages from first iteration (no 1-page exploration)
5. [ ] Run full E2E test on Fashion Italy with simplified pipeline
6. [ ] Compare: timing, credits, target quality vs previous approach
7. [ ] Verify results with Opus

## Questions / Considerations

1. **Should we keep industry map enrichment on new companies?**
   Yes — but as a side effect during pipeline, not as a blocking exploration phase.
   When we scrape + classify companies, if we find a new industry not in the map,
   we can enrich ONE company to get the tag_id and add it. No need for "top 5" enrichment.

2. **What about the filter optimization from exploration?**
   Now handled by the industry map + A11 classifier. No runtime optimization needed.
   If user says "wrong companies" → they adjust filters via feedback, not auto-exploration.

3. **Bulk people search across multiple companies?**
   Apollo's /mixed_people/api_search only accepts single domain per call.
   Can't bulk search across companies. But can parallelize heavily (20-50 concurrent).
   The bulk optimization is on the enrichment side (bulk_match), not search side.
