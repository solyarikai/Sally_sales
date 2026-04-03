# MCP Pipeline Processing Chain

Full specification of what happens at each stage, which models are used, and how data flows.

## 1. DOCUMENT EXTRACTION
**File**: `services/document_extractor.py:extract_from_document()`
**Model**: `gpt-4.1-mini`
**Input**: Raw strategy document text + company website URL
**Prompt**: Extracts structured data from free-form outreach documents

**Output** (stored in `project.offer_summary`):
```
offer_summary = {
  "_source": "document",
  "primary_offer": "Company's value proposition",
  "target_audience": "ICP description",
  "segments": [
    {"name": "PAYMENTS", "keywords": ["payment gateway API", "PSP platform", ...]},
    {"name": "LENDING", "keywords": ["lending-as-a-service", "loan origination", ...]},
    ...  // 8-10 keywords per segment
  ],
  "apollo_filters": {
    "combined_keywords": [...],  // all segment keywords merged
    "locations": ["United States", "United Kingdom"],
    "employee_range": "20,500",
    "industries": ["financial services"],
    "funding_stages": ["series_a", "series_b"]  // prioritization filter
  },
  "target_roles": {
    "titles": ["VP Sales", "CRO", "CMO", ...],
    "reasoning": "Why these roles"
  },
  "exclusion_list": [{"type": "...", "reason": "..."}],
  "sequences": [
    {"name": "Sequence Name", "steps": [...], "cadence_days": [...]}
  ],
  "seed_data": {
    "keywords": ["all segment keywords, deduped"],
    "industry_tag_ids": [],  // empty for documents (no Apollo IDs)
    "source": "document"
  }
}
```

## 2. WEBSITE SCRAPING (if URL provided instead of document)
**File**: `services/offer_scraper.py`
**Model**: `gpt-4.1-mini` (for offer extraction from scraped HTML)
**Input**: Company website URL
**Method**: Apify residential proxy → BeautifulSoup HTML parsing → GPT extraction
**Output**: Same `offer_summary` structure but with `_source: "website"`

## 3. OFFER CONFIRMATION
**File**: `mcp/dispatcher.py:confirm_offer()`
**Input**: User approval or feedback text
**If feedback**: Re-runs extraction with feedback as additional context
**Sets**: `project.offer_approved = True`

## 4. EMAIL ACCOUNT ALIGNMENT
**File**: `mcp/dispatcher.py:align_email_accounts()`
**Input**: Account filter string (e.g., "all accounts with john")
**Method**: Fetches all SmartLead accounts, filters by substring match
**Output**: Draft `Campaign` record linked to project with selected account IDs

## 5. SEED DATA (from documents or example companies)

Seeds are GPT-prioritized keywords and industry_tag_ids stored on the project. They inform (but don't dictate) keyword generation for any subsequent `tam_gather` call.

### Stored in `project.offer_summary.seed_data`:
```json
{
  "keywords": ["apparel", "fashion brand", ...],       // GPT-prioritized
  "industry_tag_ids": ["5567cd82...", ...],             // GPT-prioritized
  "example_domains": ["nike.com", "adidas.com"],        // user-provided (examples only)
  "source": "document" | "examples"
}
```

### Source: Document
**Trigger**: `create_project(document_text=...)`
**Flow**:
1. `document_extractor.py` extracts segments with per-segment keywords [gpt-4.1-mini]
2. All segment keywords collected, deduped → stored as `seed_data.keywords`
3. No industry_tag_ids (document doesn't provide Apollo IDs)
4. `seed_data.source = "document"`

### Source: Example Companies
**Trigger**: `tam_enrich_from_examples(domains=["nike.com", "adidas.com", ...])`
**Flow**:
1. Each domain enriched via Apollo `/organizations/bulk_enrich` [1 credit each]
2. Apollo returns per-company: `industry`, `industry_tag_id`, `keywords[]`
3. `_extract_common_labels()` aggregates across all examples [no GPT]
4. **Keyword prioritization** [gpt-4o-mini]: Filters raw keywords to keep only segment-relevant ones (max 8). Excludes tech stacks, product names, frameworks.
5. **Industry tag_id prioritization** [gpt-4o-mini]: Selects 2-3 most relevant industries from those found on examples, maps back to tag_ids.
6. GPT-prioritized results stored as `seed_data` on project — reusable across queries

### How seeds are consumed by tam_gather
```
tam_gather(project_id, query="fashion brands in Italy")
  → Read project.offer_summary.seed_data
  → seed_keywords passed to filter_mapper as GPT hints
  → seed_tag_ids merged into organization_industry_tag_ids
  → filter_mapper GPT decides which seeds are relevant for THIS query
  → Seeds from "nike.com" help "fashion brands" but GPT ignores "athletic footwear" for "luxury brands"
```

## 6. FILTER GENERATION (tam_gather → filter_mapper)

### Filter Classification

**Mandatory** (MCP must have before pipeline starts, asks user if missing):
- **Geo** (locations) — from user query or document
- **Segments** (query describing target companies) — from user query or document

**Inferred** (GPT derives automatically, no need to ask user):
- **Size** (employee range) — GPT infers from offer context
- **Industries** (Apollo industry names) — GPT picks 2-3 from 84 real Apollo industries
- **Keywords** (free-text search terms) — GPT generates 20-30 freely, informed by seeds

**Prioritization** (nice-to-have, graceful degradation):
- **Funding** (series_a, series_b) — from document. Applied when Apollo has data, silently dropped when exhausted. Unfunded streams continue in parallel.

### Apollo Industry Taxonomy
**Table**: `apollo_taxonomy` (PostgreSQL)
**Content**: 84 real Apollo industries, each with a unique `tag_id` (hex MongoDB ObjectId)
**Source**: Enriched from real company data via Apollo `/organizations/enrich` endpoint
**Auto-extension**: New industries discovered automatically during:
- Company enrichment (`apollo_service.bulk_enrich_organizations`)
- People enrichment (`apollo_service.enrich_people_emails` — `bulk_match` returns org data including `industry_tag_id`)
**No keywords stored**: Apollo accepts any free-text keywords. Only industry name ↔ tag_id mapping is maintained.

### Step A: Industry Selection
**File**: `services/filter_mapper.py:_pick_industries()`
**Model**: `gpt-4.1-mini` (fallback: `gpt-4o-mini`)
**Input**: User query + 84 real Apollo industry names (from `apollo_taxonomy` table, all with tag_ids)
**Prompt**: `"[query]" — pick 2-3 matching Apollo industries. [84 industries] JSON: {"industries": ["exact name"]}`
**Output**: 2-3 industry names → direct tag_id lookup from `apollo_taxonomy.tag_id`

### Step B: Keyword + Employee Size Generation
**File**: `services/filter_mapper.py:_generate_keywords()`
**Model**: `gpt-4.1-mini` (fallback: `gpt-4o-mini`)
**Input**: User query + offer description + seed keywords (from `project.offer_summary.seed_data`)
**Prompt**:
```
Generate Apollo.io search keywords for finding B2B companies.

User's segment: {query}
User's product: {offer}

SEED KEYWORDS (from user's strategy document or example companies):
[seed_data.keywords if available — used as starting point and inspiration]

Generate 20-30 keywords...
```
**Output**: `{keywords: [...], employee_ranges: [...]}`

**Apollo keyword behavior** (verified via live testing 2026-04-03):
- `q_organization_keyword_tags` accepts ANY free-text strings
- Multiple keywords are **OR-combined** — adding keywords EXPANDS results:
  - "payment gateway" alone: 3,199 companies
  - "lending platform" alone: 401 companies
  - Both together: 3,591 (more than either alone)
  - 5 keywords together: 5,788 (keeps growing)
- One API call with 20-30 keywords covers all segments at once
- No per-keyword calls needed, no predefined list, no validation
- More keywords = broader coverage = more targets for GPT to classify
- Keywords are NOT per-segment — flat list, all OR'd together in one search

### Step C: Location Extraction
**File**: `services/filter_mapper.py:_extract_locations()`
**Method**: Regex parsing (no GPT) — extracts "in Miami", "in US and UK"
**Note**: Document locations override this if available

### Step D: Document Structural Overrides
**File**: `mcp/dispatcher.py` (inline in tam_gather handler)
**Applied from document if available**:
- Locations (override filter_mapper's regex)
- Funding stages (prioritization filter — applied to funded streams)
- Employee range (if GPT didn't set one)

### Step E: Seed Tag ID Merge
**File**: `mcp/dispatcher.py` (inline in tam_gather handler)
**Input**: `seed_data.industry_tag_ids` from project (GPT-prioritized from examples)
**Method**: Merged with filter_mapper's industry_tag_ids (union, no duplicates)
**Result**: Both GPT-selected and example-derived tag_ids available for parallel industry stream

### Final Filter Assembly
```json
{
  "q_organization_keyword_tags": ["industry_names + GPT_keywords (seed-informed)"],
  "organization_industry_tag_ids": ["filter_mapper_ids + seed_tag_ids (merged)"],
  "organization_locations": ["Country1", "Country2"],
  "organization_num_employees_ranges": ["20,500"],
  "organization_latest_funding_stage_cd": ["series_a"],
  "mapping_details": {"industries, keywords, tag_ids, model_used, seed_count"}
}
```

## 7. APOLLO PROBE
**File**: `services/filter_intelligence.py:probe_and_scrape()`
**Input**: Final assembled filters
**Method**: Apollo API `/organizations/search` (1 credit per call)
**Output**: `total_available` companies, sample results for preview

## 8. PIPELINE PREVIEW → USER APPROVAL
**File**: `mcp/dispatcher.py` (tam_gather PREVIEW mode)
**Shows user**: All keywords, industries, tag_ids, cost estimate, KPIs, pipeline link
**Waits for**: User says "Proceed?" → `tam_gather(confirm_filters=true)`

**MCP agent behavior**:
- User provides query + geo → show preview, ask only "Proceed?"
- User provides query without geo → ask "Which location?"
- User provides only website → after project creation, ask "What companies and where?"
- Document provides everything → show preview, ask only "Proceed?"

## 9. AUTONOMOUS PIPELINE
**File**: `services/streaming_pipeline.py`
**Runs in background after user confirms**

### Parallel Streams (all launched simultaneously)
```
streams = []

# Prioritization: funded streams (if funding filter provided)
if has_funding:
    L0_kw_funded   → keywords + funding + geo + size    (best: funded + relevant)
    L0_ind_funded  → industry_tag_ids + funding + geo + size  (best: funded + broad)

# Mandatory: always run
L1_keywords    → keywords + geo + size              (broad coverage)
L1_industry    → industry_tag_ids + geo + size       (precise, good pagination)

# All run via asyncio.gather — pipeline deduplicates by domain
# KPI flag stops ALL streams when target reached
```

**Apollo rule**: `industry_tag_ids` and `keywords` are NEVER combined in the same API call (they AND together = near-zero results). Each stream uses one or the other.

### Phase 1: Gather
- Apollo API pages (100 companies/page, parallel batches)
- ~56-85 unique companies per page (Apollo pagination is inconsistent with keywords)
- ~100 unique companies per page with industry_tag_ids (consistent)
- Stores as `DiscoveredCompany` records
- Cross-page dedup by domain (~5% duplicates)

### Phase 2: Scrape
- Website content via Apify residential proxy (50 concurrent)
- BeautifulSoup HTML → clean text
- Stored as `CompanyScrape` records

### Phase 3: Classify (via negativa)
**Model**: `gpt-4o-mini` (50 concurrent)
**Prompt**: Analyzes scraped website content against project's ICP
**Method**: Via negativa — focuses on EXCLUDING non-matches
**Output per company**:
- `is_target`: bool
- `confidence`: 0-100
- `segment`: CAPS_LOCKED label (PAYMENTS, LENDING, etc.)
- `reasoning`: Why target/not-target

**Cost**: ~$0.003 per company ($0.07 per 300 companies)

### Phase 4: Extract People
**Method**: Apollo `/mixed_people/api_search` (FREE, no credits) → `/people/bulk_match` (1 credit per person)
**Config**: 3 contacts per target company (20 concurrent)
**Roles**: Auto-adjusted based on project's offer:
- Payroll offer → VP HR, CHRO, Head of People
- SaaS offer → CTO, VP Engineering
- Fashion offer → Brand Director, CMO
**Priority**: owner/founder > c_suite > vp > head > director
**Side effect**: `bulk_match` returns org data including `industry_tag_id` → auto-extends `apollo_taxonomy` with any new industries discovered

### Phase 5: Auto-Push to SmartLead
**Trigger**: When KPI met (default: 100 people, 3/company)
**Creates**: SmartLead DRAFT campaign with:
- Generated email sequence (4-5 steps)
- Selected sending accounts
- Uploaded target contacts with normalized company names + segment as custom fields
- Test email sent to user's email
- Campaign settings: plain text, no tracking, stop on reply, Mon-Fri 9-18 target timezone

### Phase 6: Keyword Regeneration (if KPI not met)
**File**: `services/streaming_pipeline.py:_regenerate_keywords()`
**Model**: `gpt-4.1-mini`
**Trigger**: After all initial streams exhausted, KPI not reached
**Method**: GPT generates new keywords based on which target companies were found
**Runs**: Up to 3 regeneration cycles

**Default KPIs**: `target_people=100`, `max_people_per_company=3`

**Typical results** (from testing):
- Fashion Italy: 102 targets, 131 people, 59s, $0.17
- Video London: 81 targets, 134 people, 55s, $0.19
- IT Miami: 18 targets, 39 people, 27s, $0.04

---

## 10. DOCUMENT → PROJECT CREATION — AGENT CHAIN

Full trace of what happens when a user provides a strategy document or website URL.

### Agent Chain
```
User input (document or URL)
  │
  ├─ Document path:
  │   Agent #1: Document Extractor (gpt-4.1-mini)
  │   Input: raw text (up to 15K chars) + website URL
  │   Output: offer, segments, roles, filters, sequences,
  │           campaign_settings, exclusion_list
  │   Variable normalization: gpt-4o-mini (if unfillable vars)
  │
  ├─ Website path:
  │   Layer 1: Apify scrape (residential proxy, 15s timeout)
  │   Layer 2: Direct HTTP + meta extraction (fallback)
  │   Layer 3: GPT analysis (gpt-4.1-mini) — always runs
  │   Output: offer_summary with _source="website"|"gpt_knowledge"
  │
  ▼
  project.offer_summary (JSONB) ← stored on Project record
  │
  ▼ confirm_offer (user approval or feedback)
  │   If feedback: gpt-4.1-mini re-extracts with feedback context
  │   Sets: offer_approved = True
  │
  ▼ align_email_accounts (filter, preset_name, or explicit IDs)
  │   Creates mcp_draft Campaign with selected accounts
  │
  ▼ tam_gather (preview phase)
  │
  ├─ Filter generation chain:
  │   ├ Step A: _pick_industries (gpt-4.1-mini) → 2-3 tag_ids
  │   ├ Step B: _generate_keywords (gpt-4.1-mini) → 20-30 keywords
  │   │         seed_keywords from document inform generation
  │   ├ Step C: _extract_locations (regex) → countries
  │   ├ Step D: Document overrides (locations, funding, size)
  │   └ Step E: Seed tag_id merge (union with filter_mapper)
  │
  ├─ A11 Classifier (gpt-4o-mini) — informational label only
  ├─ Apollo Probe (1 page, 1 credit) → total_entries + 100 companies
  └─ Preview response → user confirms → pipeline starts
```

### offer_summary JSON Schema
```json
{
  "_source": "document | website | gpt_knowledge",
  "primary_offer": "What we sell",
  "value_proposition": "Problem solved",
  "target_audience": "Who buys",
  "target_roles": {
    "titles": ["VP Sales", "CRO", "CMO"],
    "primary": ["CEO", "VP Sales"],
    "secondary": ["Director of Sales"],
    "tertiary": ["Manager"],
    "seniorities": ["c_suite", "vp", "head", "director"],
    "exclude_titles": ["Chief Risk Officer"]
  },
  "segments": [
    {"name": "PAYMENTS", "keywords": ["payment gateway API", "PSP", ...]},
    {"name": "LENDING", "keywords": ["lending-as-a-service", ...]}
  ],
  "apollo_filters": {
    "combined_keywords": ["60-80 merged keywords"],
    "locations": ["United States", "United Kingdom"],
    "employee_range": "20,500",
    "industries": ["financial services"],
    "funding_stages": ["series_a", "series_b"]
  },
  "exclusion_list": [{"type": "competitors", "reason": "..."}],
  "campaign_settings": {"tracking": false, "stop_on_reply": true, "plain_text": true},
  "seed_data": {"keywords": [...], "industry_tag_ids": [], "source": "document"}
}
```

### Classification Prompt Generation (Pipeline Init)
```
If exclusion_list exists:
  Agent #2 (gpt-4.1-mini) → via negativa prompt with 5-8 exclusion + 3-4 inclusion rules
Else:
  Generic _build_via_negativa_prompt() from offer_text + segments
```

### GPT Models Across the Chain

| Step | Model | Purpose |
|------|-------|---------|
| Document extraction | gpt-4.1-mini | Extract all structured data from strategy doc |
| Variable normalization | gpt-4o-mini | Fix SmartLead {{variables}} |
| Website analysis | gpt-4.1-mini | Scrape + extract offer from URL |
| Offer feedback merge | gpt-4.1-mini | Update offer from user corrections |
| Industry selection | gpt-4.1-mini | Pick 2-3 Apollo industries from 84 |
| Keyword generation | gpt-4.1-mini | Generate 20-30 search keywords (seed-informed) |
| Industry specificity (A11) | gpt-4o-mini | SPECIFIC vs BROAD label (informational) |
| Classification prompt (Agent #2) | gpt-4.1-mini | Generate via negativa rules from document |
| Company classification | gpt-4o-mini | Classify each scraped company |
| 2-pass re-evaluation | gpt-4o | Re-classify on low/medium confidence |
| Keyword regeneration | gpt-4.1-mini | Fresh keywords per angle (10 angles) |
| Sequence generation | gpt-4o | Generate 4-5 step email sequence |
| People role selection | gpt-4o-mini | Rank candidates by target roles |

---

## 11. MCP BEHAVIOR RULES

### Token & Auth Gating
- No token → respond ONLY with signup link
- Keys not configured → list WHICH keys missing + Setup page link
- All 4 keys (Apollo, OpenAI, SmartLead, Apify) required before pipeline ops

### Approval Gates
Show "what I will do" + wait for user approval before:
- Starting/pausing/resuming pipeline
- Changing target definition or classification prompts
- Pushing to SmartLead or activating campaigns
- Any action that costs credits

### Cost Transparency
Show estimated costs BEFORE executing: Apollo credits, Apify GB, OpenAI tokens

### No Hardcoding
- Classification prompts generated fresh from project context
- Filter mapping uses general approach — no bias toward specific industries
- All tested against multiple segments for generality

---

## 12. SYSTEM ARCHITECTURE

### Isolation
- Own PostgreSQL (`mcp_leadgen`), own Redis (port 6380)
- Shared frontend components via `@main` alias
- Independent from main leadgen app

### Pipeline UI
- Status column: new → scraping → scraped → analyzing → target/rejected
- Segment label column (PAYMENTS, LENDING, etc.)
- Click row → modal with analysis details
- Company name normalization stored + passed to SmartLead

---

## 13. REPLY MONITORING
**File**: `services/reply_monitor.py`
**Frequency**: Every 3 minutes (background poller)
**Classification model**: `gpt-4o-mini`
**Draft generation model**: `gemini-2.5-pro`
**Categories**: interested, meeting_request, not_interested, out_of_office, wrong_person, unsubscribe, question, other
**Notifications**: Telegram bot for warm replies (interested, meeting_request)

## 11. OPERATOR LEARNING
**File**: `api/pipeline.py` (learning_router)
**Frontend**: `LearningPage.tsx` — Actions tab + Analytics tab
**Flow**:
1. AI classifies reply + generates draft response
2. Operator reviews on Actions page: approve or dismiss
3. System tracks approval rates per category
4. Golden examples accumulate for future improvement
