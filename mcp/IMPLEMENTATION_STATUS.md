# MCP Implementation Status — Critical Analysis

**Date**: 2026-03-30
**Sources**: default_requirements.md, exploration.md, requirements_source.md, Pavel's bugs, test results

---

## WHAT'S BUILT AND WORKING

### Core Pipeline (90% done)
- Auth (signup/login/token) ✅
- Project creation with website scraping (offer discovery) ✅
- Apollo API search with filter confirmation ✅ (Bug 2 fixed)
- Blacklist check with project-scoped isolation ✅
- Scraping via Apify residential proxy ✅
- Via negativa classification (gpt-4o-mini) ✅
- Re-analyze with adjusted prompt ✅ (tam_re_analyze)
- Sequence generation + approval ✅
- SmartLead campaign push + test email + activation ✅
- Reply monitoring auto-enable ✅
- Session continuity ✅

### Exploration System (80% done by other agent)
- Taxonomy: 2,014 keywords + 112 industries (JSON cache) ✅
- Embedding pre-filter (cosine similarity) ✅
- Filter mapper (taxonomy → GPT selection) ✅
- Exploration service (search → scrape → classify → enrich → optimize) ✅ scaffolded
- Tested: 35 model×prompt setups, winner = gpt-4o × v9_negativa (96% accuracy) ✅

### UI
- Setup page: SmartLead, Apollo, OpenAI, Apify, GetSales ✅
- Pipeline page: companies table, filters, iterations, company modal ✅
- CRM: reused from main app via @main alias ✅
- Campaigns: MCP badge, LISTENING indicator, monitoring toggle ✅
- Conversations: tool call logging ✅

---

## WHAT'S NOT DONE — CRITICAL GAPS

### GAP 1: Exploration Not Wired Into Pipeline Flow
**Status**: exploration_service.py exists (372 lines) but NEVER CALLED from dispatcher
**Impact**: Users get raw Apollo search → 35-55% target rate instead of optimized 70%+
**What's needed**:
1. After initial tam_gather + classify, AUTO-RUN exploration enrichment on top 5 targets
2. Extract their keyword_tags → update taxonomy → suggest optimized filters
3. Show user: "Your initial filters got 55% targets. I found better filters that should get ~70%. Re-search?"
4. This is the CORE differentiator — without it, MCP is just a fancy Apollo wrapper

### GAP 2: People Enrichment Not Implemented in MCP
**Status**: Apollo people search endpoint exists in apollo_service.py but NOT called in pipeline
**Impact**: Pipeline stops at target companies. No contacts gathered. User has to do it manually.
**What's needed**:
1. After targets confirmed at Checkpoint 2 → auto-search people (C-level by default)
2. Offer-adjusted roles: payroll → HR directors; fashion → brand managers
3. 3 contacts per company minimum
4. Store as ExtractedContact records in DB
**This blocks the entire campaign creation flow** — can't push to SmartLead without contacts

### GAP 3: Default Flow Not End-to-End
**default_requirements.md describes**: user says segment → MCP does EVERYTHING → campaign with test email ready
**Reality**: User must manually call 8+ tools in sequence. MCP doesn't orchestrate.
**What's needed**: A `run_full_pipeline` meta-tool that:
1. Creates project (if needed)
2. Discovers filters via exploration
3. Gathers companies (with confirmation)
4. Runs blacklist + scrape + analyze
5. Enriches people
6. Generates sequence
7. Pushes to SmartLead
8. Sends test email
9. Asks for approval
Each step notifies user with links. User only needs to confirm at checkpoints.

### GAP 4: Taxonomy Not in DB (pgvector)
**Status**: JSON file cache at `apollo_filters/apollo_taxonomy_cache.json`
**Impact**: No persistence across container restarts, no pgvector index for fast similarity search
**What's needed**: Migration to create `apollo_taxonomy` table with pgvector embedding column
**Blocked by**: pgvector extension not installed in MCP postgres container

### GAP 5: Pavel's Real-World Quality Issues
From his actual usage (iGaming tech providers for Mifort):
- 48% accuracy (15/31 clean targets) — needs ≥90%
- GPT confuses operators (casinos) with technology providers (casino software)
- Domain-specific exclusion rules needed per segment
**Partially fixed**: gpt-4.1-mini now crafts domain-specific rules before gpt-4o-mini applies them
**Not verified**: Need to retest Pavel's exact case after the fix

### GAP 6: No Cost Tracking on Account Page
**Status**: Account page shows API tool call counts but NOT Apollo credit usage by project/date
**What's needed**: Track `credits_used` per gathering run, aggregate by project and date range

---

## BOTTLENECKS (ordered by impact)

### #1: People enrichment missing → campaigns can't be created from gathered companies
Without contacts, the SmartLead push uploads 0 leads. The entire pipeline stops.
**Fix**: Add people search step after Checkpoint 2 approval.

### #2: Exploration not wired → suboptimal filters → low target rate
Users like Pavel get 48% target rate. With exploration (enrich top 5 → discover real keywords → re-search), this should be 70%+.
**Fix**: Wire exploration_service into dispatcher, run automatically after initial classify.

### #3: No end-to-end orchestration → user must call 8+ tools manually
The agent (Claude/Cursor) must know the exact tool sequence. This breaks when the agent makes wrong decisions (Bug 2 — auto-launching without confirmation).
**Fix**: Create `run_full_pipeline` that orchestrates everything with checkpoints.

### #4: Classification quality for niche B2B segments
GPT-4o-mini with generic via negativa gets 48% on iGaming (operators vs providers confusion).
The gpt-4.1-mini domain-specific rule generation is deployed but untested on Pavel's case.
**Fix**: Test on Pavel's exact segment. If still <90%, add more examples to the prompt.

---

## WHAT TO BUILD NEXT (priority order)

### P0: People enrichment → unblocks campaign creation
```python
# After Checkpoint 2 approved:
# 1. Get all target companies
# 2. For each: Apollo people search (FREE) → 3 contacts C-level
# 3. Store as ExtractedContact
# 4. Show user: "Found {N} contacts from {M} target companies"
```

### P1: Wire exploration into pipeline
```python
# After initial classify at Checkpoint 2:
# 1. Pick top 5 target companies
# 2. Enrich via Apollo (5 credits) → extract keyword_tags, industry
# 3. Update taxonomy with new keywords
# 4. GPT: which new keywords to add to search?
# 5. Show user: "Found better filters. Re-search? Current: 55% → Expected: ~70%"
```

### P2: End-to-end pipeline orchestrator
```python
# Tool: run_full_pipeline
# Input: segment description, geo, project_id
# Orchestrates: gather → blacklist → scrape → classify → explore → re-search → people → campaign
# User sees: progress updates at each step, confirms at checkpoints
```

### P3: Taxonomy to pgvector DB
- Install pgvector in MCP postgres
- Create apollo_taxonomy table
- Migrate 2,014 keywords from JSON cache
- Pre-compute embeddings for all keywords
- Filter mapper uses DB instead of file

### P4: Account page credit tracking
- Show Apollo credits used per project, per date range
- Show OpenAI token costs per pipeline
- Show estimated monthly cost for N campaigns

---

## MODEL STRATEGY (finalized from 35-setup test)

| Task | Model | Cost | Why |
|------|-------|------|-----|
| Intent parsing (split segments) | gpt-4o-mini | $0.15/1M | Simple structured extraction |
| Filter mapping (pick from taxonomy) | gpt-4.1-mini | $0.40/1M | Needs to reason about business segments |
| Domain-specific rule CREATION | gpt-4.1-mini | $0.40/1M | Crafts nuanced exclusion rules once |
| Company classification (apply rules) | gpt-4o-mini | $0.15/1M | Follows well-crafted rules at scale |
| Sequence generation | gpt-4o-mini | $0.15/1M | Template-based with patterns |
| Filter optimization (after enrichment) | gpt-4o-mini | $0.15/1M | Picks from known keyword list |

**Total cost per segment**: ~$0.10-0.20 for AI + 7-10 Apollo credits

---

## TEST QUALITY RESULTS (from other agent's exploration tests)

| Segment | Filter Quality | Target Rate | Accuracy |
|---------|---------------|-------------|----------|
| EasyStaff IT Miami | ✅ Perfect filters | 55% (6/11) | 100% classification |
| TFP Fashion Italy | ✅ Perfect filters | 100% (7/7) | 100% classification |
| OnSocial Creator UK | ⚠️ Industries too broad | 50% (5/10) | 90% classification |
| Pavel iGaming | ❌ Not tested post-fix | 48% pre-fix | Needs retest |

**OnSocial bottleneck**: "internet" and "information services" industries are too broad (46K results).
Fix: Only use "marketing & advertising" industry + specific influencer keywords.

**Pavel bottleneck**: GPT can't distinguish operators from tech providers.
Fix: gpt-4.1-mini domain-specific rules should handle this. Needs verification.
