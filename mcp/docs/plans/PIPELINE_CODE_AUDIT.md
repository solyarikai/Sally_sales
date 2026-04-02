# Pipeline Code Audit — Spec vs Reality

**Date**: 2026-04-02
**Auditor**: Claude Opus 4.6
**Scope**: All MCP pipeline code vs `pipeline_spec.md` (god-level vision) + `DOCUMENT_BASED_FLOW.md` (implementation plan)

---

## SEVERITY LEGEND

- **CRITICAL** — Breaks core pipeline behavior, causes wrong results or wasted money
- **MAJOR** — Feature gap that blocks a documented requirement
- **MINOR** — Deviation from spec that works but isn't optimal
- **HARDCODE** — Something that should be configurable but is baked into code

---

## PART 1: pipeline_spec.md vs Actual Code

### ~~CRITICAL-01: Probe Page Reuse~~ — VERIFIED, WORKS CORRECTLY

**Spec says**: Probe call fetches page 1 (100 companies), saves to DB, and is REUSED when pipeline starts. Pipeline starts from page 2.

**Code does**: Full flow works correctly:
1. **Preview**: Dispatcher fetches page 1 (100 companies), stores in `filters["_probe_companies"]`, sets `_probe_page_done = 1`
2. **Confirm**: Dispatcher pops `_probe_companies`, creates `DiscoveredCompany` rows in DB, sets `filters["page_offset"] = 2`, reduces `max_pages` by 1
3. **Pipeline**: `StreamingPipeline.__init__` reads `self._tam_pages = run.pages_fetched`. L1 starts from `start_page = (self._tam_pages + 1)` = page 2. Probe companies already in DB, picked up by `run_until_kpi()` as existing companies → fed to scrape_queue.
4. **Credits**: `_persist_progress()` reports `self._tam_pages + self.pages_fetched` — counts probe page correctly.

**Status**: IMPLEMENTED CORRECTLY. No wasted credits, no duplicate fetches.

---

### CRITICAL-02: Parallelization — Scrape/Classify/People NOT Truly Overlapping with Apollo Fetch

**Spec says**: "EVERYTHING OVERLAPS. No phase waits for another." Apollo pages 2-10 fetch in parallel while probe companies are already being scraped. First scraped sites go to classifier immediately. First targets go to people queue immediately. Zero batch boundaries.

**Code does**: `StreamingPipeline.run_until_kpi()` DOES start 3 worker tasks (scraper, classifier, people) and feeds companies to scrape_queue as Apollo pages return. This is correct — the streaming architecture with queues does enable overlap.

**Status**: IMPLEMENTED CORRECTLY. The queue-based architecture with workers genuinely overlaps all phases. Each page's companies flow immediately through scrape→classify→people as workers pick them up.

---

### CRITICAL-03: Exhaustion Cascade Levels — Implementation Differs from Spec

**Spec says** (Industry-First strategy):
- Level 1: Industry IDs ONLY → up to 25 pages
- Level 2: Keywords ONLY → up to 25 pages
- Level 3: Regenerate keywords → up to 5 cycles x 20 pages each
- Level 4: Insufficient

**Spec says** (Keywords-First strategy):
- Level 1: Keywords ONLY → up to 25 pages
- Level 2: Regenerate keywords → up to 5 cycles x 20 pages
- Level 3: Industry IDs ONLY (fallback) → up to 25 pages
- Level 4: Insufficient

**Code does**: `_feed_apollo_pages()` implements a 3-level cascade:
- Strategy A (industry_first): L1 industry(25p) → L2 keywords(25p) → L3 regen(5x20p)
- Strategy B (keywords_only): L1 keywords(25p) → L2 regen(5x20p) → L3 industry(25p)

**Gap**: The level ordering MATCHES the spec. Constants match: `PAGES_PER_STRATEGY=25`, `PAGES_PER_REGEN_CYCLE=20`, `MAX_KEYWORD_REGENERATIONS=5`, `MAX_TOTAL_PAGES=150`.

**Status**: IMPLEMENTED CORRECTLY.

---

### CRITICAL-04: 10 Consecutive Empty Pages = Exhausted

**Spec says**: "10 consecutive pages with 0 NEW companies (after dedup) = strategy exhausted"

**Code does**: `EXHAUSTION_THRESHOLD = 10` in streaming_pipeline.py. `_run_level()` counts `consecutive_empty` and returns `True` (exhausted) when it reaches threshold.

**Status**: IMPLEMENTED CORRECTLY.

---

### CRITICAL-05: People Extraction — Retry Logic for <3 Verified

**Spec says**: "Go back to Step 3 candidates (25 total from seniority search). Pick NEXT best candidates that match target_roles. Repeat until 3 verified OR all candidates exhausted. Worst case: 6-9 credits per company (2-3 retry rounds)."

**Code does**: `apollo_service.py` `enrich_by_domain()` has `max_rounds = 3` retry logic. Step 1: free search (25 people), Step 2: filter has_email, Step 3: GPT rank candidates, Step 4: bulk_match top N. If <3 verified, retries with next candidates from the pool.

**Status**: IMPLEMENTED. The retry logic exists with `max_rounds=3`.

---

### CRITICAL-06: Classification Uses Scraped Website Text — NOT Apollo Industry Label

**Spec says**: "Classification NEVER uses Apollo industry label (it's always wrong) — use scraped website text only"

**Code does**: Classifier in `_classifier_worker()` uses `company.scraped_text[:3000]` as input. The prompt includes offer text + scraped website text. Apollo's industry label is NOT used in classification.

**Status**: IMPLEMENTED CORRECTLY.

---

### CRITICAL-07: Never Combine industry_tag_ids + keyword_tags

**Spec says**: "Pipeline NEVER combines organization_industry_tag_ids + q_organization_keyword_tags in same Apollo call"

**Code does**: `apollo_service.py` `search_organizations()` has logic to prefer one or the other. The streaming pipeline's `_feed_apollo_pages()` runs them at different LEVELS (L1 vs L2), never in the same API call.

**Status**: IMPLEMENTED CORRECTLY.

---

### MAJOR-01: SmartLead Auto-Push — Sequence Source Priority — VERIFIED, WORKS

**Spec says**: "Generate email sequence via GPT" (Section 9)

**DOCUMENT_BASED_FLOW says**: "When project has document-extracted sequences, SmartLead push MUST USE those — never generate new ones"

**Code does**: Full auto-push chain verified and working:
1. **Trigger**: After pipeline finishes, `kpi_met OR has_contacts > 0` → `_auto_generate_campaign()`
2. **Sequence priority**: Checks for document-extracted sequence first (`rationale ILIKE "%document%"`), falls back to CampaignIntelligenceService
3. **Gate**: Only auto-pushes if `run.campaign_id` exists AND campaign has `email_account_ids` (pre-selected via `align_email_accounts`)
4. **Push**: 8-step flow — create SmartLead campaign, set sequences, set settings (respects document settings with defaults), set schedule (auto-detects timezone from contact geography), assign accounts, upload contacts WITH segment as custom field, update DB, Telegram notification

**Status**: IMPLEMENTED CORRECTLY.

**Minor fragility**: Document sequence detection uses `rationale.ilike("%document%")` — string matching. A `source` column on GeneratedSequence would be more robust but not blocking.

---

### ~~MAJOR-02: Segment Labels NOT Pushed to SmartLead~~ — VERIFIED, WORKS

**Code does**: `_auto_push_to_smartlead()` at line 777-781 builds custom_fields per lead:
```python
"custom_fields": {
    "segment": company.analysis_segment,
    "domain": company.domain,
    "pipeline_run": str(run.id),
}
```

**Status**: IMPLEMENTED CORRECTLY. Segment labels ARE pushed as SmartLead custom fields during auto-push. Both the manual `smartlead_push_campaign` tool and the auto-push path include segments.

---

### MAJOR-03: Apollo Stats NOT Shown in Pipeline UI

**Spec says** (Section 10.2): Must show:
- Total in Apollo: 8,127 companies matching filters
- Pages available: 82
- Pages fetched: 10
- Companies obtained: 306 (unique)

**Code does**: `pipeline_status` tool in dispatcher.py returns progress (people_pct, targets_pct), timing, cost, campaign_info. It does NOT return Apollo-specific stats like total_entries, total_pages, or companies_obtained.

**Gap**: These stats are available from the probe call (total_entries, total_pages) and could be stored on GatheringRun. The streaming pipeline tracks `new_companies_count` and `pages_fetched` but not Apollo's `total_entries`.

---

### MAJOR-04: Cost Estimation Formula Differs from Spec

**Spec says**: "~10 pages search + ~100 enrichment = ~$1.10" and provides detailed cost breakdown per operation.

**Code does**: `estimate_cost()` in dispatcher.py uses: `companies_per_page = 8.75 avg` and `target_rate = 0.3 (30%)` for estimation. The actual pipeline sees much higher target rates (80%+ with industry-first strategy per spec).

**Gap**: The estimate uses 30% target rate but spec documents 80-90% with industry-first. This means cost estimates are 3x too high, which may confuse users. Should use strategy-dependent target rate.

---

### MAJOR-05: Two-Pass Classification — Model Mismatch

**Spec says** (Section 11.1): Classifier uses `gpt-4o-mini`.

**Code does**: `_classifier_worker()` uses `gpt-4o-mini` for pass 1, then `gpt-4o` for pass 2 if confidence is low/medium.

**Also**: `_generate_classification_prompt()` (Agent #2) uses `gpt-4.1-mini` (NOT `gpt-4o-mini`).

**Gap**: The spec only mentions `gpt-4o-mini`. The two-pass approach with `gpt-4o` fallback is an improvement not documented in spec. The use of `gpt-4.1-mini` for Agent #2 is also undocumented. Spec should be updated, or models should be configurable.

---

### MAJOR-06: Sequence Generation Model Mismatch

**Spec says** (Section 11.4): Sequence generation uses `gpt-4o` (fallback: `gpt-4o-mini`).

**Code does**: CampaignIntelligenceService generates sequences. Document extractor uses `gpt-4.1-mini`.

**Gap**: Model inconsistency between spec and implementation. Not blocking but should be documented.

---

### MINOR-01: People Concurrency Limit

**Spec says**: "20 concurrent" for people extraction.

**Code does**: People worker has 20 concurrent (via queue size and semaphore).

**Status**: MATCHES SPEC.

---

### MINOR-02: Scraper Concurrency Limit

**Spec says**: "100 concurrent" for website scraping.

**Code does**: Scraper uses adaptive semaphore starting at 100, scrape_queue size 200.

**Status**: MATCHES SPEC.

---

### MINOR-03: Website Text Truncation

**Spec says**: "50K characters" for scraped text.

**Code does**: `scraper_service.py` has max output 50KB. `_classifier_worker()` truncates to 3000 chars for classification.

**Status**: MATCHES SPEC.

---

## PART 2: Hardcoded Values That Should Be Configurable

### HARDCODE-01: Classification Prompt — Via Negativa Exclusion Categories

**File**: `streaming_pipeline.py` `_build_via_negativa_prompt()`

**What's hardcoded**:
- "PURE B2C with NO B2B product"
- "DOES NOT SELL PRODUCTS: VC/PE funds, investors, market makers"
- "MEDIA/RESEARCH: publications, magazines, news sites"
- "RECRUITMENT/HR: staffing agencies, recruitment firms"
- "CONSULTING/SERVICES: management consulting, advisory firms"
- "TRADITIONAL INSTITUTIONS: traditional banks, government, NGOs"
- "IT OUTSOURCING: dev agencies, software houses, body shops"
- "LAYER 1 BLOCKCHAIN PROTOCOLS: infrastructure chains"
- "COMPLETELY UNRELATED: zero connection"

**Problem**: These categories are fintech-specific. For Pavel's iGaming case or a "fashion brands" query, most of these are irrelevant and some are actively harmful (e.g., "TRADITIONAL INSTITUTIONS" would exclude banks that ARE targets for banking software).

**Should be**: Generated dynamically by Agent #2 based on the document/offer. The `_generate_classification_prompt()` method exists but the via negativa categories are still partially hardcoded.

---

### HARDCODE-02: GPT Role Selection — Target Role Exclusions

**File**: `apollo_service.py` `_gpt_rank_candidates()`

**What's hardcoded**: The prompt used to include hardcoded "NEVER target" roles: Engineering/DevOps/SRE, Finance/CFO, Operations/COO, Product, HR/People, Legal, Data/Analytics, Design/UX, Customer Success/Support, Account Management, Project Management, Delivery.

**Problem**: For a dev tools company, Engineering IS the target. For an HR SaaS product, HR IS the target. The hardcoded exclusion list breaks any non-sales-focused campaign.

**Should be**: The exclusion list should be the INVERSE of target_titles from document extraction. If target_titles = ["CTO", "VP Engineering"], then those roles are explicitly included and everything else is lower priority (but not excluded).

---

### HARDCODE-03: CRO Expansion

**File**: `apollo_service.py`

**What's hardcoded**: "CRO expanded to 'Chief Revenue Officer — NOT Chief Risk Officer'"

**Problem**: Minor — this is a disambiguation that's always useful. But it's embedded in the GPT prompt rather than being a general disambiguation system.

**Severity**: Low. This one is reasonable to keep hardcoded.

---

### HARDCODE-04: SmartLead Campaign Settings — Reference Campaign 3070919

**File**: `smartlead_service.py` `set_campaign_settings()`

**What's hardcoded**:
- track_settings: [] (NO tracking)
- stop_lead_settings: "REPLY_TO_AN_EMAIL"
- send_as_plain_text: True
- follow_up_percentage: 40
- enable_ai_esp_matching: True
- Schedule: Mon-Fri 9-18
- min_time_btw_emails: 3
- max_new_leads_per_day: 1500

**Problem**: These are production defaults from reference campaign 3070919. They're reasonable defaults but not configurable per project. A user might want tracking enabled, or different follow-up percentages, or weekend sending.

**Should be**: Configurable via `campaign_settings` extracted from document, with these as defaults.

---

### HARDCODE-05: Default Seniorities for People Search

**File**: `apollo_service.py`

**What's hardcoded**: `["owner", "founder", "c_suite", "vp", "head", "director"]`

**Problem**: Minor — these are the right defaults for most B2B outreach. But for some campaigns (e.g., targeting "senior engineers"), this list is too narrow.

**Should be**: Configurable via `people_filters.seniorities` from project config. The `set_people_filters` MCP tool exists for this but the defaults are hardcoded.

---

### HARDCODE-06: Frontend URL Base

**File**: `dispatcher.py`

**What's hardcoded**: `http://46.62.210.24:3000`

**Problem**: Hardcoded server IP. If server changes or runs locally, all links break.

**Should be**: Environment variable or config setting.

---

### HARDCODE-07: Country → Timezone Mapping

**File**: `smartlead_service.py`

**What's hardcoded**: 25+ country-to-timezone mappings (US→America/New_York, UK→Europe/London, etc.)

**Problem**: Incomplete — missing many countries. Also, US has 4 time zones.

**Severity**: Low. Works for most cases. Could use a library like `pytz` or `zoneinfo` for completeness.

---

## PART 3: Missing from DOCUMENT_BASED_FLOW.md Implementation

### MISSING-01: SmartLead Accounts Pre-Cache System

**Plan says** (Requirement 2): When user connects SmartLead API key, immediately paginate ALL accounts (2400+) and cache in `smartlead_accounts_cache` table. Future lookups query local cache.

**Code has**: `align_email_accounts` in dispatcher.py calls SmartLead API directly to list accounts, applies filter. There IS caching logic (checks cache first, falls back to API).

**Status**: PARTIALLY IMPLEMENTED. The cache exists but needs verification that it's populated on key connect (not just on first lookup).

---

### MISSING-02: Classification Prompt Generator (Agent #2)

**Plan says** (Requirement 5B): Agent #2 takes extracted segments + offer text → generates the PERFECT classification prompt. Tests multiple prompt variations, picks highest accuracy. Runs ONCE per project. Output stored on `project.offer_summary.classification_prompt`.

**Code has**: `_generate_classification_prompt()` in streaming_pipeline.py uses GPT-4.1-mini to generate a classification prompt from offer + segments. It generates ONE prompt (no variation testing). Result is used directly in classification, but unclear if stored on `project.offer_summary.classification_prompt` for reuse.

**Gap**: No multi-variation testing. No accuracy-based selection. Single prompt generated and used immediately. Should generate 3-5 variations, test each on probe companies, pick best.

---

### MISSING-03: Document Extraction — Multi-Model Comparison Test

**Plan says**: Must create `doc_extract_MODEL_TIMESTAMP.json` files (7 files — one per model) and `model_comparison_summary.json` with winner model + scores table.

**Code has**: `document_extractor.py` has `test_model_extraction()` that tests across 7 models and `score_extraction()` for scoring.

**Status**: The CODE exists but unclear if the test was actually run and results saved. Need to check `mcp/tests/results/` for these files.

---

### MISSING-04: Opus Verification Files

**Plan says**: Must create:
- `verification_companies_TIMESTAMP.json` — Opus review of all 100+ companies
- `verification_people_TIMESTAMP.json` — Opus review of all 100+ people
- `verification_sequences_TIMESTAMP.json` — Opus review of sequence vs document

**Status**: These are test artifacts, not code. But the pipeline should support generating them via MCP tools or scripts.

---

### MISSING-05: Pipeline Status — ETA Calculation

**Plan says** (implied by spec Section 10): Pipeline UI should show elapsed time, progress, and ETA.

**Code has**: `pipeline_status` tool calculates ETA based on current rate: `remaining = target - current; eta = remaining / rate * elapsed`.

**Status**: IMPLEMENTED.

---

### MISSING-06: Funding Stage as Prioritization Layer

**Plan says**: "funded first, then all" — funding stage should be used as a prioritization signal, not a hard filter.

**Code has**: `search_organizations()` accepts `latest_funding_stages` as a filter parameter. But it's a HARD filter (only returns funded companies) rather than a soft priority (show funded first, then unfunded).

**Gap**: The spec treats funding as "optional" filter field. The plan wants it as prioritization. Current implementation is a hard filter which may exclude good targets.

---

### MISSING-07: Generality Test Infrastructure

**Plan says**: Must test with 3 documents: outreach-plan-fintech.md, pavel_example_of_target_companies_description.md, simple one-liner.

**Code has**: No automated generality test. No script that runs the pipeline with all 3 documents and compares results.

**Gap**: Need a test harness or at minimum documented manual test procedure that verifies all 3 documents produce acceptable results.

---

### MISSING-08: Iteration Log — Automated Score Tracking

**Plan says**: After each iteration: run full pipeline → verify → calculate scores → log to `iteration_log.md` with timestamp, scores, what changed.

**Code has**: `PipelineIteration` model exists in DB for tracking iterations. But no automated scoring or logging to markdown file.

**Gap**: Score calculation and iteration logging is manual. Should be automated: after each pipeline run, Opus verifies results and writes scores to iteration_log.md.

---

### MISSING-09: Document Extraction → Project.offer_summary Integration

**Plan says**: Document extraction should populate `project.offer_summary` with all extracted data including segments, target_roles, sequences, campaign_settings, exclusion_list.

**Code has**: `create_project` in dispatcher.py handles `document_text` parameter. It calls `extract_from_document()` and stores results. The extracted data goes into `offer_summary` and creates `GeneratedSequence`.

**Status**: IMPLEMENTED. But need to verify ALL extracted fields are stored (especially `exclusion_list`, `campaign_settings`, `segments`).

---

### MISSING-10: Dynamic Exclusion List from Document

**Plan says**: Each document may have its own exclusion list (e.g., "exclude consulting firms, exclude dev agencies"). This should drive classification, not hardcoded categories.

**Code has**: `_build_via_negativa_prompt()` reads `self._exclusion_list` from `project.offer_summary.exclusion_list`. BUT it also has 8+ hardcoded exclusion categories that are always present regardless of document.

**Gap**: The hardcoded categories should be REMOVED and replaced entirely by document-extracted exclusion list + Agent #2 generated prompt. Currently it's a mix of hardcoded + dynamic, which means some categories are always present even when they're wrong for the domain.

---

## PART 4: Architecture Concerns

### ARCH-01: Orchestrator vs StreamingPipeline — Unclear Boundary

The codebase has TWO pipeline execution paths:
1. `PipelineOrchestrator` (in pipeline_orchestrator.py) — batch-based, iterates with PAGES_PER_BATCH=10
2. `StreamingPipeline` (in streaming_pipeline.py) — queue-based, fully streaming with workers

The orchestrator calls StreamingPipeline internally. But some tools (`run_auto_pipeline`) go through the orchestrator while others (`tam_gather` confirm) also call `start_pipeline_background()`.

**Concern**: Two entry points to the same pipeline create confusion about which path is "production". The streaming pipeline is the spec-compliant one. The orchestrator adds auto-push and notifications on top. Both should be clearly documented.

---

### ARCH-02: Session Management — Own Session per Worker

**Spec says**: "Each worker uses OWN session (no conflicts)"

**Code does**: `_ingest_page_results()` "Uses own session (no conflicts with workers)". Workers appear to share the session passed to StreamingPipeline constructor.

**Concern**: If workers share a session, concurrent commits could conflict. Need to verify each worker truly gets its own session or that the shared session is used safely with proper isolation.

---

### ARCH-03: Cost Tracking — Dual System

Two cost tracking systems exist:
1. `CostTracker` (global service) — accumulates entries in memory
2. `MCPUsageLog` (DB table) — persisted by orchestrator's `_flush_costs()`

**Concern**: If pipeline crashes before `_flush_costs()`, cost data is lost. The streaming pipeline calls `_persist_progress()` which updates GatheringRun.credits_used, but this may not include all costs tracked by CostTracker.

---

### ARCH-04: Filter Strategy Decision — A11 Classifier Location

**Spec says**: "A11 classifier" decides industry-first vs keywords-first strategy.

**Code has**: `industry_classifier.py` (A11) makes the decision. But the streaming pipeline also has its own strategy selection in `_feed_apollo_pages()` based on `has_industry` flag in filters.

**Concern**: Two places make strategy decisions. If they disagree, the pipeline may use the wrong strategy. Should be a single source of truth.

---

## SUMMARY — Top 10 Issues to Fix

| # | Severity | Issue | File |
|---|----------|-------|------|
| 1 | CRITICAL | Hardcoded via negativa categories (fintech-specific) | streaming_pipeline.py |
| 2 | CRITICAL | Hardcoded role exclusions in GPT prompt | apollo_service.py |
| 3 | MAJOR | Agent #2 generates 1 prompt, no variation testing | streaming_pipeline.py |
| ~~4~~ | ~~MAJOR~~ | ~~Segment labels~~ — VERIFIED, pushed as custom_fields | pipeline_orchestrator.py |
| 5 | MAJOR | Apollo stats not exposed in pipeline_status | dispatcher.py |
| 6 | MAJOR | Cost estimate uses 30% target rate (real is 80-90%) | dispatcher.py |
| 7 | MAJOR | No automated generality test infrastructure | — |
| ~~8~~ | ~~MAJOR~~ | ~~Probe page reuse~~ — VERIFIED OK | dispatcher.py → streaming_pipeline.py |
| 9 | HARDCODE | Frontend URL hardcoded to 46.62.210.24:3000 | dispatcher.py |
| 10 | HARDCODE | SmartLead campaign settings not configurable per project | smartlead_service.py |

**Bottom line**: The streaming pipeline architecture (queues, workers, concurrency, exhaustion cascade) is solid and matches the spec. The main problems are all about HARDCODING — classification prompts, role exclusions, and campaign settings that should be dynamic per project/document. The generality requirement (works for ANY document) is the single biggest gap.
