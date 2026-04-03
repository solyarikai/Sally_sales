# Data Pipeline & Chat System

## Overview

The data pipeline discovers target companies, extracts contacts, enriches them via Apollo, and pushes to SmartLead campaigns. The chat API is the primary interface for controlling the pipeline — it accepts natural language commands and translates them into structured pipeline actions via Gemini 2.5 Pro.

## Architecture

```
User Message (Chat UI / API / Slack / Telegram)
    │
    ▼
POST /api/search/chat
    │
    ▼
parse_chat_action()  ── Gemini 2.5 Pro (fallback: GPT-4o-mini)
    │
    ├── start_search  → Launch full pipeline
    ├── stop          → Stop running pipeline
    ├── status        → Show progress
    ├── push          → SmartLead push
    ├── show_targets  → List top targets
    ├── show_stats    → Analytics (segment/geo/engine/cost/funnel/top_queries)
    ├── clay_gather   → Full Clay pipeline (companies → contacts → CRM)
    ├── clay_export   → Clay company export only
    ├── clay_people   → Clay people search only
    ├── search        → Legacy ICP-based search
    └── info          → General questions
```

## Chat API

**Endpoint:** `POST /api/search/chat`

**Request:**
```json
{
  "message": "run yandex on real_estate for turkey and thailand, 2000 queries, push after",
  "project_id": 18,
  "max_queries": 2000,
  "target_goal": 500
}
```

**Parsed Action (by Gemini):**
```json
{
  "action": "start_search",
  "engine": "yandex",
  "segments": ["real_estate"],
  "geos": ["turkey", "thailand_bali"],
  "max_queries": 2000,
  "target_goal": 500,
  "skip_smartlead_push": false,
  "reply": "Launching Yandex search for real_estate in Turkey and Thailand..."
}
```

**Defaults:**
- Engine: `yandex` ($0.25/1K queries) — Google ($3.50/1K) only when explicitly requested
- Max queries: 1500
- Target goal: 500
- SmartLead push: enabled

## Pipeline Phases

### Phase 1: Segment Search

Runs for each segment+geo combination. Two query sources:

**A. Template Queries (zero AI cost):**
- Cartesian product of templates × variables × geos
- Example: `"{company_type_ru} {city_ru}"` × `["агентство недвижимости", "брокер"]` × `["Дубай", "Стамбул"]`
- Cap: 100 queries per geo
- Deduplication: project-wide, normalized (lowercase + whitespace)

**B. AI Expansion (when templates exhausted):**
- Up to 2 rounds × 30 queries per round
- Seeded with template queries + confirmed targets
- Model: GPT-4o-mini
- Only triggers if no targets found in Phase A

**Search execution:**
1. Execute queries against Yandex/Google
2. Collect new domains
3. Scrape domains via Crona API (JS-rendered)
4. Analyze with GPT-4o-mini (multi-criteria target scoring)

**Files:**
- `backend/app/services/company_search_service.py` — `run_segment_search()`
- `backend/app/services/query_templates.py` — `build_segment_queries()`, `build_doc_keyword_queries()`

### Phase 2: Contact Extraction

- Targets with no extracted contacts
- Batches of 20 companies
- GPT extracts contacts from scraped website content

**File:** `backend/app/api/pipeline.py` — `_bg_phase_extraction()`

### Phase 3: Apollo Enrichment

- Unenriched target companies
- Batches of 10
- Respects Apollo credits budget
- Finds people with target roles (CEO, Founder, etc.)

**File:** `backend/app/api/pipeline.py` — `_bg_phase_enrichment()`

### Phase 4: CRM Promote

- Upserts extracted contacts into the `contacts` table
- Adds `gathering_details` JSON (source, segment, geo, query)
- Updates existing contacts (fills NULL fields)

**File:** `backend/app/api/pipeline.py` — `_bg_phase_crm_promote()`

### Phase 5: SmartLead Push

- Loads active `CampaignPushRule` for the project
- Classifies contacts by language and name pattern
- Matches to campaign rules (priority-ordered)
- Pushes in batches of 100 to SmartLead API
- Verifies upload count after each batch
- Records in `pipeline_events` table

**File:** `backend/app/api/pipeline.py` — `_bg_phase_smartlead_push()`

## Campaign Push Rules

Each project has rules defining how contacts are routed to SmartLead campaigns:

| Field | Description |
|-------|-------------|
| `language` | `ru`, `en`, or `any` |
| `has_first_name` | `true` = requires name, `false` = generic emails |
| `campaign_name_template` | SmartLead campaign name |
| `sequence_language` | Sequence language for emails |
| `use_first_name_var` | Whether to use `{{first_name}}` in sequences |
| `max_leads_per_campaign` | Lead cap per campaign (default 5000) |
| `priority` | Higher = checked first |

**Deliryo example (project_id=18):**

| Rule | Language | Has Name | Priority |
|------|----------|----------|----------|
| Deliryo БЕЗ ИМЕНИ | any | false | 10 |
| Deliryo Англ имена | en | true | 5 |
| Deliryo Из РФ | ru | true | 1 |

## Available Segments

| Segment | Priority | Geos |
|---------|----------|------|
| `real_estate` | 1 | dubai, turkey, cyprus, thailand_bali, montenegro, spain_portugal, greece, london, israel, italy |
| `investment` | 2 | moscow, switzerland, dubai_difc, singapore |
| `legal` | 3 | moscow, cyprus_legal, uae_legal, serbia_legal, georgia_legal, israel, london, malta, estonia, offshore |
| `migration` | 4 | portugal_gv, spain_gv, greece_gv, montenegro_rp, general_migration, caribbean_cbi, uae_visa, eb5_usa, malta_rp, uk_visa, italy_gv |
| `crypto` | 5 | dubai_crypto, moscow_crypto |
| `family_office` | 6 | switzerland_fo, dubai_fo, moscow_fo, singapore_fo, ppli_insurance, private_banks_ru |
| `importers` | 7 | moscow_import |

## Clay TAM Gathering (clay_gather)

The Clay gather pipeline finds companies and contacts via Clay.com automation. The operator types a natural-language gather command in the project chat; the system runs a 5-step background pipeline and writes results to CRM.

### Trigger

User writes in project chat:
```
gather 30 contacts from 10 companies in content creator platforms segment
```

Gemini 2.5 Pro parses this as:
```json
{
  "action": "clay_gather",
  "clay_segment": "content creator platforms",
  "clay_company_count": 10,
  "clay_contact_count": 30
}
```

### Pipeline Steps

```
User message
    │
    ▼
parse_chat_action()  ── Gemini 2.5 Pro
    │  action = clay_gather
    ▼
Immediate SSE response (job plan + ETA)
    │
    ▼
Background task: _run_clay_gather_task()
    │
    ├── Step 1/5: Find Companies ──────────────────────────
    │   ├─ map_icp_to_clay_filters() — Gemini 2.5 Pro
    │   │  ICP text → {industries, sizes, keywords, exclusions}
    │   ├─ run_tam_export() — Puppeteer headless browser
    │   │  Clay.com → Find Companies → apply filters → Save to table
    │   └─ Read company data via Clay API (0 credits)
    │
    ├── Step 2/5: Save to Pipeline ────────────────────────
    │   └─ Upsert DiscoveredCompany records (is_target=true)
    │
    ├── Step 3/5: Find Contacts ───────────────────────────
    │   ├─ run_people_search() — Puppeteer headless browser
    │   │  Clay.com → People tab → domain list → title filters → Save
    │   └─ Read people data via Clay API (0 credits)
    │
    ├── Step 4/5: Apply Office Rules ──────────────────────
    │   ├─ Max 5 contacts per company+location
    │   ├─ Sort by role priority (CEO=1 … Manager=7 … Other=99)
    │   └─ Tag decision-makers (priority ≤ 6)
    │
    └── Step 5/5: Save to CRM ─────────────────────────────
        ├─ Build email: real > linkedin placeholder > name@domain
        ├─ Dedup by email / linkedin / name+domain
        ├─ INSERT contacts (status=draft, source=pipeline)
        └─ Segment label: "{description} #{job_id}"
```

### ICP-to-Clay Filter Mapping

Gemini 2.5 Pro (fallback: GPT-4o-mini) maps the operator's segment description to Clay search filters:

```json
{
  "industries": ["Online Audio and Video Media", "Internet Publishing"],
  "industries_exclude": ["Advertising Services", "Staffing and Recruiting"],
  "sizes": ["11-50", "51-200", "201-500"],
  "description_keywords": ["creator economy", "platform for creators"],
  "description_keywords_exclude": ["agency", "consulting"],
  "country_names": []
}
```

The ICP text is the operator's segment description only — project context is never appended (it confuses the AI into mapping to the project's existing ICP instead of the requested segment).

### Clay Puppeteer Automation

Both company and people searches use headless Chrome via Puppeteer:

1. **Session validation** — checks `claysession` cookie on `api.clay.com`
2. **Apply filters** — clicks UI elements for industries, sizes, keywords, exclusions
3. **Save to table** — Continue → "Save to new workbook and table" → Create table (skip enrichments)
4. **Read via API** — `GET /v3/tables/{id}/records` with session cookie (not API key)
5. **Zero credits** — table creation and export don't cost Clay credits

**>5000 companies**: If results exceed 5000 (Clay's export limit), the pipeline splits by geographic region (NA, EU West, EU East, APAC, LATAM, MEA, Rest of World) and runs multiple searches.

**Key files:**
- `scripts/clay/clay_tam_export.js` — company search automation
- `scripts/clay/clay_people_search.js` — people search automation
- `backend/app/services/clay_service.py` — `map_icp_to_clay_filters()`, `run_tam_export()`, `run_people_search()`

### Contact Email Strategy

Clay People search often returns contacts with LinkedIn URLs but no emails:

| Priority | Email source | Example |
|----------|-------------|---------|
| 1 | Real email from Clay | `john@company.com` |
| 2 | LinkedIn placeholder | `john-doe-abc123@linkedin.placeholder` |
| 3 | Name + domain | `john.doe@company.com` |
| 4 | No email possible | Contact skipped |

Placeholder emails ensure contacts are saved to CRM (email is NOT NULL). Real email verification via FindyMail happens later.

### Office Rules (contact_rules_service.py)

| Rule | Value |
|------|-------|
| Max contacts per office | 5 |
| Office = | company name + normalized location |
| Role priority | CEO=1, CTO/COO=2, CFO/CMO=3, VP=4, Director=5, Head=6, Manager=7, Other=99 |
| Decision-maker | role_priority ≤ 6 |

Contacts sorted: decision-makers first, then by role priority ascending.

### Real-Time Progress Updates

The background task emits progress via `ProjectChatMessage` records:

| action_type | UI rendering |
|-------------|-------------|
| `clay_gather_substep` | Compact inline status (spinner on last) |
| `clay_gather_progress` | Blue card with spinner + markdown |
| `clay_gather_done` | Green card with checkmark + results table |
| `clay_gather_error` | Red card with alert |

Frontend receives updates via persistent EventSource on `/api/search/chat/live/{project_id}`.

### Done Message

The completion message includes a markdown table with stats plus three clickable links:

```
**Gather complete** — 4m 43s

| | |
|---|---|
| Companies found | **209** (saved **5**) |
| Contacts found | **22** → **17** after office rules |
| Decision-makers | **0** of 17 |
| CRM draft | **17** contacts |
| Segment | content creator platforms #605 |

- Industries: Online Audio and Video Media, Internet Publishing, ...
- Keywords: creator economy, content creator platform, ...
- Sizes: 1-10, 11-50, 51-200, ...

[Companies in Clay →](clay_url) | [People in Clay →](clay_url) | [Open CRM →](/contacts?...)
```

### Segment Label in CRM

Each gather run creates a unique segment label: `"{description} #{job_id}"` (e.g., "content creator platforms #605"). The CRM link filters by this segment so the operator sees only contacts from that specific run.

### Data Flow Summary

| Table | What's stored |
|-------|--------------|
| `project_chat_messages` | All chat messages + progress steps + done message |
| `search_jobs` | Job metadata (engine=CLAY, status, config with filters) |
| `discovered_companies` | Clay-found companies (domain, name, is_target, company_info with clay_filters) |
| `extracted_contacts` | Raw contacts from Clay (source=CLAY, raw_data with role_priority) |
| `contacts` | CRM contacts (status=draft, source=pipeline, segment label, provenance JSON) |

### Costs

Clay gather costs **zero Clay credits** — it uses table creation + API read, not enrichment. The only cost is Gemini 2.5 Pro for ICP filter mapping (~$0.001 per call).

## CRM Export

**Google Sheet export:** `POST /api/contacts/export/google-sheet`
- Accepts all CRM filters (project_id, campaign, segment, status, date range, search)
- Exports all matching contacts (no pagination)
- Creates a shared Google Sheet via Drive API

**CSV export:** `POST /api/contacts/export/csv`
- Same filter support as Google Sheet
- Downloads as CSV file

**Campaign verification:** `GET /api/contacts/verify-campaigns?project_id=18`
- Compares DB contact counts vs SmartLead lead counts per campaign
- Returns match/mismatch status

## Costs

| Service | Cost | Usage |
|---------|------|-------|
| Yandex Search API | $0.25 / 1K queries | Primary search engine |
| Google SERP (Apify) | $3.50 / 1K queries | English/international queries |
| Apollo | ~$0.01 / contact | Email enrichment |
| GPT-4o-mini | ~$0.15/1M input tokens | Domain analysis, query expansion |
| Gemini 2.5 Pro | ~$1.25/1M input tokens | Chat intent parsing |
| Crona | ~$0.001 / domain | Website scraping |

## Key Configuration

- Search concurrency: segments in parallel, geos sequential within segment
- GPT analysis concurrency: 25 (semaphore)
- SmartLead batch: 100 leads per upload, 3s delay between batches
- Apollo batch: 10 companies
- Extraction batch: 20 companies
- Max queries per geo: 100 (template cap)
- AI expansion: 2 rounds × 30 queries (when templates exhausted)
