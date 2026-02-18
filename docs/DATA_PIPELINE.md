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
