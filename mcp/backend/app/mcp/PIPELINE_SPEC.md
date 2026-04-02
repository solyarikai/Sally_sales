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
    "combined_keywords": [...],  // all segment keywords merged (60-80)
    "locations": ["United States", "United Kingdom"],
    "employee_range": "20,500",
    "industries": ["financial services"],
    "funding_stages": ["series_a", "series_b"]
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

## 5. KEYWORD GENERATION (tam_gather → filter_mapper)

### Step A: Taxonomy Embedding Search
**File**: `services/taxonomy_service.py:get_keyword_shortlist()`
**Model**: `text-embedding-3-small` (OpenAI embeddings)
**Input**: User query (e.g., "fintech companies in US")
**Method**: 
1. Embed query using OpenAI embeddings API
2. pgvector cosine similarity search on `apollo_taxonomy` table (2,356 known keywords)
3. Return top 50 most semantically similar keywords
**Output**: `keyword_shortlist` — 50 Apollo keywords ranked by relevance

### Step A2: Seed Keyword Injection
**File**: `services/filter_mapper.py` (inline in `map_query_to_filters()`)
**Input**: Document-extracted segment keywords (if project created from document)
**Method**: Merge seed keywords into shortlist, deduplicate, seeds placed first for priority
**Output**: Enriched shortlist (50 taxonomy + N document seeds)

### Step B1: Industry Selection
**File**: `services/filter_mapper.py:_pick_industries()`
**Model**: `gpt-4.1-mini` (fallback: `gpt-4o-mini`)
**Prompt**: `"[query]" — 2-3 matching industries. [full industry list] JSON: {"industries": ["exact name"]}`
**Output**: 2-3 Apollo industry names

### Step B2: Keyword + Employee Size Selection
**File**: `services/filter_mapper.py:_gpt_pick_filters()`
**Model**: `gpt-4.1-mini` (fallback: `gpt-4o-mini`)
**Prompt**: 
```
You map business queries to Apollo.io search filters.
Select ONLY from the lists provided. Never invent.

User's segment: {query}
User's product: {offer}

SEED KEYWORDS (from user's strategy document — PRIORITIZE these):
[document keywords if available]

KEYWORDS
Filtering Apollo for "{query}" — pick 20-30 keywords...
[enriched shortlist: taxonomy matches + document seeds]

EMPLOYEE SIZE
Pick 1-3 ranges that match the typical BUYER...
```
**Output**: `{keywords: [...], unverified_keywords: [...], employee_ranges: [...]}`

### Step C: Industry Specificity Classification
**File**: `services/industry_classifier.py:classify_industry_specificity()`
**Model**: `gpt-4.1-mini`
**Input**: Query + selected industries
**Output**: Strategy recommendation: `industry_first` | `keywords_first` | `keywords_only`

### Step D: Location Extraction
**File**: `services/filter_mapper.py:_extract_locations()`
**Method**: Regex parsing (no GPT) — extracts "in Miami", "in US and UK"
**Note**: Document locations override this if available

### Step E: Document Structural Overrides
**File**: `mcp/dispatcher.py` (inline in tam_gather handler)
**Applied from document if available**:
- Locations (override filter_mapper's regex)
- Funding stages (filter_mapper never extracts this)
- Employee range (if filter_mapper didn't set one)
- Keywords are NOT overridden — they're seeded into filter_mapper instead

### Final Filter Assembly
```
{
  "q_organization_keyword_tags": [industries + verified_keywords + unverified_to_fill],
  "organization_industry_tag_ids": [specific_tag_ids if industry_first strategy],
  "organization_locations": ["Country1", "Country2"],
  "organization_num_employees_ranges": ["20,500"],
  "organization_latest_funding_stage_cd": ["series_a"],  // from document only
  "filter_strategy": "industry_first | keywords_first | keywords_only",
  "mapping_details": {full audit trail}
}
```

## 6. APOLLO PROBE
**File**: `services/filter_intelligence.py:probe_and_scrape()`
**Input**: Final assembled filters
**Method**: Apollo API `/organizations/search` (1 credit per call)
**Output**: `total_available` companies, sample results for preview

## 7. PIPELINE PREVIEW → USER APPROVAL
**File**: `mcp/dispatcher.py` (tam_gather PREVIEW mode)
**Shows user**: All keywords, strategy reasoning, cost estimate, KPIs, pipeline link
**Waits for**: User says "Proceed?" → `tam_gather(confirm_filters=true)`

## 8. AUTONOMOUS PIPELINE
**File**: `services/pipeline_orchestrator.py`
**Runs in background after user confirms**

### Phase 1: Gather
- Apollo API pages (25 companies/page, 4 concurrent pages)
- Stores as `DiscoveredCompany` records

### Phase 2: Scrape
- Website content via Apify residential proxy
- BeautifulSoup HTML → clean text
- Stored as `CompanyScrape` records

### Phase 3: Classify (via negativa)
**Model**: `gpt-4o-mini`
**Prompt**: Analyzes scraped website content against project's ICP
**Method**: Via negativa — focuses on EXCLUDING non-matches
**Output per company**:
- `is_target`: bool
- `confidence`: 0-100
- `segment`: CAPS_LOCKED label (PAYMENTS, LENDING, etc.)
- `reasoning`: Why target/not-target

### Phase 4: Extract People
**Method**: Apollo `/mixed_people/api_search` (FREE, no credits)
**Config**: 3 contacts per target company
**Roles**: Auto-adjusted based on project's offer (payroll→HR, SaaS→CTO, fashion→CMO)

### Phase 5: Auto-Push to SmartLead
**Trigger**: When KPI met (default: 100 people, 3/company)
**Creates**: SmartLead DRAFT campaign with:
- Generated email sequence (4-5 steps)
- Selected sending accounts
- Uploaded target contacts
- Test email sent to user

**Default KPIs**: `target_people=100`, `max_people_per_company=3`

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
