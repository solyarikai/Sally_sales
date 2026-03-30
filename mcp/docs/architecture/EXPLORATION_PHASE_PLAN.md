# Exploration Phase Plan — God-Level Apollo Filter Optimization

## Proven Results (test_exploration_quality.py)

| Metric | Result |
|---|---|
| Initial search | 25 companies (1 credit) |
| Website scraping | 12/15 scraped (free via Apify) |
| Target classification | **75% conversion rate** (9/12 targets by GPT-4o-mini) |
| Enrichment | 5 targets enriched → discovered 15 common keywords |
| Optimized search | **96 companies** with new filters (4 credits) |
| **Total Apollo credits** | **10** (1 search + 5 enrich + 4 full search) |
| **Estimated targets** | **~72 companies** |
| **Estimated contacts** | **~216** (3 per company) |

## Architecture

```
User query: "IT consulting in Miami, 10-200 employees"
                    ↓
┌─── ITERATION 1: EXPLORATION (shown in pipeline as "Draft Filters") ───┐
│                                                                         │
│  1. Size inference (GPT-4o-mini) → 10-200 from EasyStaff offer          │
│  2. Initial Apollo search (1 credit, 25 companies)                      │
│  3. Scrape top 15 websites (free, Apify proxy)                          │
│  4. GPT-4o-mini classifies: pick top 5 definite targets                 │
│  5. Apollo enrich 5 targets (5 credits) → extract ALL labels            │
│  6. Reverse engineer: common industries, keywords, SIC codes            │
│  7. Build optimized filters (add discovered labels)                     │
│                                                                         │
│  Shows in pipeline UI as Iteration 1: "Exploration (draft filters)"     │
│  Companies visible, classified, but labeled as exploration phase        │
└─────────────────────────────────────────────────────────────────────────┘
                    ↓
┌─── ITERATION 2: FULL PIPELINE (optimized filters) ────────────────────┐
│                                                                         │
│  8. Full Apollo search with optimized filters (4 credits, ~100 cos)     │
│  9. Blacklist check (exclude companies from user's campaigns)           │
│  10. Scrape ALL company websites (Apify batch, free)                    │
│  11. GPT-4o-mini via negativa analysis → targets + segments             │
│  12. Opus QA verification (agent reviews targets for accuracy)          │
│                                                                         │
│  Shows in pipeline UI as Iteration 2: "Full Pipeline (optimized)"       │
│  This is the main run — targets from here go to SmartLead               │
└─────────────────────────────────────────────────────────────────────────┘
                    ↓
┌─── PEOPLE SEARCH ──────────────────────────────────────────────────────┐
│                                                                         │
│  13. Apollo people search for target companies (C-level default)         │
│      - GPT-4o-mini adjusts role filters based on offer                  │
│      - Up to 3 contacts per company                                     │
│  14. Contacts added to CRM + SmartLead campaign                         │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Credit Budget

| Step | Credits | Description |
|---|---|---|
| 1. Size inference | 0 | GPT-4o-mini (OpenAI key) |
| 2. Initial search | 1 | Apollo companies search (25 results) |
| 3. Scrape websites | 0 | Apify proxy (user's key) |
| 4. Classify targets | 0 | GPT-4o-mini |
| 5. Enrich 5 targets | 5 | Apollo organization enrich |
| 6-7. Label extraction | 0 | Pure logic |
| 8. Full search | 4 | Apollo companies search (4 pages × 25) |
| 9-12. Pipeline | 0 | Scraping + GPT (no Apollo) |
| 13. People search | ~10 | Apollo people search (depends on target count) |
| **TOTAL** | **~20** | For 100+ contacts, well within budget |

## Key Decisions Needed

### Q1: Should exploration companies show in pipeline?
**Proposed: YES** — as Iteration 1 "Exploration (draft filters)". They're already classified. User can see the conversion rate and understand why filters were changed.

### Q2: How to show iterations in UI?
**Proposed:** Pipeline dropdown shows:
- Iteration 1: "Exploration — 25 companies, 75% target rate"
- Iteration 2: "Full Pipeline — 96 companies, optimized filters"
- Default view: "All iterations" (both merged)
- Recently applied filters shown = Iteration 2 filters (optimized)

### Q3: What if exploration finds 0 targets?
**Proposed:** Skip enrichment, use initial filters for full pipeline. Warn user: "Exploration found 0 targets — proceeding with initial filters. Consider adjusting segment or geo."

### Q4: People filters — C-level only or adjusted?
**Proposed:** GPT-4o-mini infers roles from offer:
- EasyStaff (payroll) → CEO, CFO, COO, VP Finance, Head of HR, CTO
- IT product → CTO, VP Engineering, Head of Product
- Marketing → CMO, VP Marketing, Head of Growth

### Q5: Competitor exclusion?
**Proposed:** GPT-4o-mini via negativa prompt includes:
- "Company is NOT a competitor to {sender_company} offering {offer_summary}"
- For EasyStaff: exclude Deel, Remote, Oyster, Papaya Global, etc.

### Q6: Speed optimization?
**Proposed:**
- Scrape websites in parallel (batch of 10)
- GPT classification in one batch call (all 15 companies at once)
- Enrichment sequential (Apollo rate limits)
- Full search pages in parallel (4 pages)
- **Total time: ~30-45 seconds for exploration, ~60s for full pipeline**

## Implementation Steps

1. Wire `exploration_service.py` into `tam_gather` dispatcher
2. When `tam_gather` is called:
   - If no previous exploration run for this project+segment → run exploration first
   - Create Iteration 1 (GatheringRun with `source_label="exploration"`)
   - Then create Iteration 2 (GatheringRun with optimized filters)
3. Update `parse_gathering_intent` to call `offer_analyzer.infer_target_size()`
4. Update pipeline page to show iteration labels
5. Add people search after company pipeline complete
6. Wire into `smartlead_push_campaign` for auto-sequence + campaign creation

## Files to Change

| File | Change |
|---|---|
| `dispatcher.py` | Wire exploration into tam_gather flow |
| `gathering_service.py` | Support exploration iteration label |
| `exploration_service.py` | Already built — fix Apollo auth to use X-Api-Key |
| `offer_analyzer.py` | Already built — improve size inference prompt |
| `filter_intelligence.py` | Merge with exploration service (they overlap) |
| `pipeline.py` (API) | Return iteration labels in response |
| `PipelinePage.tsx` | Show iteration labels in dropdown |

## What NOT to Change

- Main app (`backend/`) — untouched
- Existing adapters (CSV, Sheet, Drive) — not affected
- Blacklist logic — already project-scoped, works as-is
