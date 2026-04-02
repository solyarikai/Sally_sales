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
  ]
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

## 5. FILTER GENERATION (tam_gather → filter_mapper)

### Filter Classification

**Mandatory** (MCP must have before pipeline starts, asks user if missing):
- **Geo** (locations) — from user query or document
- **Segments** (query describing target companies) — from user query or document

**Inferred** (GPT derives automatically, no need to ask user):
- **Size** (employee range) — GPT infers from offer context
- **Industries** (Apollo industry names) — GPT picks 2-3 from 84 real Apollo industries
- **Keywords** (free-text search terms) — GPT generates 20-30 freely

**Prioritization** (nice-to-have, graceful degradation):
- **Funding** (series_a, series_b) — from document. Applied when Apollo has data, silently dropped when exhausted. Unfunded streams continue in parallel.

### Step A: Industry Selection
**File**: `services/filter_mapper.py:_pick_industries()`
**Model**: `gpt-4.1-mini` (fallback: `gpt-4o-mini`)
**Input**: User query + 84 real Apollo industry names (from `apollo_taxonomy` table, all with tag_ids)
**Prompt**: `"[query]" — pick 2-3 matching Apollo industries. [84 industries] JSON: {"industries": ["exact name"]}`
**Output**: 2-3 industry names → direct tag_id lookup (no separate map table)

### Step B: Keyword + Employee Size Generation
**File**: `services/filter_mapper.py:_generate_keywords()`
**Model**: `gpt-4.1-mini` (fallback: `gpt-4o-mini`)
**Input**: User query + offer description + seed keywords (from document, if available)
**Prompt**:
```
Generate Apollo.io search keywords for finding B2B companies.

User's segment: {query}
User's product: {offer}

SEED KEYWORDS (from user's strategy document):
[document keywords if available — used as starting point]

Generate 20-30 keywords that target companies would have on their Apollo profiles.
Include: industry terms, product/service names, technology names, synonyms,
adjacent niches, specific sub-sectors, business model descriptors.

EMPLOYEE SIZE
Pick 1-3 ranges that match the typical BUYER...
```
**Output**: `{keywords: [...], employee_ranges: [...]}`

**Note**: Apollo accepts ANY free-text in `q_organization_keyword_tags`. No predefined keyword list or validation needed. GPT generates freely.

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

### Final Filter Assembly
```
{
  "q_organization_keyword_tags": [industry_names + generated_keywords],
  "organization_industry_tag_ids": [tag_ids from industry lookup],
  "organization_locations": ["Country1", "Country2"],
  "organization_num_employees_ranges": ["20,500"],
  "organization_latest_funding_stage_cd": ["series_a"],  // prioritization, from document
  "mapping_details": {industries, keywords, tag_ids, model_used, seed_count}
}
```

## 6. APOLLO PROBE
**File**: `services/filter_intelligence.py:probe_and_scrape()`
**Input**: Final assembled filters
**Method**: Apollo API `/organizations/search` (1 credit per call)
**Output**: `total_available` companies, sample results for preview

## 7. PIPELINE PREVIEW → USER APPROVAL
**File**: `mcp/dispatcher.py` (tam_gather PREVIEW mode)
**Shows user**: All keywords, industries, tag_ids, cost estimate, KPIs, pipeline link
**Waits for**: User says "Proceed?" → `tam_gather(confirm_filters=true)`

**MCP agent behavior**:
- User provides query + geo → show preview, ask only "Proceed?"
- User provides query without geo → ask "Which location?"
- User provides only website → after project creation, ask "What companies and where?"
- Document provides everything → show preview, ask only "Proceed?"

## 8. AUTONOMOUS PIPELINE
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
**Method**: Apollo `/mixed_people/api_search` (FREE, no credits)
**Config**: 3 contacts per target company (20 concurrent)
**Roles**: Auto-adjusted based on project's offer:
- Payroll offer → VP HR, CHRO, Head of People
- SaaS offer → CTO, VP Engineering
- Fashion offer → Brand Director, CMO
**Priority**: owner/founder > c_suite > vp > head > director

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

## 9. REPLY MONITORING
**File**: `services/reply_monitor.py`
**Frequency**: Every 3 minutes (background poller)
**Classification model**: `gpt-4o-mini`
**Draft generation model**: `gemini-2.5-pro`
**Categories**: interested, meeting_request, not_interested, out_of_office, wrong_person, unsubscribe, question, other
**Notifications**: Telegram bot for warm replies (interested, meeting_request)

## 10. OPERATOR LEARNING
**File**: `api/pipeline.py` (learning_router)
**Frontend**: `LearningPage.tsx` — Actions tab + Analytics tab
**Flow**:
1. AI classifies reply + generates draft response
2. Operator reviews on Actions page: approve or dismiss
3. System tracks approval rates per category
4. Golden examples accumulate for future improvement
