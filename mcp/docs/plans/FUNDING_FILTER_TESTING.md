# Funding Filter Testing Plan

## Questions to Answer

### 1. Does funding filter break anything?
- Campaign 3118379 was gathered WITHOUT funding filter
- Need to test WITH funding filter and verify pipeline still completes
- Track: time, pages, credits, targets, people

### 2. Metrics to Track Per Run
- Pipeline duration (seconds)
- Apollo pages scraped
- Apollo credits: search (pages) + enrichment (people)
- Targets found
- People found
- KPI hit (yes/no)
- SmartLead campaign created (yes/no)

### 3. Industry-first vs Keywords-first with Funding
Compare two strategies (both with initial funding filter):
- **Strategy A**: Funded + Industry IDs → Funded + Keywords → All + Industry → All + Keywords → Regen
- **Strategy B**: Funded + Keywords → All + Keywords → Regen → Industry fallback

Which achieves default KPI (100 people) faster?

### 4. Exhaustion Detection for Prioritization Filters
Funding is a SOFT filter (prioritization, not mandatory). How does the system decide "exhausted"?

**Current implementation**: Same as any level — 10 consecutive empty pages = exhausted.
When Level 0 (funded) exhausts, the cascade drops the funding filter and continues with Level 1 (same keywords/industries, no funding).

**Difference from mandatory filters (geo, size)**:
- Geo/size: ALWAYS applied, never dropped
- Funding: applied at Level 0 only, dropped when exhausted
- Segments (keywords/industries): cascade through levels, regen keywords when exhausted

### 5. UI Visibility
The prioritization logic and applied filters must be shown in the pipeline page filters modal:
- Which strategy (industry-first / keywords-first)
- Whether funding filter is active (Level 0) or dropped (Level 1+)
- Current level in the cascade
- Pages fetched per level

---

## Test Plan

### Test 1: Fintech WITH Funding Filter
```
- Use same project (425) with exclusion list
- Add funding_stages: ["series_a", "series_b", "series_c", "series_d"] to filters
- Run pipeline
- Track all metrics
- Verify SmartLead campaign created
```

### Test 2: Compare Strategies
```
Run A: Industry-first + funding Level 0
Run B: Keywords-first + funding Level 0
Compare: time to KPI, pages used, credits spent
```

### Test 3: Exhaustion Cascade
```
- Monitor pipeline logs for level transitions
- Verify: L0 (funded) → exhausted → L1 (no funding) → continues
- Check that geo/size filters are NEVER dropped
```

### Test 4: Pipeline Page UI
```
- Check filters modal shows:
  - Strategy name
  - Funding filter status (active/dropped)
  - Current cascade level
  - Pages per level
```

---

## REAL Test Results (fresh Apollo search, 2026-04-02)

| Strategy | Companies/3pages | Total Avail | Credits | Time | Est. Credits to KPI |
|----------|-----------------|-------------|---------|------|---------------------|
| **Keywords + Funding** | **64** | 1,933 | 3 | 4.5s | **~103** |
| Keywords NO funding | 0 | 43,212 | 1 | — | ~440 (sparse) |
| **Industry + Funding** | **62** | 1,852 | 3 | 3.0s | **~105** |
| Industry NO funding | 0 | 93,120 | 1 | — | ~440 (sparse) |

### CRITICAL FINDING
**Funding filter FIXES Apollo's sparse pagination!** Without funding, Apollo returns 0 results per page despite 43K-93K total. With funding, returns 20+ per page. Funding is NOT optional — it's essential for Apollo to work.

### Winner
**Keywords + Funding** — marginally more companies (64 vs 62), est. 103 credits to KPI.
Both strategies very close with funding. Industry-first is 0.5s faster per batch.

### Exhaustion Cascade (with funding as Level 0)
```
L0: Keywords + Funding (Series A-D) → 1,933 companies pool → ~10 pages = ~200 companies
    If 10 consecutive empty = exhausted → drop funding:
L1: Keywords (no funding) → 43,212 pool BUT sparse pagination (0 per page!)
    This level will exhaust quickly (10 empty) → try regen:
L2: Regenerated keywords (no funding) → may find different pool
L3: Industry fallback (no funding) → 93,120 pool BUT also sparse

IMPORTANT: Level 0 (funded) is the ONLY level that gives good pagination.
If Level 0 exhausts, remaining levels likely produce very few companies.
The funded pool (1,933) should be enough for KPI in most cases.
```

---

## Answers (to be filled after testing)

### Was campaign 3118379 gathered without funding filter?
**YES** — Run 450 (and subsequent runs) used `filter_strategy: "keywords_first"` without `organization_latest_funding_stage_cd`. The funding filter was never applied.

### How does exhaustion work for funding (soft filter)?
The pipeline's `_feed_apollo_pages` runs levels sequentially:
1. Level 0: keywords + funding_stages → fetches pages → if 10 consecutive empty = exhausted
2. Level 1: keywords (NO funding) → fetches pages → same exhaustion detection
3. ...continues cascade

The exhaustion threshold (10 consecutive empty pages) is the SAME for all levels. When Level 0 exhausts, the pipeline doesn't fail — it just moves to Level 1 with the funding filter removed. Geo and size are ALWAYS in the payload at every level.

### Are filters shown in pipeline page UI?
**GAP**: The current pipeline page shows basic progress (targets, people, time) but does NOT show:
- Filter strategy name
- Current cascade level
- Funding filter status
- Pages per level breakdown

This needs to be added to the pipeline page.
