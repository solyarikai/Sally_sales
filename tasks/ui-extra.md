# System As-Is State — For New Agent Context

## What This System Does

A B2B lead generation platform: find target companies via web search, extract contacts, enrich with Apollo, manage in CRM, run outreach campaigns via SmartLead/GetSales. The user is building an agency tool where operators use a chat-driven UI to discover companies, then push them through an automated enrichment pipeline to campaign platforms.

---

## Architecture (4 layers)

```
Frontend (React+TS+Vite+Tailwind)  →  FastAPI Backend  →  PostgreSQL + Redis  →  External APIs
                                                                                  (OpenAI, Yandex, Apollo, Crona, SmartLead, GetSales, Google Sheets)
```

- **Multi-tenancy**: User → Environment → Company. Most endpoints require `X-Company-ID` header.
- **Singletons**: All services are module-level singletons (`service = ServiceClass()`).
- **DB sessions**: `get_session` (endpoint DI), `async_session_maker()` (background tasks/scripts).

---

## The Core Pipeline (This Is The Main Product)

```
User Chat  →  GPT Query Gen  →  Yandex Search  →  Domain Filter  →  Crona Scrape  →  GPT Scoring  →  Auto-Review
                                                                                                          ↓
CRM Contact  ←  Promote  ←  ExtractedContact  ←  Apollo + GPT+Regex  ←  DiscoveredCompany  ←  SearchResult
```

### How a search runs:
1. **Chat input** (`/data-search` page, project mode): user types "Find villa builders in Dubai"
2. `POST /api/search/chat` → `chat_search_service.parse_search_intent()` (GPT-4o-mini) → creates/updates `Project.target_segments`
3. Creates `SearchJob`, launches background task: `company_search_service.run_project_search()`
4. **Iterative loop** until target_goal reached:
   - Generate queries (GPT from target_segments + feedback)
   - Run queries on Yandex API (8 concurrent workers)
   - Filter domains (trash regex, dedup, blacklist)
   - Scrape via Crona API (JS-rendered) or httpx fallback
   - GPT-4o-mini multi-criteria scoring (language, industry, service, company_type, geography)
   - `_validate_analysis()` hard rules override GPT
   - Auto-review (GPT-4o second pass, batches of 20)
5. Auto-promote: `SearchResult` → `DiscoveredCompany` via `pipeline_service.promote_search_results()`
6. **SSE streaming**: `GET /api/search/jobs/{jobId}/stream` → polls DB every 2s, sends progress events

### After search completes (Pipeline page, `/pipeline`):
7. **Extract Contacts**: Select companies → "Extract Contacts" → GPT-4o-mini parses HTML + regex fallback → `ExtractedContact` records
8. **Apollo Enrichment**: Select companies → "Enrich Apollo" → settings popover (titles, max_people, max_credits) → `ExtractedContact` records with source=APOLLO
9. **Promote to CRM**: Select contacts → creates `Contact` records (deduped by email)
10. **Export**: Google Sheets or CSV

---

## Frontend Pages (Key Ones)

| Route | What It Does | Key File |
|---|---|---|
| `/` or `/data-search` | **Main search UI** — chat-driven. 3 modes: chat, reverse, project. Project mode is the primary one used. | `DataSearchPage.tsx` |
| `/pipeline` | **Enrichment dashboard** — table of DiscoveredCompanies with filters (project, status, target). Bulk actions: Extract Contacts, Enrich Apollo (with settings popover), Promote to CRM, Reject. Detail modal shows Info/Contacts/Events tabs. | `PipelinePage.tsx` |
| `/search-results` | **Job history** — lists past search jobs, per-job result tables, export to Google Sheets | `SearchResultsPage.tsx` |
| `/contacts` | **CRM** — ag-Grid table with all contacts, filters by project/campaign/source/status, bulk actions | `ContactsPage.tsx` |
| `/replies` | **Reply automation** — Smartlead campaign monitoring, AI classification, Slack/Sheets forwarding | `RepliesPage.tsx` |
| `/companies` | Workspace management | `HomePage.tsx` |
| `/company/:id/knowledge-base` | Company KB: profile, products, segments, competitors, case studies | `KnowledgeBasePage.tsx` |

---

## Backend Services (Key Ones)

| Service | File | Does What |
|---|---|---|
| `company_search_service` | `company_search_service.py` | **Main pipeline orchestrator** — iterative search loop |
| `chat_search_service` | `chat_search_service.py` | Parses natural language → structured search params |
| `search_service` | `search_service.py` | Query generation (GPT) + Yandex API execution |
| `pipeline_service` | `pipeline_service.py` | Promote → Extract → Enrich → CRM. Dedup built in |
| `apollo_service` | `apollo_service.py` | Apollo API (`/mixed_people/api_search`), in-memory credit counter |
| `contact_extraction_service` | `contact_extraction_service.py` | GPT + regex email/phone extraction from HTML |
| `crona_service` | `crona_service.py` | JS-rendered website scraping (api.crona.ai) |
| `review_service` | `review_service.py` | Auto-review (GPT second pass), knowledge accumulation |
| `google_sheets_service` | `google_sheets_service.py` | Create/populate sheets, append reply data |
| `crm_sync_service` | `crm_sync_service.py` | Bidirectional sync with SmartLead + GetSales |
| `smartlead_service` | `smartlead_service.py` | SmartLead API: campaigns, leads, replies, webhooks |

---

## Data Models (The Important Ones)

### Search Domain
- **`Project`** (`contact.py`): `target_segments` (JSON), `campaign_filters`, groups contacts
- **`SearchJob`** (`domain.py`): Company+project scoped, tracks query/domain counts, status
- **`SearchQuery`** (`domain.py`): Individual query within a job, effectiveness tracking
- **`SearchResult`** (`domain.py`): Per-domain analysis — `is_target`, `confidence`, `scores` (JSON), `review_status`
- **`ProjectSearchKnowledge`** (`domain.py`): Good/bad query patterns, anti-keywords (learned per project)

### Pipeline Domain
- **`DiscoveredCompany`** (`pipeline.py`): Persistent across jobs. Status: new→scraped→analyzed→contacts_extracted→enriched→exported/rejected. Has `scraped_html`, `emails_found`, `phones_found`
- **`ExtractedContact`** (`pipeline.py`): `source` = website_scrape | apollo | manual. Links to DiscoveredCompany. Can be promoted to Contact via `contact_id`
- **`PipelineEvent`** (`pipeline.py`): Audit trail per company

### CRM Domain
- **`Contact`** (`contact.py`): Unified contacts table. `source`, `status`, `smartlead_id`, `getsales_id`, `campaigns` (JSON array)
- **`ContactActivity`** (`contact.py`): Multi-channel interaction history (email, linkedin, etc.)

---

## What's Currently Working

1. **Chat-driven search** — user describes target, GPT generates queries, Yandex finds domains, Crona scrapes, GPT scores. SSE progress streaming works.
2. **Pipeline page** — table of discovered companies with filters. Extract Contacts (GPT+regex), Enrich Apollo (with settings popover showing titles/credits), Promote to CRM.
3. **Dedup** — extract_contacts_batch skips companies with `contacts_count > 0`. enrich_apollo_batch skips companies with `apollo_enriched_at` set. promote_to_crm skips by `contact_id` and email uniqueness.
4. **Google Sheets export** — search results export works (`POST /search/projects/{id}/export-sheet`). Reply logging to sheets works.
5. **SmartLead sync** — campaigns, leads, reply webhooks, AI classification.
6. **CRM** — contacts table with ag-Grid, activity timeline, project management.
7. **Reply automation** — Smartlead reply processing, Slack notifications, Google Sheets logging.

## What's NOT Working / Missing (From ui.md Feedback)

1. **Loading indicators** — project filter dropdown shows no loading state while fetching projects
2. **Column-embedded filters** — status/target/search filters should be IN table columns (like CRM page with ag-Grid), not separate dropdowns above
3. **Google Sheets export button missing on Pipeline page** — only CSV exists
4. **Cost/spending visibility** — no way to see total cost (Yandex API, OpenAI tokens, Crona credits, Apollo credits) per project on Pipeline page
5. **Auto-enrichment after search** — user wants: after search finds targets → auto-extract contacts → auto-enrich Apollo. Currently these are manual button clicks
6. **Chat should be project-scoped** — currently the search chat is generic, user wants it tightly coupled to a project
7. **Apollo title feedback** — operator should see AND adjust Apollo title filters from the chat/dashboard (done: popover exists on Pipeline page, but not in chat flow)
8. **SmartLead/GetSales campaign creation** — currently system only syncs FROM platforms. User wants to create campaigns and push leads TO them from the pipeline
9. **Unified dashboard** — search → enrich → outreach should feel like one flow, not 3 separate pages

---

## Key File Paths Quick Reference

### Frontend
- Routes: `frontend/src/App.tsx` (lines 37-130)
- API clients: `frontend/src/api/` (pipeline.ts, dataSearch.ts, contacts.ts, replies.ts)
- Pipeline page: `frontend/src/pages/PipelinePage.tsx`
- Search page: `frontend/src/pages/DataSearchPage.tsx`
- Company header interceptor: `frontend/src/api/client.ts` (`shouldSkipCompanyHeader()`)

### Backend
- Router registration: `backend/app/api/__init__.py`
- Search pipeline: `backend/app/api/search.py` + `search_chat.py`
- Pipeline API: `backend/app/api/pipeline.py`
- Schemas: `backend/app/schemas/pipeline.py`
- Main search service: `backend/app/services/company_search_service.py`
- Pipeline service: `backend/app/services/pipeline_service.py`
- Apollo: `backend/app/services/apollo_service.py`
- Contact extraction: `backend/app/services/contact_extraction_service.py`
- Models: `backend/app/models/` (domain.py, pipeline.py, contact.py, user.py)
- DB setup: `backend/app/db/__init__.py` → `database.py`

### Deployment
- Docker: `docker-compose.yml` (postgres, redis, backend, frontend)
- Hetzner: `ssh hetzner`, path `~/magnum-opus-project/repo`
- Scripts: `scripts/` — standalone async scripts run via `docker run -d --network repo_default`

---

## For the Next Agent: What To Know Before You Start

1. **Branch**: `datamodel` is the active branch. All recent work is here.
2. **TypeScript build**: Uses `tsc -b` with `noUnusedLocals: true` — unused vars will fail Docker build even if local `tsc --noEmit` passes.
3. **Services are singletons** — don't create new instances, import the module-level one.
4. **Models must be registered** in both `backend/app/models/__init__.py` AND `backend/alembic/env.py`.
5. **Frontend API client** auto-adds `X-Company-ID` header except for paths in `shouldSkipCompanyHeader()`.
6. **Alembic migrations**: If version mismatch, stamp with `UPDATE alembic_version SET version_num = 'xxx'`.
7. **Long-running scripts on Hetzner**: Use `docker run -d` with `--network repo_default`, NOT `docker exec -d`.
8. **Apollo credits**: Tracked in-memory only (resets on restart). The API endpoint changed to `/mixed_people/api_search` with `X-Api-Key` header (not in body).
