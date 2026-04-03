# Exploration Phase — Full Implementation Plan
**Date**: 2026-03-30
**Source**: requirements/exploration.md + default_requirements.md
**Status**: Plan (ready to implement)

---

## The Flow

```
User: "Gather IT consulting in Miami and video production in London"
                              │
                              ▼
              ┌───────────────────────────────┐
              │  INTENT SPLITTER (gpt-4o-mini) │
              │  → 2 segments detected         │
              └──────┬────────────────┬────────┘
                     │                │
        ┌────────────┘                └────────────┐
        ▼                                          ▼
  SEGMENT 1 PIPELINE                        SEGMENT 2 PIPELINE
  "IT consulting, Miami"                    "video production, London"
        │                                          │
        ▼ (same flow for each)                     ▼

═══════════════════════════════════════════════════════════
  PHASE 1: INITIAL FILTERS (automated, no user agent)
═══════════════════════════════════════════════════════════

  Step A: Embed query → top 50 keywords from taxonomy map
  Step B1: _pick_industries (gpt-4o-mini) → 2-3 industries
  Step B2: _gpt_pick_filters (gpt-4.1-mini) → keywords + size
  Step C: Location extraction (regex)
  Step D: Filter assembler → Apollo filters ready

  RESULT: initial Apollo filters
  STATUS: tested, 100% on golden validation set

═══════════════════════════════════════════════════════════
  PHASE 2: INITIAL SEARCH + SCRAPE (1 credit)
═══════════════════════════════════════════════════════════

  Apollo search with initial filters → 25 companies
  Scrape all 25 websites (free, httpx + Apify proxy)
  GPT-4o-mini classifies targets (via negativa prompt)

  RESULT: 25 companies with scraped website text + GPT classifications
  This becomes ITERATION 0 in the pipeline
  STATUS: built, tested

═══════════════════════════════════════════════════════════
  PHASE 3: USER AGENT REVIEW (the key feedback loop)
═══════════════════════════════════════════════════════════

  MCP returns to user agent (Opus in Claude Code):
  ┌──────────────────────────────────────────────────┐
  │  "Here are 25 companies from Apollo.              │
  │   I scraped their websites.                       │
  │   GPT classified X as targets, Y as not.          │
  │                                                   │
  │   Please review ALL 25 companies:                 │
  │   1. Select top 5 for Apollo enrichment           │
  │   2. For EACH company: is it a real target        │
  │      for {offer}? Why or why not?                 │
  │                                                   │
  │   Companies:                                      │
  │   1. synergybc.com — IT staffing & consulting...  │
  │   2. cipher.com — cybersecurity solutions...      │
  │   ... (all 25 with 300 chars website text)        │
  │                                                   │
  │   Call provide_feedback with your review."         │
  └──────────────────────────────────────────────────┘

  User agent (Opus) responds via provide_feedback tool:
  ┌──────────────────────────────────────────────────┐
  │  feedback_type: "targets"                         │
  │  feedback_text: {                                 │
  │    "top_5_for_enrichment": [                      │
  │      "synergybc.com",                             │
  │      "koombea.com",                               │
  │      "bluecoding.com",                            │
  │      "avalith.net",                               │
  │      "therocketcode.com"                          │
  │    ],                                             │
  │    "target_verdicts": {                           │
  │      "synergybc.com": {"target": true,            │
  │        "reason": "IT staffing, hires contractors, │
  │        needs payroll"},                            │
  │      "cipher.com": {"target": false,              │
  │        "reason": "cybersecurity product company,  │
  │        not IT consulting"},                       │
  │      ... (all 25)                                 │
  │    }                                              │
  │  }                                                │
  └──────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════
  PHASE 4: TWO PARALLEL TASKS (triggered by agent feedback)
═══════════════════════════════════════════════════════════

  MCP receives agent's feedback and launches 2 tasks IN PARALLEL:

  ┌─────────────────────────────┐    ┌─────────────────────────────┐
  │  TASK A: ENRICH TOP 5       │    │  TASK B: PROMPT ADJUSTMENT  │
  │  (5 Apollo credits)         │    │  LOOP (free, GPT only)      │
  │                             │    │                             │
  │  For each of agent's top 5: │    │  Agent's verdicts = TRUTH   │
  │  1. Apollo enrich API       │    │  GPT's classifications =    │
  │  2. Extract keyword_tags    │    │  current prompt output      │
  │  3. Extract industry        │    │                             │
  │  4. UPSERT into shared      │    │  LOOP:                     │
  │     taxonomy map            │    │  1. Compare GPT vs agent    │
  │  5. Rebuild embeddings      │    │     on all 25 companies     │
  │                             │    │  2. If match ≥95%: done     │
  │  RESULT:                    │    │  3. If not: GPT generates   │
  │  - Taxonomy map extended    │    │     improved prompt based   │
  │  - New keywords available   │    │     on the mismatches       │
  │    for filter optimization  │    │  4. Re-classify same 25     │
  │                             │    │     companies with new      │
  │                             │    │     prompt                  │
  │                             │    │  5. Each iteration = new    │
  │                             │    │     PipelineIteration       │
  │                             │    │     visible in UI           │
  │                             │    │  6. Go to step 1            │
  │                             │    │                             │
  │                             │    │  Max 5 iterations.          │
  │                             │    │  RESULT: tuned prompt       │
  │                             │    │  that matches agent's       │
  │                             │    │  judgment at ≥95%           │
  └──────────┬──────────────────┘    └──────────┬──────────────────┘
             │                                  │
             └──────────┬───────────────────────┘
                        │ (both complete)
                        ▼

═══════════════════════════════════════════════════════════
  PHASE 5: SCALE SEARCH (new iteration, optimized)
═══════════════════════════════════════════════════════════

  New PipelineIteration started with:
  - OPTIMIZED FILTERS: initial industries + keywords
    extended with enrichment-discovered keywords
    (re-run filter_mapper with enriched taxonomy map)
  - TUNED PROMPT: the GPT classification prompt that
    matched agent's judgment at ≥95%
  - HIGHER VOLUME: max_pages = enough for 30+ targets
    (100+ contacts at 3/company)

  Apollo search → scrape all → classify with tuned prompt
  → ≥30 target companies → people enrichment → campaign

  This is the PRODUCTION iteration visible in pipeline UI.
  All previous prompt-tuning iterations also visible
  via dropdown (selected by default = latest/best).

═══════════════════════════════════════════════════════════
  PHASE 6: PEOPLE + CAMPAIGN (existing pipeline)
═══════════════════════════════════════════════════════════

  People enrichment (3 contacts/company, C-level, FREE)
  SmartLead campaign creation (sequence, accounts, test email)
  User approves → launch
```

---

## Pipeline Iteration Model

### New DB entity: `PipelineIteration`

```sql
-- Migration 008_pipeline_iterations.py
CREATE TABLE pipeline_iterations (
    id SERIAL PRIMARY KEY,
    gathering_run_id INTEGER REFERENCES gathering_runs(id),
    iteration_number INTEGER NOT NULL DEFAULT 0,

    -- What changed in this iteration
    filters JSONB,                    -- Apollo filters used
    classification_prompt TEXT,       -- GPT prompt used for classification
    prompt_source VARCHAR(50),        -- 'initial' | 'agent_feedback' | 'auto_tuned'

    -- Results
    total_companies INTEGER,
    targets_found INTEGER,
    target_rate FLOAT,

    -- Agent feedback (if this iteration was reviewed)
    agent_verdicts JSONB,             -- {domain: {target: bool, reason: str}}
    agent_top_5 TEXT[],               -- domains selected for enrichment

    -- Prompt tuning loop
    prompt_accuracy FLOAT,            -- % match with agent verdicts
    tuning_iterations INTEGER DEFAULT 0,

    is_active BOOLEAN DEFAULT TRUE,   -- latest = active, shown by default in UI
    created_at TIMESTAMP DEFAULT NOW()
);

-- UI: pipeline page shows dropdown of iterations
-- Default: latest (highest iteration_number) selected
-- Each iteration shows: filters, prompt, companies, segments, targets
```

### How iterations relate to the existing pipeline:
- `GatheringRun` = the pipeline (one per segment per user request)
- `PipelineIteration` = each re-classification of the same companies
- `DiscoveredCompany` results (is_target, analysis_segment) = per-iteration via `source_data.iteration_results[iteration_id]`
- Companies are NOT re-blacklisted between iterations (same set, different prompt)
- Companies ARE re-scraped only if scrape failed in previous iteration

---

## What Needs Building

### 1. MCP Tool: Return scraped companies for agent review
**Current**: `suggest_apollo_filters` returns filter suggestions, not company data.
**Need**: A tool (or enhanced return from `tam_gather`) that returns all 25 scraped companies with website text for agent review.
**Implementation**: After Phase 2 (search + scrape + classify), return:
```json
{
  "companies": [
    {
      "domain": "synergybc.com",
      "name": "Synergy Business Consulting",
      "website_text": "... 300 chars ...",
      "gpt_classification": {"is_target": true, "segment": "IT_CONSULTING", "reasoning": "..."}
    },
    ...
  ],
  "gpt_summary": {"targets": 6, "total": 25, "target_rate": "24%"},
  "message": "Review these companies. Which are real targets for {offer}? Select top 5 for enrichment."
}
```

### 2. MCP Tool: Accept agent feedback on targets
**Current**: `provide_feedback` is generic text.
**Need**: Structured feedback specifically for target review.
**Implementation**: Enhance `provide_feedback` or create `refinement_override` to accept:
```json
{
  "top_5_for_enrichment": ["domain1", "domain2", ...],
  "target_verdicts": {
    "domain1": {"target": true, "reason": "IT consulting firm, hires contractors"},
    "domain2": {"target": false, "reason": "cybersecurity product, not consulting"}
  }
}
```

### 3. Prompt Adjustment Loop (Task B)
**New service**: `prompt_tuner.py`
```python
async def tune_classification_prompt(
    companies: List[Dict],           # 25 companies with website text
    agent_verdicts: Dict,            # {domain: {target: bool, reason: str}}
    offer: str,                      # what we sell
    query: str,                      # segment query
    openai_key: str,
    max_iterations: int = 5,
) -> Tuple[str, float]:
    """Iterate GPT prompt until it matches agent's verdicts at ≥95%.

    Returns: (tuned_prompt, accuracy)
    """
    current_prompt = _build_initial_prompt(offer, query)

    for i in range(max_iterations):
        # Classify all 25 with current prompt
        gpt_results = await _classify_batch(companies, current_prompt, openai_key)

        # Compare vs agent truth
        accuracy, mismatches = _compare(gpt_results, agent_verdicts)

        # Save as PipelineIteration
        await _save_iteration(i, current_prompt, gpt_results, accuracy)

        if accuracy >= 0.95:
            return current_prompt, accuracy

        # Ask GPT to improve the prompt based on mismatches
        current_prompt = await _improve_prompt(
            current_prompt, mismatches, offer, query, openai_key
        )

    return current_prompt, accuracy
```

### 4. Enrichment → Taxonomy Update (Gaps 1-4 from previous plan)
Wire enrichment results into shared taxonomy map. Already designed, just needs wiring:
- `exploration_service.py`: return `enriched_companies`
- `dispatcher.py`: call `taxonomy_service.add_from_enrichment()` + `rebuild_embeddings_if_needed()`
- `filter_mapper.py`: no changes (already uses taxonomy_service singleton)

### 5. Scale Search with Optimized Filters (Phase 5)
After both parallel tasks complete:
- Re-call `filter_mapper.map_query_to_filters()` (taxonomy map now has enrichment data → better keywords)
- Create new `PipelineIteration` with optimized filters + tuned prompt
- Search Apollo with higher max_pages
- Classify with tuned prompt (≥95% accuracy)
- ≥30 target companies → proceed to people enrichment

### 6. Pipeline UI: Iteration Dropdown
- Dropdown shows all iterations for a run
- Default: latest (best) iteration selected
- Each iteration shows: filters applied, prompt used, companies, target rate
- Switching iterations updates the company table (same companies, different classifications)

---

## Files to Create/Modify

| File | Action | What |
|------|--------|------|
| `backend/app/services/prompt_tuner.py` | CREATE | Prompt adjustment loop (Task B) |
| `backend/app/models/pipeline.py` | MODIFY | Add PipelineIteration model |
| `backend/alembic/versions/008_pipeline_iterations.py` | CREATE | DB migration |
| `backend/app/services/exploration_service.py` | MODIFY | Return enriched_companies, integrate with taxonomy |
| `backend/app/services/gathering_service.py` | MODIFY | Support iterations (re-classify without blacklist) |
| `backend/app/mcp/dispatcher.py` | MODIFY | Wire feedback → parallel tasks → scale search |
| `backend/app/mcp/tools.py` | MODIFY | Enhanced tool responses with company data |
| `frontend/src/pages/PipelinePage.tsx` | MODIFY | Iteration dropdown, latest by default |

## Tests to Create

| File | What |
|------|------|
| `tests/exploration/test_step1_filters.py` | Golden validation (existing, passing) |
| `tests/exploration/test_step2_search.py` | Real Apollo + scrape + classify |
| `tests/exploration/test_step3_agent_review.py` | Simulate agent feedback, verify MCP receives it |
| `tests/exploration/test_step4_prompt_tuning.py` | Prompt loop converges to ≥95% |
| `tests/exploration/test_step5_enrich_map.py` | Enrichment updates taxonomy, embeddings rebuilt |
| `tests/exploration/test_step6_optimized.py` | Re-search with better filters + tuned prompt |
| `tests/exploration/test_full_e2e.py` | All steps, ≥30 targets found |

---

## Credit Budget Per Segment

| Phase | Action | Credits |
|-------|--------|---------|
| Phase 2 | Apollo search (25 companies) | 1 |
| Phase 4 Task A | Enrich top 5 | 5 |
| Phase 5 | Scale search (1-4 pages) | 1-4 |
| Phase 6 | People search | FREE |
| **TOTAL** | | **7-10** |

GPT costs for prompt tuning loop: ~$0.01 (5 iterations × 25 companies × gpt-4o-mini)

---

## KPIs

| Metric | Target |
|--------|--------|
| Target companies found | ≥30 per segment |
| Contacts per campaign | ≥100 (3 per company) |
| Classification accuracy (GPT vs agent) | ≥95% after tuning |
| Apollo credits per segment | ≤10 |
| Prompt tuning iterations | ≤5 |
| Keyword map growth per enrichment | +30-100 keywords |

---

## Implementation Order

1. **PipelineIteration model + migration** — foundation for everything else
2. **prompt_tuner.py** — the core feedback loop
3. **Wire enrichment → taxonomy** — Gaps 1-4
4. **Enhanced MCP tool responses** — return scraped companies for agent review
5. **Dispatcher wiring** — agent feedback → parallel tasks → scale
6. **Tests** — step by step, each must pass before next
7. **UI iteration dropdown** — last (frontend)
