# Data Pipeline — Complete Technical Documentation

End-to-end documentation of the AI-driven company search, scoring, review, and outreach pipeline.

---

## Table of Contents

1. [Pipeline Overview](#1-pipeline-overview)
2. [Query Generation](#2-query-generation)
3. [Search Engines](#3-search-engines)
4. [Domain Filtering & Blacklisting](#4-domain-filtering--blacklisting)
5. [Website Scraping (Crona)](#5-website-scraping-crona)
6. [GPT Company Analysis & Scoring](#6-gpt-company-analysis--scoring)
7. [Post-Processing Validation](#7-post-processing-validation)
8. [Auto-Review](#8-auto-review)
9. [Blacklist & Skip Logic](#9-blacklist--skip-logic)
10. [Knowledge Accumulation & Feedback Loop](#10-knowledge-accumulation--feedback-loop)
11. [Iterative Self-Improving Pipeline](#11-iterative-self-improving-pipeline)
12. [Outreach Pipeline (Post-Search)](#12-outreach-pipeline-post-search)
13. [Domain-Campaign Exclusion](#13-domain-campaign-exclusion)
14. [API Endpoints Reference](#14-api-endpoints-reference)
15. [GPT Prompts Reference](#15-gpt-prompts-reference)
16. [External APIs & Credentials](#16-external-apis--credentials)
17. [Configuration Reference](#17-configuration-reference)
18. [Cost Model](#18-cost-model)
19. [Database Models](#19-database-models)

---

## 1. Pipeline Overview

```
                    +-----------------------+
                    |   Project Config      |
                    | (target_segments)     |
                    +----------+------------+
                               |
                    +----------v------------+
                    | 1. Query Generation   |  GPT-4o-mini
                    |    (50 per batch)     |  temp=0.95
                    +----------+------------+
                               |
                    +----------v------------+
                    | 2. Yandex Search API  |  3 pages/query
                    |    (async/deferred)   |  8 workers
                    +----------+------------+
                               |
                    +----------v------------+
                    | 3. Domain Filtering   |  Trash patterns
                    |    Blacklist + Dedup  |  6936 blacklist
                    +----------+------------+
                               |
                    +----------v------------+
                    | 4. Website Scraping   |  Crona API (JS)
                    |    (batch, 50/batch)  |  or httpx fallback
                    +----------+------------+
                               |
                    +----------v------------+
                    | 5. GPT Analysis       |  Multi-criteria
                    |    (20 concurrent)    |  scoring rubric
                    +----------+------------+
                               |
                    +----------v------------+
                    | 6. Validation         |  Hard rules
                    |    (override GPT)     |  override GPT
                    +----------+------------+
                               |
                    +----------v------------+
                    | 7. Auto-Review        |  Batches of 20
                    |    CONFIRM/REJECT/FLAG|  GPT second pass
                    +----------+------------+
                               |
              +----------------+----------------+
              |                                 |
   +----------v----------+          +-----------v-----------+
   | 8. Knowledge Update |          | 9. Auto-Promote       |
   |    (patterns,       |          |    to DiscoveredCompany|
   |     effectiveness)  |          +-----------+-----------+
   +----------+----------+                      |
              |                      +-----------v-----------+
              +----> NEXT ITERATION  | 10. Contact Extract   |
                    (if < target_goal)|     Apollo Enrich     |
                                     +-----------+-----------+
                                                 |
                                     +-----------v-----------+
                                     | 11. Promote to CRM    |
                                     +-----------------------+
```

**File**: `backend/app/services/company_search_service.py` (orchestrator)

The pipeline is iterative. It generates batches of queries, searches, scrapes, analyzes, reviews, then loops. Each iteration feeds knowledge from prior results back into query generation.

---

## 2. Query Generation

**File**: `backend/app/services/search_service.py`
- Prompt builder: `build_project_query_prompt()` → `search_service.py:52`
- GPT call: `SearchService.generate_queries()` → `search_service.py:233`
- API endpoint: `POST /search/generate-queries` → `backend/app/api/search.py:87`

### How it works

1. Takes `project.target_segments` (free-text description of ideal customer)
2. Samples up to 30 existing queries for dedup context (reservoir sampling)
3. Injects feedback from prior iterations:
   - **Good queries**: queries with `effectiveness_score > 0.3` (found targets)
   - **Bad queries**: queries with `effectiveness_score == 0` but `domains_found > 0` (found only junk)
   - **Confirmed target domains**: up to 30 domains confirmed as targets
4. Sends to GPT-4o-mini with `temperature=0.95` for diversity
5. Deduplicates output against all previously used queries (normalized lowercase comparison)
6. Filters queries shorter than 8 chars

### GPT Prompt (Russian)

```
System: "You are an expert at generating diverse B2B search queries..."

User: "Ты - эксперт по генерации поисковых запросов для B2B лидогенерации.

ЦЕЛЕВОЙ СЕГМЕНТ: {target_segments}

ЗАДАЧА: Сгенерируй поисковые запросы...

ПРАВИЛА:
- 3-8 слов per query
- 85% Russian, 15% English
- No informational queries ("что такое...")
- No buyer intent ("купить...")
- No job queries ("вакансии...")

ВАРИАЦИИ:
- Direct: "[company type] [city]"
- Refined: "[company type] для [audience]"
- Geographic: vary Russian cities
- English: for Russian companies with English sites

УЖЕ ИСПОЛЬЗОВАННЫЕ ЗАПРОСЫ (НЕ ПОВТОРЯЙ!):
{existing_sample}

ЭФФЕКТИВНЫЕ ЗАПРОСЫ (генерируй похожие):
{good_queries}

НЕЭФФЕКТИВНЫЕ ЗАПРОСЫ (НЕ генерируй похожие):
{bad_queries}

ПОДТВЕРЖДЁННЫЕ ЦЕЛЕВЫЕ ДОМЕНЫ (генерируй запросы, которые нашли бы похожие):
{confirmed_targets}"
```

**Model**: `gpt-4o-mini` | **Temperature**: `0.95` | **Max tokens**: `4000`

---

## 3. Search Engines

### Yandex Cloud Search API (primary)

**File**: `backend/app/services/search_service.py`
- Search function: `_yandex_search_single_query()` → `search_service.py:431`
- Poll function: `_yandex_poll_operation()` → `search_service.py:499`
- POST request: `search_service.py:458` → `POST {YANDEX_SEARCH_API_URL}` (= `https://searchapi.api.cloud.yandex.net/v2/web/searchAsync`)
- Poll request: `search_service.py:513` → `GET {YANDEX_OPERATIONS_URL}/{operation_id}` (= `https://operation.api.cloud.yandex.net/operations/{id}`)

| Setting | Value | Config key |
|---------|-------|------------|
| API URL | `https://searchapi.api.cloud.yandex.net/v2/web/searchAsync` | `settings.YANDEX_SEARCH_API_URL` |
| Operations URL | `https://operation.api.cloud.yandex.net/operations` | `settings.YANDEX_OPERATIONS_URL` |
| Auth | `Api-Key {YANDEX_SEARCH_API_KEY}` header | `settings.YANDEX_SEARCH_API_KEY` |
| Folder ID | in request body | `settings.YANDEX_SEARCH_FOLDER_ID` |
| Search type | `SEARCH_TYPE_RU` | hardcoded |
| Response format | `FORMAT_HTML` (parsed for domains) | hardcoded |
| Pages per query | `SEARCH_MAX_PAGES` (default 3) | `settings.SEARCH_MAX_PAGES` |
| Concurrent workers | `SEARCH_WORKERS` (default 8) | `settings.SEARCH_WORKERS` |
| Mode | Async/deferred: POST creates operation, poll GET until `done=true` | — |
| Response decoding | Base64-encoded HTML, decoded to UTF-8 | — |

**Flow per query:**
1. `POST /v2/web/searchAsync` (`search_service.py:458`) with `{"query": {"searchType": "SEARCH_TYPE_RU", "queryText": "...", "page": 0}, "folderId": "...", "responseFormat": "FORMAT_HTML"}`
2. Get `operation_id` from response (`search_service.py:474`)
3. Poll `GET /operations/{id}` every 1s, max 60s (`search_service.py:507-523`)
4. When `done=true`, decode `response.rawData` from base64 (`search_service.py:523`)
5. Parse HTML with `extract_domains_from_html()` (`search_service.py:484`)
6. Repeat for pages 0..2

**429 handling**: Sleep 5s and retry (`search_service.py:464-467`).

### Google SERP (secondary, via Apify proxy)

**File**: `backend/app/services/search_service.py`
- Search function: `_scrape_single_query()` → `search_service.py:348`
- HTTP request: `search_service.py:385-389`

| Setting | Value | Code location |
|---------|-------|---------------|
| Proxy URL | `http://groups-GOOGLE_SERP,session-{random}:{password}@{host}:{port}` | `search_service.py:357-361` |
| Search URL | `http://www.google.com/search?q={query}&num=100&start={page*10}&hl=ru` | `search_service.py:365` |
| Retries | 3 per page, exponential backoff (2^retry * 5s + random) | `search_service.py:373-380` |
| CAPTCHA detection | Checks for "unusual traffic", "captcha", "recaptcha" | — |
| User-Agent | Rotated from 5 browser-like agents | `search_service.py:368` |

### Domain extraction from SERP HTML

**Function**: `extract_domains_from_html()` → `search_service.py:169`

Two methods:
1. **Links** (`search_service.py:175`): Parse `<a href>`, follow `/url?q=` redirects, extract hostname
2. **Cite elements** (`search_service.py:189`): Parse `<cite>` text with regex for domain patterns

All extracted domains are passed through `normalize_domain()` and `matches_trash_pattern()` from `domain_service.py`.

---

## 4. Domain Filtering & Blacklisting

**File**: `backend/app/services/domain_service.py`
- Trash check: `matches_trash_pattern()` → `domain_service.py:72`
- Filter + persist: `DomainService.filter_domains()` → `domain_service.py:230`
- Normalize: `normalize_domain()` → `domain_service.py:55`

### Three-layer filtering

#### Layer 1: Hardcoded trash domains (`BASE_TRASH`)

~30 domains: `ya.ru`, `yandex.ru`, `google.com`, `avito.ru`, `vk.com`, `facebook.com`, `linkedin.com`, `twitter.com`, `wikipedia.org`, etc.

#### Layer 2: Pattern matching (`TRASH_PATTERNS`)

~50 substring patterns organized by category:

| Category | Examples |
|----------|----------|
| Social networks | `t.me`, `telegram`, `vk.com`, `facebook.com`, `instagram.com`, `tiktok.com` |
| News sites | `news.ru`, `ria.ru`, `lenta.ru`, `rbc.ru`, `kommersant`, `forbes` |
| Crypto exchanges | `binance.com`, `bybit.com`, `coinmarketcap`, `coinbase.com` |
| Russian banks | `banki.ru`, `tbank.ru`, `vtb.ru`, `sberbank`, `tinkoff` |
| Real estate | `tranio.`, `realting.com`, `cian.ru`, `domclick`, `avito.ru` |
| Travel | `booking.com`, `tripadvisor`, `airbnb` |
| Search/wikis | `wikipedia.org`, `yandex.ru`, `google.com`, `dzen.ru` |
| Payment | `wise.com`, `revolut.com`, `stripe.com`, `paypal` |

Matching is `pattern in domain` (substring match).

#### Layer 3: Blacklist file (`blacklist_domains.txt`)

- **6,936 domains** loaded from file at module import time
- Source: Exported from Deliryo's `blacklist.db`
- Exact domain match

### Domain registry workflow

**Function**: `DomainService.filter_domains()` (line 230)

For each domain from search results:
1. `normalize_domain()`: strip protocol, paths, `www.`, lowercase
2. Check `matches_trash_pattern()` → mark as TRASH in DB
3. Check batch dedup (within same search batch)
4. Check DB for existing `Domain` record → mark as DUPLICATE (increment `times_seen`)
5. Otherwise → mark as NEW, create `Domain(status=ACTIVE)` record

Returns: `{"new": [...], "trash": [...], "duplicate": [...]}`

---

## 5. Website Scraping (Crona)

**File**: `backend/app/services/crona_service.py`
**API**: `https://api.crona.ai`
**Account**: `pn@getsally.io`
**Cost**: 1 credit per domain

### Crona API Endpoints Used

All calls made from `backend/app/services/crona_service.py` :: `CronaService.scrape_domains()`.
Base URL: `settings.CRONA_API_URL` = `https://api.crona.ai`

| Step | Method | Endpoint | Code Location | Request Body / Params | Response |
|------|--------|----------|---------------|----------------------|----------|
| 1. Auth | `POST` | `/api/clients/sign_in` | `crona_service.py:55` | `{"client": {"email": "...", "password": "..."}}` | `{"jwt_token": "...", "credits_balance": 1234}` |
| 2. Balance | `GET` | `/api/whoami/credits_balance` | `crona_service.py:81` | — | `{"credits_balance": 1234}` |
| 3. Create project | `POST` | `/api/projects` | `crona_service.py:118` | `{"project": {"name": "scrape_20260210_183000"}}` | `{"id": 12345}` |
| 4. Upload CSV | `POST` | `/api/projects/{id}/source_file` | `crona_service.py:137` | multipart: `source_type=websites_list`, file=`domains.csv` (header: "website", rows: "https://domain.com") | — |
| 5. Add enricher | `POST` | `/api/projects/{id}/enrichers` | `crona_service.py:147` | `{"enricher": {"name": "Scrape Website", "field_name": "scraped_text", "type": "scrape_website", "order": 1, "arguments": {"based_on": "Website URL", "url_column": "website"}}}` | — |
| 6. Run project | `POST` | `/api/projects/{id}/project_runs` | `crona_service.py:165` | `{}` | — |
| 7. Poll status | `GET` | `/api/projects/{id}/status` | `crona_service.py:178` | — | `{"status": "completed\|running\|failed"}` |
| 8. Get results | `GET` | `/api/projects/{id}/last_results` | `crona_service.py:193` | — | `{"data": [["website","scraped_text"], ["https://x.com","...text..."], ...]}` |
| 9. Cleanup | `DELETE` | `/api/projects/{id}` | `crona_service.py:240` | — | — (best-effort, errors ignored) |

Auth header for steps 2-9: `Authorization: Bearer {jwt_token}` (token cached 6 days in memory, see `crona_service.py:46`).

### Flow

```
1. _authenticate() (line 46)    → POST /api/clients/sign_in → JWT token (cached 6 days)
2. scrape_domains() (line 117)  → POST /api/projects → create project with timestamped name
3. (line 136)                   → POST /api/projects/{id}/source_file → upload CSV: header "website", rows "https://{domain}"
4. (line 146)                   → POST /api/projects/{id}/enrichers → add scrape_website enricher
5. (line 164)                   → POST /api/projects/{id}/project_runs → start scraping
6. (line 173)                   → GET /api/projects/{id}/status → poll every 3s until "completed" or "failed" (max 120s)
7. (line 191)                   → GET /api/projects/{id}/last_results → fetch results: data[0]=header, data[1:]=[url, scraped_text]
8. finally (line 237)           → DELETE /api/projects/{id} → cleanup (best-effort)
```

### Batch processing

- Domains are batched in groups of 50
- Up to 3 Crona batches run in parallel (`asyncio.Semaphore(3)`)
- Returns **clean text** (not raw HTML) — Crona handles JS rendering

### Fallback: direct httpx

When Crona is not configured, falls back to direct `httpx.AsyncClient`:
- `GET https://{domain}` with browser-like headers
- `follow_redirects=True`, `verify=False` (bad SSL tolerance)
- Response capped at 50KB
- 3 concurrent (`asyncio.Semaphore(3)`)
- Does NOT render JavaScript — misses SPA sites

---

## 6. GPT Company Analysis & Scoring

**File**: `backend/app/services/company_search_service.py`
- GPT analysis: `analyze_company()` → `company_search_service.py:518`
- Text extraction: `_extract_clean_text()` → `company_search_service.py:60`
- Validation: `_validate_analysis()` → `company_search_service.py:138`
- Scrape + analyze batch: `_scrape_and_analyze_domains()` → `company_search_service.py:677`

### Input processing

1. **HTML → clean text** (`_extract_clean_text`, line 60):
   - If HTML: BeautifulSoup parses, strips `<script>`, `<style>`, `<nav>`, `<header>`, `<footer>`, `<aside>`, `<form>`, `<button>`, `<iframe>`, `<svg>`, `<noscript>`
   - Removes elements with classes/ids matching: `nav|menu|sidebar|footer|cookie|popup|modal|banner`
   - If Crona text: used as-is (already clean)
   - Cap at 6,000 chars
   - Extract `<title>` and `<meta name="description">`

2. **Language detection** via Cyrillic character ratio:
   - `> 0.15` → Russian
   - `< 0.02` → English
   - Otherwise → Other

### Multi-criteria scoring prompt

**System prompt:**
```
You are an expert at analyzing company websites to determine if they match
a B2B target customer segment. You use a strict multi-criteria scoring system.

CRITICAL RULES — violations mean AUTOMATIC FAILURE:
1. Non-Russian website + Russian target geography → ALL scores = 0, is_target = false
2. If your reasoning says the company doesn't match → confidence MUST be < 0.3, is_target MUST be false
3. Aggregators, directories, news sites, job boards, freelancer platforms → ALWAYS is_target = false
4. When in doubt → score LOW. False positives are WORSE than false negatives.
5. confidence = MINIMUM of all individual scores (never higher)

Respond ONLY with valid JSON.
```

**User prompt includes:**
- Knowledge context (if available): anti_keywords, rejected domains, industry keywords
- Target segment description
- Domain, title, meta description, detected language, cyrillic ratio
- Website text (up to 6000 chars)

**Scoring criteria** (each 0.0-1.0):

| Score | Meaning |
|-------|---------|
| `language_match` | 0 if site language doesn't match target geography |
| `industry_match` | 0 = wrong industry, 0.5 = adjacent, 1.0 = exact |
| `service_match` | How well services match target segment needs |
| `company_type` | 1.0 = real company, 0.5 = consulting, 0 = aggregator/news |
| `geography_match` | 1.0 = serves target geo, 0.5 = partial, 0 = different region |

**Output JSON:**
```json
{
  "scores": { "language_match": 0.9, "industry_match": 0.8, ... },
  "is_target": true,
  "confidence": 0.8,
  "reasoning": "explanation",
  "company_info": {
    "name": "...", "description": "...",
    "services": [...], "location": "...", "industry": "..."
  }
}
```

**Model**: `gpt-4o-mini` | **Temperature**: `0.1` | **Max tokens**: `600`
**Concurrency**: 20 concurrent GPT calls (`asyncio.Semaphore(20)`)

---

## 7. Post-Processing Validation

**File**: `backend/app/services/company_search_service.py` → `_validate_analysis()` at line 138

Hard rules that **override** GPT output. Applied after every GPT analysis call (called from `analyze_company()` at line 666).

### Rule 1: Non-Russian site check

If `cyrillic_ratio < 0.1`:
- Force `language_match = 0.0`
- If GPT said `is_target = true` → override to `false`, `confidence = 0.0`
- Prepend `[AUTO-REJECTED: non-Russian site, cyrillic_ratio=X]` to reasoning

### Rule 2: Confidence cap

`confidence` must not exceed the minimum individual score:
```python
min_score = min(scores.values())
if confidence > min_score:
    confidence = min_score
```

### Rule 3: Reasoning contradiction

Regex checks reasoning for negative indicators:
```
не (соответствует|подходит|относится|является|связан)
doesn't match | not (a match|relevant|related|target)
no (match|relevance|relation) | irrelevant | unrelated
wrong (industry|segment|sector)
```

If `is_target = true` but reasoning contains negatives:
- Override `is_target = false`, cap `confidence` at `0.2`
- Prepend `[AUTO-CORRECTED: reasoning contradicts is_target]` to reasoning

---

## 8. Auto-Review

**File**: `backend/app/services/review_service.py`
- Orchestrator: `review_batch()` → `review_service.py:33`
- GPT call: `_review_batch_gpt()` → `review_service.py:96`
- API endpoint: `POST /search/results/{id}/review` → `backend/app/api/search.py:666`

### Second-pass quality check

After analysis, all unreviewed results for a job are sent to GPT in batches of 20 for a quality review.

**Prompt:**
```
Review these search results for quality. Target segment: {target_segments}

RESULTS: [list of {id, domain, is_target, confidence, reasoning, scores, company_name, industry}]

Verdicts:
- CONFIRM: clearly matches, scores and reasoning consistent
- REJECT: clearly does NOT match (wrong industry/geography, aggregator, etc.)
- FLAG: uncertain, needs human review

RULES:
- is_target=true but language_match<0.3 → REJECT
- Reasoning says "doesn't match" but is_target=true → REJECT
- CRM tools, job boards, news, directories → always REJECT
- When in doubt → FLAG
```

**Model**: `gpt-4o-mini` | **Temperature**: `0.1` | **Max tokens**: `2000`

### Verdict application

| Verdict | Action |
|---------|--------|
| `CONFIRM` | `review_status = "confirmed"` |
| `REJECT` | `review_status = "rejected"`, `is_target = false`, `confidence = min(conf, 0.2)` |
| `FLAG` | `review_status = "flagged"` |

### Auto-blacklist on rejection

Rejected domains are automatically added to `ProjectBlacklist`:
```python
ProjectBlacklist(project_id=..., domain=..., reason="Auto-rejected by review", source="auto_review")
```

Also updates corresponding `DiscoveredCompany.status = REJECTED` if linked.

### Manual review

**Endpoint**: `POST /search/results/{result_id}/review`

Same verdict logic. Manual rejections also auto-blacklist with `source="manual"`.

---

## 9. Blacklist & Skip Logic

### What gets skipped (never re-processed)

**Function**: `_build_skip_set()` → `company_search_service.py:189`

Three sources merged into one skip set:

| Source | Logic |
|--------|-------|
| Already analyzed | `SearchResult.domain` where `analyzed_at >= (now - SEARCH_DOMAIN_RECHECK_DAYS)` |
| Blacklisted | `ProjectBlacklist.domain` for this project |
| Confirmed targets | `SearchResult.domain` where `is_target = true` |

Default `SEARCH_DOMAIN_RECHECK_DAYS = 365` — domains won't be re-analyzed within a year.

### Additionally filtered before analysis

In `_scrape_and_analyze_domains()` (line 694):
```python
existing_result = await session.execute(
    select(SearchResult.domain).where(
        SearchResult.project_id == job.project_id,
        SearchResult.domain.in_(domains),
    )
)
```
Domains already having a `SearchResult` for this project are skipped.

### ProjectBlacklist table

| Column | Type | Description |
|--------|------|-------------|
| `id` | int | PK |
| `project_id` | int | FK to projects |
| `domain` | str | Blacklisted domain |
| `reason` | str | Why blacklisted |
| `source` | str | `"auto_review"`, `"manual"`, etc. |
| `created_at` | datetime | When added |

---

## 10. Knowledge Accumulation & Feedback Loop

**File**: `backend/app/services/review_service.py`
- Knowledge update: `update_project_knowledge()` → `review_service.py:386`
- Query effectiveness: `compute_query_effectiveness()` → `review_service.py:348`

### What gets stored in `ProjectSearchKnowledge`

After every review batch:

| Field | Source | Used for |
|-------|--------|----------|
| `confirmed_domains` | Domains with `review_status = "confirmed"` (up to 200) | Skip set, feedback |
| `rejected_domains` | Domains with `review_status = "rejected"` (up to 200) | Knowledge context, skip |
| `industry_keywords` | Industries + services from confirmed targets (up to 100) | Prompt injection |
| `anti_keywords` | Industries from rejected results (up to 100) | Prompt injection |
| `good_query_patterns` | Queries with `effectiveness_score > 0.3` (up to 50) | Query generation feedback |
| `bad_query_patterns` | Queries with score=0 but domains_found>0 (up to 50) | Query generation feedback |
| `avg_target_confidence` | Mean confidence of confirmed results | Calibration |
| `avg_false_positive_confidence` | Mean confidence of rejected results | Calibration |
| `total_domains_analyzed` | Count of all reviewed results | Stats |
| `total_targets_found` | Count of confirmed results | Stats |
| `total_false_positives` | Count of rejected results | Stats |
| `total_jobs_run` | Count of search jobs for project | Stats |

### Query effectiveness scoring

**Function**: `compute_query_effectiveness()` (line 348)

After review, each query gets an effectiveness score:
```python
query.effectiveness_score = targets_found / max(domains_found, 1)
```

A query that found 3 domains and 2 were confirmed targets gets `0.67`.

### How knowledge feeds back into the pipeline

1. **Query generation**: Good/bad query patterns and confirmed targets injected into GPT prompt
2. **Company analysis**: Knowledge context injected into scoring prompt:
   - `anti_keywords` → "KNOWN FALSE POSITIVE PATTERNS (auto-reject if matching)"
   - `rejected_domains` → "PREVIOUSLY REJECTED DOMAINS (similar = likely false positive)"
   - `industry_keywords` → "CONFIRMED TARGET CHARACTERISTICS"

---

## 11. Iterative Self-Improving Pipeline

**File**: `company_search_service.py` → `run_project_search()` at line 233
- API endpoint: `POST /search/projects/{id}/run` → `backend/app/api/search.py:448`
- Background task: `_run_project_search_background()` → `backend/app/api/search.py:495`

### Iteration loop

```
while existing_targets < target_goal AND iteration < max_iterations:
    1. Generate batch_size queries (with feedback from prior iterations)
    2. Run Yandex search
    3. Build skip set
    4. Get new domains (not in skip set)
    5. Scrape + analyze new domains
    6. Auto-review results
    7. Update knowledge (query effectiveness, patterns)
    8. Reload knowledge for next iteration
    9. Check target count
```

### Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `SEARCH_TARGET_GOAL` | 1000 | Stop when this many targets found |
| `SEARCH_BATCH_QUERIES` | 50 | Queries per iteration |
| `SEARCH_MAX_ITERATIONS` | 30 | Safety cap |
| `SEARCH_MAX_PAGES` | 3 | Yandex pages per query |
| `SEARCH_WORKERS` | 8 | Concurrent Yandex workers |

### Self-improvement mechanism

Each iteration is smarter than the last:
1. **Query dedup**: All previously used queries are excluded
2. **Good queries amplified**: Effective queries inspire new similar ones
3. **Bad queries suppressed**: Ineffective patterns avoided
4. **Skip set grows**: Already-analyzed + blacklisted + confirmed domains all skipped
5. **Knowledge context enriched**: More confirmed/rejected examples in analysis prompt

---

## 12. Outreach Pipeline (Post-Search)

### Auto-promotion to DiscoveredCompany

**File**: `company_search_service.py:834` (called inside `_scrape_and_analyze_domains()` at line 677)
**Service**: `pipeline_service.promote_search_results()` → `backend/app/services/pipeline_service.py`

After scrape+analyze, `pipeline_service.promote_search_results()` automatically creates `DiscoveredCompany` records from `SearchResult` entries.

### Pipeline stages

| Stage | API Endpoint | Service |
|-------|-------------|---------|
| List companies | `GET /pipeline/discovered-companies` | `pipeline_service.list_discovered_companies()` |
| View detail | `GET /pipeline/discovered-companies/{id}` | `pipeline_service.get_discovered_company_detail()` |
| Extract contacts | `POST /pipeline/extract-contacts` | GPT extracts from scraped HTML |
| Apollo enrichment | `POST /pipeline/enrich-apollo` | Apollo.io people search by domain |
| Promote to CRM | `POST /pipeline/promote-to-crm` | Creates `Contact` records |
| Bulk status | `POST /pipeline/update-status` | Bulk update discovered company status |
| Export CSV | `GET /pipeline/export-csv` | Download as CSV |
| Stats | `GET /pipeline/stats` | Pipeline statistics |

### Contact Extraction (GPT)

**File**: `backend/app/services/contact_extraction_service.py`

Sends first 12,000 chars of scraped content to GPT:
```
Extract all contact information from this website content.
WEBSITE DOMAIN: {domain}
WEBSITE CONTENT: {html_excerpt}
```

Returns: `[{email, phone, first_name, last_name, job_title, confidence}]`

**Generic email filter**: Emails starting with `info@`, `support@`, `contact@`, `noreply@`, `admin@`, `sales@`, `help@`, `hello@`, `office@`, `mail@`, `webmaster@`, `marketing@`, `team@`, `feedback@`, `service@` get `confidence = 0.3`.

Also has regex fallbacks: `extract_emails_regex()` and `extract_phones_regex()` for Russian phone patterns.

### Apollo Enrichment

**File**: `backend/app/services/apollo_service.py`

| Setting | Value |
|---------|-------|
| API URL | `https://api.apollo.io/api/v1` |
| Endpoint | `POST /mixed_people/search` |
| Auth | `api_key` in request body |
| Default limit | 5 people per domain |

Payload:
```json
{
  "api_key": "...",
  "q_organization_domains": "example.com",
  "page": 1,
  "per_page": 5,
  "person_titles": ["CEO", "CTO", "VP"]  // optional
}
```

Returns people with: `email`, `first_name`, `last_name`, `job_title` (`title`), `linkedin_url`, `is_verified` (from `email_status == "verified"`), `phone`, `raw_data` (id, organization, headline, city, seniority, departments).

---

## 13. Domain-Campaign Exclusion

**File**: `backend/app/api/search.py` → `get_domain_campaigns()` at line 1164
**Endpoint**: `POST /search/domain-campaigns`

### How SmartLead/GetSales exclusion works

The frontend loads campaign overlap data to show which search result domains are already being contacted. This enables the "Fresh Targets (no overlap)" export.

### Two-method matching

1. **Email domain match**: `Contact.domain == search_result_domain` (from email parsing)
2. **Website domain match**: Extract root from domain (e.g., `alfacapital.ru` → `alfacapital`), then `Contact.company_name ILIKE '%alfacapital%'` (only if root >= 4 chars)

### Export filtering

`POST /search/projects/{project_id}/export-sheet` with `exclude_contacted: true`:
```python
contacted_result = await db.execute(
    select(func.lower(Contact.domain)).where(
        Contact.company_id == company.id,
        Contact.domain.isnot(None),
        func.lower(Contact.domain).in_(result_domains),
    ).distinct()
)
contacted_domains = {row[0] for row in contacted_result.fetchall()}
results = [r for r in results if r.domain.lower() not in contacted_domains]
```

This filters out any domains where contacts already exist in the CRM (imported from SmartLead/GetSales campaigns).

---

## 14. API Endpoints Reference

### Search Pipeline (`backend/app/api/search.py`)

| Method | Endpoint | Description | Line |
|--------|----------|-------------|------|
| `POST` | `/search/generate-queries` | Generate queries via GPT | `:87` |
| `POST` | `/search/jobs` | Create + start search job | `:117` |
| `GET` | `/search/jobs` | List search jobs (paginated) | `:201` |
| `GET` | `/search/jobs/{id}` | Job detail with all queries | `:220` |
| `GET` | `/search/jobs/{id}/queries` | Paginated queries for job | `:263` |
| `POST` | `/search/jobs/{id}/cancel` | Cancel running job | `:309` |
| `GET` | `/search/jobs/{id}/stream` | SSE real-time progress | `:338` |
| `GET` | `/search/jobs/{id}/full` | Extended detail with spending | `:948` |
| `GET` | `/search/jobs/{id}/results` | Job results with source queries | `:1042` |
| `GET` | `/search/jobs/{id}/results/download` | CSV download | `:1098` |
| `GET` | `/search/jobs/{id}/review-summary` | Review statistics | `:708` |
| `POST` | `/search/projects/{id}/run` | Run full pipeline for project | `:448` |
| `GET` | `/search/projects/{id}/results` | Paginated project results (page, page_size, job_id) | `:575` |
| `GET` | `/search/projects/{id}/results/stats` | Fast aggregate counts | `:523` |
| `GET` | `/search/projects/{id}/spending` | Cost tracking | `:643` |
| `POST` | `/search/projects/{id}/export-sheet` | Export to Google Sheet | `:737` |
| `POST` | `/search/results/{id}/review` | Manual review (confirm/reject/flag) | `:666` |
| `POST` | `/search/domain-campaigns` | Batch domain-campaign lookup | `:1164` |
| `GET` | `/search/history` | Paginated job history with stats | `:856` |

### Outreach Pipeline (`backend/app/api/pipeline.py`)

| Method | Endpoint | Description | Line |
|--------|----------|-------------|------|
| `GET` | `/pipeline/discovered-companies` | List with filters | `:32` |
| `GET` | `/pipeline/discovered-companies/{id}` | Detail with contacts + events | `:63` |
| `POST` | `/pipeline/extract-contacts` | GPT contact extraction | `:83` |
| `POST` | `/pipeline/enrich-apollo` | Apollo people enrichment | `:100` |
| `POST` | `/pipeline/promote-to-crm` | Create CRM Contact records | `:118` |
| `POST` | `/pipeline/update-status` | Bulk status update | `:154` |
| `GET` | `/pipeline/stats` | Pipeline statistics | `:137` |
| `GET` | `/pipeline/export-csv` | CSV export | `:183` |

---

## 15. GPT Prompts Reference

| Purpose | File | Function | Model | Temp | Max Tokens |
|---------|------|----------|-------|------|------------|
| Query generation | `search_service.py` | `generate_queries()` | gpt-4o-mini | 0.95 | 4000 |
| Company analysis | `company_search_service.py` | `analyze_company()` | gpt-4o-mini | 0.1 | 600 |
| Auto-review | `review_service.py` | `_review_batch_gpt()` | gpt-4o-mini | 0.1 | 2000 |
| Contact extraction | `contact_extraction_service.py` | `extract_contacts_from_html()` | gpt-4o-mini | 0.1 | 1000 |
| Company verification | `verification_service.py` | `_ai_verification()` | gpt-4o-mini | 0.1 | 600 |
| Reverse engineering | `reverse_engineering_service.py` | `analyze_with_ai()` | gpt-4o-mini | 0.3 | 300 |
| Document to markdown | `document_processor.py` | `convert_to_markdown()` | gpt-4o-mini | 0.1 | 4000 |
| Company summary | `document_processor.py` | `generate_company_summary()` | gpt-4o-mini | 0.2 | 2000 |
| Auto-reply prompt | `conversation_analysis_service.py` | `generate_auto_reply_prompt()` | gpt-4o-mini | 0.7 | 1500 |
| TAM analysis | `ai_sdr_service.py` | `generate_tam_analysis()` | gpt-4o-mini | default | — |
| GTM plan | `ai_sdr_service.py` | `generate_gtm_plan()` | gpt-4o-mini | default | — |
| Pitch templates | `ai_sdr_service.py` | `generate_pitch_templates()` | gpt-4o-mini | default | — |

All GPT calls go through `https://api.openai.com/v1/chat/completions` via `httpx`.

---

## 16. External APIs & Credentials

| Service | Base URL | Auth | Env Vars |
|---------|----------|------|----------|
| OpenAI | `https://api.openai.com/v1` | Bearer token | `OPENAI_API_KEY` |
| Yandex Search | `https://searchapi.api.cloud.yandex.net` | Api-Key header | `YANDEX_SEARCH_API_KEY`, `YANDEX_SEARCH_FOLDER_ID` |
| Yandex Operations | `https://operation.api.cloud.yandex.net` | Api-Key header | (same key) |
| Crona | `https://api.crona.ai` | JWT Bearer | `CRONA_EMAIL`, `CRONA_PASSWORD` |
| Apollo.io | `https://api.apollo.io/api/v1` | API key in body | `APOLLO_API_KEY` |
| Apify Proxy | configurable host:port | Password auth | `APIFY_PROXY_PASSWORD`, `APIFY_PROXY_HOST`, `APIFY_PROXY_PORT` |
| Google Sheets | Google API | Service account | (configured in google_sheets_service) |

---

## 17. Configuration Reference

From `backend/app/core/config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `DEFAULT_OPENAI_MODEL` | `gpt-4o-mini` | Model for all GPT calls |
| `SEARCH_MAX_PAGES` | `3` | Pages per search query |
| `SEARCH_WORKERS` | `8` | Concurrent search workers |
| `SEARCH_REQUEST_TIMEOUT` | `30` | Request timeout (seconds) |
| `SEARCH_DOMAIN_RECHECK_DAYS` | `365` | Don't re-analyze domains within N days |
| `SEARCH_TARGET_GOAL` | `1000` | Target count to stop iterating |
| `SEARCH_BATCH_QUERIES` | `50` | Queries per iteration |
| `SEARCH_MAX_ITERATIONS` | `30` | Max iterations safety cap |
| `CRONA_API_URL` | `https://api.crona.ai` | Crona API base URL |
| `CRONA_CREDITS_PER_SCRAPE` | `1` | Credits per domain scrape |
| `APOLLO_API_URL` | `https://api.apollo.io/api/v1` | Apollo API base URL |

---

## 18. Cost Model

| Resource | Unit | Price | Example (500 queries) |
|----------|------|-------|-----------------------|
| Yandex API | per 1K requests | $0.25 | 500 queries * 3 pages = 1500 req = $0.375 |
| OpenAI (analysis) | per 1M tokens | $0.15 input / $0.60 output | ~500 domains * ~1K tokens = 500K = $0.075 |
| OpenAI (query gen) | per 1M tokens | $0.15 / $0.60 | ~10 batches * ~4K tokens = $0.006 |
| OpenAI (review) | per 1M tokens | $0.15 / $0.60 | ~25 batches * ~2K tokens = $0.008 |
| Crona | per credit | ~$0.001 | 500 domains = $0.50 |

Typical cost for a 500-query search: **~$1.00**

---

## 19. Database Models

### Core search models (`backend/app/models/domain.py`)

| Model | Table | Key Fields |
|-------|-------|------------|
| `Domain` | `domains` | domain (unique), status (ACTIVE/TRASH), source, times_seen, first_seen, last_seen |
| `SearchJob` | `search_jobs` | company_id, project_id, status, search_engine, queries_total/completed, domains_found/new/trash/duplicate, config (JSON) |
| `SearchQuery` | `search_queries` | search_job_id, query_text, status, domains_found, pages_scraped, targets_found, effectiveness_score |
| `SearchResult` | `search_results` | search_job_id, project_id, domain, is_target, confidence, reasoning, company_info (JSON), scores (JSON), review_status, source_query_id |
| `ProjectBlacklist` | `project_blacklist` | project_id, domain, reason, source |
| `ProjectSearchKnowledge` | `project_search_knowledge` | project_id, confirmed_domains, rejected_domains, good_query_patterns, bad_query_patterns, industry_keywords, anti_keywords |

### Pipeline models (`backend/app/models/pipeline.py`)

| Model | Table | Key Fields |
|-------|-------|------------|
| `DiscoveredCompany` | `discovered_companies` | company_id, project_id, domain, search_result_id, is_target, confidence, status (NEW→SCRAPED→ANALYZED→CONTACTS_EXTRACTED→ENRICHED→EXPORTED/REJECTED) |
| `ExtractedContact` | `extracted_contacts` | discovered_company_id, email, phone, first_name, last_name, job_title, linkedin_url, source (WEBSITE_SCRAPE/APOLLO/MANUAL), contact_id (CRM link) |
| `PipelineEvent` | `pipeline_events` | discovered_company_id, event_type, detail (JSON), error_message |
