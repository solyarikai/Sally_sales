# TAM Gathering System — God Architecture

## What We're Building

A reusable system that remembers **everything** about TAM gathering:
- Which filters were applied in which source (Apollo, Clay, Sales Navigator, etc.)
- Which companies were found from which filters
- Website content scraped (multiple pages, versioned with TTL)
- AI analysis runs (multiple models, multiple prompts, all stored)
- Blacklist checks against CRM/campaigns
- Approval gates before credit-spending steps

**MCP-ready**: Each source is a pluggable adapter module. Today they're Puppeteer emulators; tomorrow users connect their own Apollo/Clay API keys. The DB layer is the same.

**Reusable across projects**: EasyStaff Global, OnSocial, Inxy, any future project — same tables, same pipeline.

**Runs on Hetzner only**: All scripts, scrapers, migrations, DB queries execute on the production server (46.62.210.24). Local machines are for code editing only. Claude Code SSHes to Hetzner for all execution.

---

## Pipeline Flow — Strict Linear, No Skipping

```
GATHER+DEDUP → BLACKLIST → ★ CP1 → PRE-FILTER → SCRAPE → ANALYZE → ★ CP2 → VERIFY → ★ CP3 → GOD_SEQ → PUSH
     auto          auto     STOP       auto        auto      auto     STOP    blocked   STOP    auto    blocked
                          confirms                                   gate in DB         gate in DB
                          project +
                          scope
```

CP1 is the real project confirmation. It shows the project's campaigns and contacts
so the operator confirms they're in the right project AND the blacklist scope is correct.
This cannot be bypassed — it's an approval_gate in the database.

**Phase state machine** (`gathering_run.current_phase`):
```
gathered → awaiting_scope_ok → scope_approved → filtered → scraped →
analyzed → awaiting_targets_ok → targets_approved → awaiting_verify_ok →
verify_approved → verified → pushed
```

At `awaiting_*` phases, the run is physically stuck. An `approval_gate` record exists in the DB.
The ONLY way forward is `POST /approval-gates/{gate_id}/approve`. No code path skips this.
This survives crashes, session reloads, server restarts — the state is in the database.

### Phase Details

| # | Phase | Cost | Auto? | What it does |
|---|-------|------|-------|-------------|
| 1 | **GATHER** | varies | auto | Execute adapter, get raw company list from source |
| 2 | **DEDUP** | $0 | auto | Normalize domains, match to existing DiscoveredCompanies, create source_links. "Already known" = exists in discovered_companies for THIS project from a previous gathering run. NOT yet blacklisted — that's next. |
| 3 | **BLACKLIST** | $0 | auto | Project-scoped CRM check + project_blacklist + enterprise_blacklist |
| — | **★ CHECKPOINT 1** | — | **STOP** | **Project confirmation + blacklist review.** Shows: project name/ID, total contacts, ALL active campaigns (name, platform, leads), per-campaign rejection breakdown, enterprise blacklist, cross-project warnings. Operator confirms: "Yes, this is my project, and the scope is correct." **Code-enforced — cannot be bypassed.** If wrong project → cancel run. If wrong campaign → fix campaign_filters. |
| 4 | **PRE-FILTER** | $0 | auto | Deterministic rejection: offline industries (restaurant, hotel, construction), junk domains (.gov, .edu), trash patterns. NO AI. Rejects 40-60%. |
| 5 | **RESOLVE** | $0-low | auto | For companies missing domain: LinkedIn URL → domain. Company name → Google lookup. Skip if domain already known. |
| 6 | **SCRAPE** | $0 (httpx) | auto | Fetch website content. TTL check — skip if fresh. Multiple pages. **Cheap — no approval needed.** |
| 7 | **ANALYZE** | ~$0.01-0.05 | auto | AI analysis (GPT-4o-mini). Scores: industry_match, size_match, service_model. **Cheap — no approval needed.** |
| — | **★ CHECKPOINT 2** | — | **STOP** | **Operator reviews target list.** Must see: every company marked as target, its confidence score, reasoning, segment. Operator can accept, reject individual companies, override verdicts. Only after operator confirms the target list does the pipeline proceed. This is where the operator ensures the AI didn't hallucinate. **No credits are spent until this is approved.** |
| 8 | **VERIFY** | $$$ | **BLOCKED** | FindyMail email verification. **This is the expensive step.** Only runs on operator-approved targets. |
| — | **★ CHECKPOINT 3** | — | **STOP** | **Operator approves FindyMail spend.** Must see: how many emails to verify, estimated cost, which companies. Operator can remove companies before verification. |
| 9 | **GOD_SEQUENCE** | ~$0.08 | auto | Generate 5-step sequence from 3-level knowledge: universal patterns + business knowledge (same sender_company) + project ICP. Operator reviews draft before push. `POST /generate-sequence/` → `POST /approve/` |
| 10 | **PUSH** | $0 | **BLOCKED** | `POST /generated/{id}/push/` creates SmartLead campaign (DRAFT) with GOD_SEQUENCE output. Operator adds leads + activates. |

### What "new" and "duplicate" mean at each phase

This is critical. The words change meaning depending on where you are:

| After phase | "New" means | "Duplicate" means | "Rejected" means |
|-------------|-------------|-------------------|------------------|
| **GATHER+DEDUP** | Domain not in discovered_companies for THIS project from any previous gathering run | Domain already known from a previous gathering run (gets a new source_link, not a new record) | Nothing yet — no filtering applied |
| **BLACKLIST** | Passed all blacklist checks | N/A | In THIS project's active campaigns, OR in project blacklist, OR in enterprise blacklist. **NOT in other projects — that's a warning, not rejection.** |
| **PRE-FILTER** | Passed pattern matching | N/A | Offline industry, junk domain, trash pattern |
| **ANALYZE** | AI says is_target=true | N/A | AI says not a target for this ICP |
| **CHECKPOINT 2** | Operator confirmed as target | N/A | Operator rejected / overridden |

### Session Crash Recovery

All checkpoint state is persisted in the database (gathering_run.current_phase + approval_gates table).

**What happens if Claude Code session crashes at checkpoint 1:**
1. Next session: Claude Code reads CLAUDE.md which says "check for in-progress runs first"
2. Queries: `GET /runs?project_id=X` → finds run with `current_phase=awaiting_scope_ok`
3. Queries: `GET /approval-gates?project_id=X` → finds pending gate with `gate_type=scope_verification`
4. Reads `gate.scope` which contains the FULL blacklist detail (rejected_domains, warning_domains, campaign breakdown)
5. Shows the same checkpoint 1 results to the operator
6. Operator approves → pipeline continues

**No data is lost.** The gate's `scope` JSON stores everything needed to reconstruct the checkpoint display.

### Scrape Failures Are Reported

When analysis runs, companies without scraped text are SKIPPED (not analyzed). The analysis response includes:
- `total_eligible`: how many companies could have been analyzed
- `skipped_no_scraped_text`: how many were skipped because scraping failed
- `total_analyzed`: how many were actually analyzed

Claude Code MUST report this at checkpoint 2: "Analyzed 300 of 500 eligible companies. 200 skipped (scrape failed — no website text)."

### Why this order is non-negotiable

1. **BLACKLIST before PRE-FILTER**: Blacklist is project-scoped business logic (campaigns, CRM). Pre-filter is generic pattern matching. Business logic first — if a company is already in your outreach, who cares if it matches an offline pattern.

2. **CHECKPOINT 1 after BLACKLIST**: The operator MUST verify the system correctly identified their project's campaigns. If campaign_filters are misconfigured, the blacklist is wrong. Better to catch this before wasting time on 10K companies.

3. **SCRAPE and ANALYZE are auto (no checkpoint)**: httpx scraping is free. GPT-4o-mini analysis costs ~$0.01-0.05 for 500 companies. Not worth interrupting the operator for $0.03.

4. **CHECKPOINT 2 after ANALYZE**: This is where the operator sees the actual target list. Before this point, everything is disposable. After this point, money gets spent.

5. **CHECKPOINT 3 before VERIFY**: FindyMail is real money ($0.01/email × 1000 emails = $10). Operator must approve the exact list and cost.

6. **No Apollo API in default flow**: Default enrichment is Apollo UI emulator (Puppeteer) — scrapes contact data from Apollo's UI for free. Apollo API costs credits. If credits are needed, that's a separate approval gate.

### What Claude Code must do at each checkpoint

**CHECKPOINT 1 (after blacklist)**:
```
Show the operator:
- "Checked 1,800 companies against [Project Name]'s campaigns"
- "YOUR PROJECT'S CAMPAIGNS that triggered rejections:"
  - Campaign: "EasyStaff - Dubai Agencies v3" → 45 domains, 120 contacts
  - Campaign: "EasyStaff - UAE IT Companies" → 12 domains, 38 contacts
- "Enterprise blacklist: 28 domains (competitors)"
- "Project blacklist: 3 domains (manually banned)"
- "PASSED: 1,712 companies ready for next phase"
- If cross_project=true: "WARNING: 89 domains also in Inxy project (not rejected)"

Ask: "Project scope looks correct? Proceed with pre-filter?"
DO NOT proceed until operator says yes.
```

**CHECKPOINT 2 (after analyze)**:
```
Show the operator:
- "Analyzed 542 companies with [prompt name]"
- "TARGETS: 180 companies (33% target rate, avg confidence 0.72)"
- Top 10 targets with domain, name, confidence, segment, reasoning
- "REJECTED: 362 companies (not matching ICP)"
- Bottom 5 rejections (borderline) with reasoning

Ask: "Review the target list. Remove any false positives, then confirm to proceed to FindyMail verification."
DO NOT proceed until operator confirms the target list.
```

**CHECKPOINT 3 (before FindyMail)**:
```
Show the operator:
- "Ready to verify emails for 180 target companies"
- "Estimated FindyMail cost: ~$X.XX (X emails × $0.01)"
- "Breakdown: 450 contacts found, 380 with emails to verify"

Ask: "Approve FindyMail spend of ~$X.XX?"
DO NOT call FindyMail until operator says yes.
```

---

## What The System Knows About Each Project

The gathering system doesn't operate in a vacuum. It reads the project's existing knowledge to make smart decisions.

### Project Context (already exists in DB — reuse, don't rebuild)

| Source | Table/Field | How Gathering Uses It |
|--------|------------|----------------------|
| **ICP Definition** | `projects.target_segments`, `projects.target_industries` | → AI maps to source-specific filters. "Agencies <50 emp in UAE" becomes Apollo location + seniority + size filters |
| **Segments** | `kb_segments` (flexible data JSON per segment) | → Each segment can have its OWN gathering configuration. Segment "Dubai Agencies" → apollo.companies.emulator with UAE filters. Segment "AU-PH Corridor" → clay.people.emulator with Filipino language filters |
| **Products** | `kb_products` (what we sell) | → AI analysis prompt: "Does this company need {product}?" |
| **Competitors** | `kb_competitors` (domains, strengths, weaknesses) | → Auto-blacklist competitor domains. Don't gather companies already using competitor |
| **Case Studies** | `kb_case_studies` (client industry, size, challenge, solution) | → Lookalike search: "Find companies similar to these customers" |
| **Company Profile** | `kb_company_profile` (who WE are) | → AI analysis context: "We are {company}, we offer {products}" |
| **Project Knowledge** | `project_knowledge` (category=icp/outreach/contacts/gtm) | → Rich ICP context, outreach rules, GTM strategy |
| **Existing Contacts** | `contacts` + `campaigns` (CRM) | → Blacklist: don't re-target companies already in outreach |
| **Enterprise Blacklist** | `project_blacklist` + `enterprise_blacklist.json` | → Hard exclusion before any processing |
| **Past Gathering Runs** | `gathering_runs` (this system) | → "Don't repeat filters that yielded <5% target rate" |

### Operator Input Modes

When an operator (or MCP agent) starts a gathering run, they can provide input in several ways:

**Mode 1: Natural Language** (easiest, MCP-optimized)
```
"Find 5000 digital agencies in UAE with <100 employees"
```
→ AI maps to filters using project's ICP + segment context
→ Suggests best source (Apollo for broad, Clay for specific)
→ Returns estimated results + cost

**Mode 2: Structured Filters** (experienced operators, precise)
```json
{
  "source_type": "apollo.people.emulator",
  "filters": {
    "person_locations": ["Dubai, United Arab Emirates"],
    "person_seniorities": ["founder", "c_suite"],
    "organization_num_employees_ranges": ["1,10", "11,50", "51,100"]
  }
}
```
→ Bypasses AI mapping, direct execution

**Mode 3: Lookalike** (from case studies or existing customers)
```
"Find companies similar to: frizzon.ae, 10xbrand.com, zopreneurs.com"
```
→ Reverse-engineer patterns (industry, size, location, tech stack)
→ Generate filters that match the pattern
→ Already partially exists: `reverse_engineering_service.py`

**Mode 4: Expand/Repeat** (iterate on previous runs)
```
"Run the same search as gathering_run #42 but for Singapore instead of Dubai"
```
→ Copy filters, modify location
→ Filter dedup (hash check) prevents accidental duplicates

### Gathering Run ↔ Segment Link

Each gathering run CAN be linked to a specific segment:

```
gathering_runs.segment_id  FK(kb_segments) NULL
```

This lets the system:
- Track which segments have been gathered (and which haven't)
- Calculate segment-level TAM: "Dubai Agencies segment: 5,150 companies found, 1,200 analyzed, 340 targets, 89 enriched"
- Suggest under-gathered segments: "AU-PH Corridor has 0 gathering runs — consider starting"

---

## Data Layer — New Tables

### 1. `gathering_runs` — Filter Memory (the core missing piece)

Every search execution = one record. Remembers EXACTLY which filters were applied.

```
gathering_runs
├── id                    SERIAL PK
├── project_id            FK(projects) NOT NULL
├── company_id            FK(companies) NOT NULL        -- tenant scope
│
│   ── SOURCE IDENTIFICATION ──
├── source_type           VARCHAR(100) NOT NULL           -- free string: "apollo.companies.emulator", "clay.people.api", etc.
│                                                         -- convention: {platform}.{target}.{method}
│                                                         -- NOT an enum — new sources added without DB changes
├── source_label          VARCHAR(255)                    -- human-readable: "Apollo People Search (Puppeteer)"
├── source_subtype        VARCHAR(100)                    -- optional strategy: "strategy_a" | "strategy_b" | "industry_tags"
│
│   ── FILTER MEMORY ──
├── filters               JSONB NOT NULL                 -- source-specific schema (see Filter Schemas)
├── filter_hash           VARCHAR(64) NOT NULL           -- SHA256 of sorted canonical JSON
│                                                        -- dedup: same filters = same hash
│
│   ── EXECUTION STATE ──
├── status                VARCHAR(30) DEFAULT 'pending'  -- pending|running|completed|failed|cancelled|paused
├── started_at            TIMESTAMPTZ
├── completed_at          TIMESTAMPTZ
├── duration_seconds      INTEGER                        -- wall clock time
│
│   ── RESULTS SUMMARY ──
├── raw_results_count     INTEGER DEFAULT 0              -- total from source before dedup
├── new_companies_count   INTEGER DEFAULT 0              -- net new DiscoveredCompany records
├── duplicate_count       INTEGER DEFAULT 0              -- already known (linked via company_source_links)
├── rejected_count        INTEGER DEFAULT 0              -- failed blacklist/offline filter
├── error_count           INTEGER DEFAULT 0
│
│   ── COST ──
├── credits_used          INTEGER DEFAULT 0
├── total_cost_usd        NUMERIC(10,4) DEFAULT 0
│
│   ── CONTEXT ──
├── segment_id            FK(kb_segments) NULL           -- which target segment this run serves
├── pipeline_run_id       FK(pipeline_runs) NULL         -- if part of automated pipeline
├── triggered_by          VARCHAR(100)                   -- operator | scheduler | mcp_agent | claude_code
├── input_mode            VARCHAR(30) DEFAULT 'structured' -- structured | natural_language | lookalike | expand
├── input_text            TEXT                           -- original operator input (NL mode)
├── notes                 TEXT
├── error_message         TEXT
│
│   ── RAW OUTPUT (debug/reprocess) ──
├── raw_output_ref        TEXT                           -- file path or S3 key for full output
├── raw_output_sample     JSONB                          -- first 50 results cached in DB
│
├── created_at            TIMESTAMPTZ DEFAULT now()
├── updated_at            TIMESTAMPTZ DEFAULT now()
│
├── INDEX ix_gr_project_source     (project_id, source_type, status)
├── INDEX ix_gr_filter_hash        (project_id, filter_hash)
├── INDEX ix_gr_pipeline           (pipeline_run_id)
└── INDEX ix_gr_created            (project_id, created_at DESC)
```

#### Source Architecture — Open/Closed Principle

**Critical design decision**: The DB is **source-agnostic**. It does NOT know about Apollo, Clay, or any specific platform. Adding a new source = new adapter class + register. Zero DB changes.

**Why not typed models per source in DB?**
- Apollo alone has: People UI, Companies UI, People API, Org API — 4 variants
- Clay has: Companies UI, Companies API, People UI, People API — 4 more
- Sales Navigator, Google Maps, LinkedIn, Crunchbase, Indeed... — keeps growing
- Each platform adds new filters regularly — model updates = migrations = downtime
- Explosion: platforms x targets x methods = too many models to maintain

**The god approach**: Three dimensions describe any source:

| Dimension | Column | Examples |
|-----------|--------|---------|
| **Platform** | `source_platform` | apollo, clay, sales_navigator, google_maps, crunchbase, csv |
| **Target** | `source_target` | companies, people |
| **Method** | `source_method` | api, emulator, manual |

`source_type` = `{platform}.{target}.{method}` — e.g. `apollo.companies.emulator`, `clay.people.api`

But `source_type` is just a **free VARCHAR** — the system never parses it. The adapter owns the semantics. Tomorrow you add `indeed.jobs.api` and nothing changes in the DB.

#### Filter Design — The DB Doesn't Care

```
filters JSONB NOT NULL
```

That's it. The DB stores whatever the adapter puts in. It never queries individual filter fields. It uses filters for:
1. **Store** — write once when gathering run starts
2. **Display** — read and show to operator in UI
3. **Hash** — SHA256 for dedup detection (same filters = same hash)
4. **Re-execute** — pass back to adapter unchanged

**No Pydantic validation at DB level.** Validation is the adapter's job.

#### Adapter-Level Validation (not DB)

Each adapter defines its OWN Pydantic model. This is adapter code, not schema code:

```python
class GatheringAdapter(ABC):
    source_type: str                  # "apollo.companies.emulator"
    filter_model: Type[BaseModel]     # adapter's own Pydantic class

    async def validate(self, raw_filters: dict) -> BaseModel:
        """Validate using adapter's model. All models use extra='allow'."""
        return self.filter_model(**raw_filters)
```

Every adapter's filter model has `class Config: extra = "allow"` — unknown fields are preserved. When Apollo adds a new filter, it passes through without code changes. When the adapter is updated to explicitly handle it, old records still load fine.

**Current adapters and their filters** (adapter code, NOT DB schema — this list grows without DB changes):

##### Apollo (4 adapters)

| Adapter | source_type | Key filters |
|---------|-------------|-------------|
| People UI | `apollo.people.emulator` | person_locations[], person_seniorities[], organization_num_employees_ranges[], q_organization_name, organization_industry_tag_ids[], person_titles[], exclude_keywords[], strategy, max_pages |
| Companies UI | `apollo.companies.emulator` | organization_locations[], organization_industry_tag_ids[], q_keywords, organization_num_employees_ranges[], sort_by_field, max_pages |
| Org API | `apollo.companies.api` | q_organization_keyword_tags[], organization_locations[], organization_num_employees_ranges[], max_pages, per_page |
| People API | `apollo.people.api` | domains[], person_titles[], limit_per_domain, reveal_personal_emails |

##### Clay (4 adapters)

| Adapter | source_type | Key filters |
|---------|-------------|-------------|
| Companies UI | `clay.companies.emulator` | industries[], industries_exclude[], sizes[], types[], country_names[], country_names_exclude[], annual_revenues[], description_keywords[], description_keywords_exclude[], minimum/maximum_member_count, icp_text |
| Companies API | `clay.companies.api` | Same fields as UI, direct API call instead of Puppeteer |
| People UI | `clay.people.emulator` | domains[], use_titles, job_title, name, countries[], cities[], schools[], languages[] |
| People API | `clay.people.api` | Same fields as UI, direct API call |

**Clay 5,000 limit**: Internal to adapter. When estimated_total > 5,000, adapter creates MULTIPLE `gathering_runs` (one per geo split). All share same `pipeline_run_id`. The `filters` JSON includes `_geo_split_label` for tracking. This is transparent to the rest of the system.

##### Other (extensible — add new ones without DB changes)

| Adapter | source_type | Key filters |
|---------|-------------|-------------|
| Sales Navigator | `sales_navigator.companies.emulator` | search_url, company_headcount[], geography[], industry[], annual_revenue[], seniority_level[], function[] |
| Google Maps | `google_maps.companies.api` | query, location, radius_km, type, min_rating |
| Crunchbase | `crunchbase.companies.api` | categories[], locations[], funding_rounds[], employee_count, founded_after |
| **Google Sheets** | `google_sheets.companies.manual` | sheet_url, gid, column_mapping (auto-detected from headers), skip_rows |
| CSV Import | `csv.companies.manual` | file_name, file_url, column_mapping, row_count |
| Manual | `manual.companies.manual` | domains[], source_description |
| Google SERP | `google.companies.api` | queries[], max_pages, geo, language (existing flow) |

**Google Sheets adapter**: Team members manually gather leads in Apollo/Clay/LinkedIn, paste into Google Sheets. Feed the sheet URL → pipeline processes (dedup, scrape, analyze). Auto-detects column mapping from header names (domain/website/url, company/name/organization, linkedin, employees, industry, country, city, email). Sheet must be shared "Anyone with link".

**Adding a new module tomorrow** (e.g. `indeed.jobs.api`):
1. Write `IndeedJobsAdapter` class with its Pydantic filter model
2. Register in `ADAPTER_REGISTRY["indeed.jobs.api"] = IndeedJobsAdapter`
3. Done. DB unchanged. UI auto-discovers via `/gathering/sources` endpoint.

### 2. `company_source_links` — Multi-Source Dedup Bridge

Solves: "Acme.com was found by Apollo keyword search, Apollo seniority search, AND Clay TAM export."

```
company_source_links
├── id                      SERIAL PK
├── discovered_company_id   FK(discovered_companies, CASCADE) NOT NULL
├── gathering_run_id        FK(gathering_runs, CASCADE) NOT NULL
├── source_rank             INTEGER                     -- position in source results (1st, 50th, etc.)
├── source_data             JSONB                       -- raw record from this source for this company
├── source_confidence       FLOAT                       -- relevance score from source
├── found_at                TIMESTAMPTZ DEFAULT now()
│
├── UNIQUE (discovered_company_id, gathering_run_id)
├── INDEX (gathering_run_id)
└── INDEX (discovered_company_id)
```

**How dedup works**:
1. GatheringRun #1 finds domain `acme.com` → creates DiscoveredCompany + company_source_link(run=1)
2. GatheringRun #2 finds `acme.com` again → finds existing DC by domain → only creates new link(run=2)
3. `SELECT COUNT(DISTINCT gathering_run_id) FROM company_source_links WHERE discovered_company_id = X` = "found by 2 sources"
4. `source_data` preserves what each source said about this company (different employee counts, industries, etc.)

### 3. `company_scrapes` — Versioned Website Content with TTL

Multiple pages per company. Versioned. TTL-based re-scraping.

```
company_scrapes
├── id                      SERIAL PK
├── discovered_company_id   FK(discovered_companies, CASCADE) NOT NULL
├── url                     TEXT NOT NULL                -- https://acme.com/about
├── page_path               VARCHAR(255) DEFAULT '/'    -- /, /about, /contact, /team, /careers
├── raw_html                TEXT                         -- raw HTML (100KB max)
├── clean_text              TEXT                         -- extracted readable text
├── metadata                JSONB                        -- {title, description, language, cyrillic_ratio, word_count, og_tags}
├── scraped_at              TIMESTAMPTZ DEFAULT now()
├── ttl_days                INTEGER DEFAULT 180          -- 6 months default
├── expires_at              TIMESTAMPTZ                  -- computed: scraped_at + interval(ttl_days)
├── is_current              BOOLEAN DEFAULT true         -- latest version for this (company, page_path)
├── version                 INTEGER DEFAULT 1            -- incremented on re-scrape
├── scrape_method           VARCHAR(50) DEFAULT 'httpx'  -- httpx | crona | puppeteer | apify
├── scrape_status           VARCHAR(30) DEFAULT 'success' -- success | error | timeout | blocked | redirect | empty | js_only
├── error_message           TEXT
├── http_status_code        INTEGER
├── html_size_bytes         INTEGER
├── text_size_bytes         INTEGER
├── created_at              TIMESTAMPTZ DEFAULT now()
│
├── INDEX (discovered_company_id, page_path, is_current)
├── INDEX (discovered_company_id) WHERE is_current = true
├── INDEX (expires_at) WHERE is_current = true           -- re-scrape scheduler
└── INDEX (scrape_status)
```

**TTL re-scrape**: Scheduled job queries `WHERE is_current = true AND expires_at < now()`. When re-scraped:
1. Old record: `is_current = false`
2. New record: `is_current = true, version = old.version + 1`
3. All historical scrapes preserved — can compare website changes over time

**Backward compat**: New code writes to `company_scrapes`. Also copies latest homepage (`page_path='/'`) to `discovered_companies.scraped_html/scraped_text/scraped_at` for existing code paths.

### 4a. `gathering_prompts` — Reusable AI Prompt Templates

Same prompt gets reused across many analysis runs. Deduped by SHA256 hash. Tracks per-prompt effectiveness.

```
gathering_prompts
├── id                    SERIAL PK
├── company_id            FK(companies) NOT NULL
├── project_id            FK(projects) NULL              -- NULL = global/shared prompt
├── name                  VARCHAR(255) NOT NULL           -- "EasyStaff UAE Agency ICP v2"
├── prompt_text           TEXT NOT NULL
├── prompt_hash           VARCHAR(64) NOT NULL UNIQUE     -- SHA256, same text = same prompt
├── category              VARCHAR(50) DEFAULT 'icp_analysis'  -- icp_analysis | segment_classification | pre_filter | enrichment
├── model_default         VARCHAR(100) DEFAULT 'gpt-4o-mini'
├── version               INTEGER DEFAULT 1
├── parent_prompt_id      FK(gathering_prompts) NULL      -- version chain for iterations
│
│   ── EFFECTIVENESS TRACKING (updated after each analysis run) ──
├── usage_count           INTEGER DEFAULT 0
├── avg_target_rate       FLOAT                           -- targets / total analyzed
├── avg_confidence        FLOAT
├── total_companies_analyzed  INTEGER DEFAULT 0
│
├── created_by            VARCHAR(100)
├── is_active             BOOLEAN DEFAULT true
├── created_at            TIMESTAMPTZ DEFAULT now()
├── updated_at            TIMESTAMPTZ DEFAULT now()
│
├── INDEX (company_id, project_id)
└── INDEX (company_id, category)
```

**Prompt lifecycle**:
1. Operator writes prompt → `get_or_create_prompt()` creates record (or finds existing by hash)
2. Analysis run links to prompt via `prompt_id` FK
3. After run completes → `update_prompt_stats()` recalculates effectiveness
4. Dashboard: "Which prompt has the best target rate?" → sort by avg_target_rate

**Version iteration**: When improving a prompt, set `parent_prompt_id` to the old version. Both remain usable; the system tracks which version performs better.

### 4b. `analysis_runs` + `analysis_results` — AI Analysis Versioning

Multiple analysis passes with different models/prompts. Compare results. Store everything.

```
analysis_runs
├── id                    SERIAL PK
├── project_id            FK(projects) NOT NULL
├── company_id            FK(companies) NOT NULL
├── prompt_id             FK(gathering_prompts) NULL      -- links to reusable prompt
├── model                 VARCHAR(100) NOT NULL           -- gemini-2.5-pro | gpt-4o-mini | gpt-4o | claude-sonnet-4
├── prompt_hash           VARCHAR(64) NOT NULL            -- SHA256 of prompt text
├── prompt_text           TEXT NULL                       -- inline fallback if no prompt_id
├── scope_type            VARCHAR(50) DEFAULT 'batch'   -- batch | single | re_analysis | comparison
├── scope_filter          JSONB                         -- {gathering_run_id: 5} or {status: "new"} or {company_ids: [1,2,3]}
├── status                VARCHAR(30) DEFAULT 'pending' -- pending | running | completed | failed | cancelled
├── started_at            TIMESTAMPTZ
├── completed_at          TIMESTAMPTZ
├── total_analyzed        INTEGER DEFAULT 0
├── targets_found         INTEGER DEFAULT 0
├── rejected_count        INTEGER DEFAULT 0
├── avg_confidence        FLOAT
├── total_cost_usd        NUMERIC(10,4) DEFAULT 0
├── total_tokens          INTEGER DEFAULT 0
├── triggered_by          VARCHAR(100)
├── error_message         TEXT
├── created_at            TIMESTAMPTZ DEFAULT now()
│
├── INDEX (project_id, status)
├── INDEX (project_id, model)
└── INDEX (project_id, prompt_hash)

analysis_results
├── id                      SERIAL PK
├── analysis_run_id         FK(analysis_runs, CASCADE) NOT NULL
├── discovered_company_id   FK(discovered_companies, CASCADE) NOT NULL
├── is_target               BOOLEAN DEFAULT false
├── confidence              FLOAT                       -- 0.0-1.0
├── segment                 VARCHAR(100)                -- matched segment name
├── reasoning               TEXT                        -- AI's explanation
├── scores                  JSONB                       -- {industry: 0.9, size: 0.7, service: 0.6, digital: 0.8}
├── raw_output              TEXT                        -- full AI response (for debugging)
├── override_verdict        BOOLEAN                     -- operator manual override
├── override_reason         TEXT
├── overridden_at           TIMESTAMPTZ
├── tokens_used             INTEGER
├── cost_usd                NUMERIC(10,6)
├── created_at              TIMESTAMPTZ DEFAULT now()
│
├── UNIQUE (analysis_run_id, discovered_company_id)
├── INDEX (discovered_company_id)
└── INDEX (analysis_run_id, is_target)
```

**Comparing two analysis runs**:
```sql
SELECT dc.domain, dc.name,
  a1.is_target AS run1, a1.confidence AS conf1, a1.reasoning AS why1,
  a2.is_target AS run2, a2.confidence AS conf2, a2.reasoning AS why2
FROM discovered_companies dc
JOIN analysis_results a1 ON a1.discovered_company_id = dc.id AND a1.analysis_run_id = :run1
JOIN analysis_results a2 ON a2.discovered_company_id = dc.id AND a2.analysis_run_id = :run2
WHERE a1.is_target != a2.is_target  -- disagreements only
ORDER BY ABS(a1.confidence - a2.confidence) DESC;
```

### 5. `approval_gates` — Operator Checkpoints

Pipeline pauses before credit-spending steps. Operator reviews scope + estimated cost, then approves/rejects.

```
approval_gates
├── id                    SERIAL PK
├── project_id            FK(projects) NOT NULL
├── pipeline_run_id       FK(pipeline_runs) NULL
├── gathering_run_id      FK(gathering_runs) NULL
├── gate_type             VARCHAR(50) NOT NULL          -- pre_scrape_crona | pre_analysis | pre_enrichment | pre_verification | pre_push
├── gate_label            VARCHAR(255) NOT NULL         -- "Approve 150 companies for Apollo enrichment (~$4.50)"
├── scope                 JSONB NOT NULL                -- {count: 150, company_ids: [...], estimated_cost_usd: 4.50, estimated_credits: 150}
├── status                VARCHAR(30) DEFAULT 'pending' -- pending | approved | rejected | expired
├── decided_by            VARCHAR(100)
├── decided_at            TIMESTAMPTZ
├── decision_note         TEXT
├── expires_at            TIMESTAMPTZ                   -- auto-expire if not decided
├── created_at            TIMESTAMPTZ DEFAULT now()
│
├── INDEX (project_id, status)
└── INDEX (status) WHERE status = 'pending'
```

**When gates are created**:
- `pre_scrape_crona`: Crona costs credits — gate before batch scraping via Crona
- `pre_analysis`: AI analysis costs tokens — gate before GPT/Gemini batch analysis
- `pre_enrichment`: Apollo enrich costs 1 credit/person — gate before enrich_apollo_batch
- `pre_verification`: FindyMail costs credits — gate before verify_emails_batch
- `pre_push`: Final review before SmartLead/GetSales push

**httpx scraping is free** — no gate needed. Only credit-spending steps get gates.

---

## Extensions to Existing Tables

### `discovered_companies` — New Columns

```python
# Multi-source tracking
source_count             = Column(Integer, default=1)          # how many gathering_runs found this
first_found_by           = Column(Integer, ForeignKey('gathering_runs.id'))

# CRM blacklist cache
blacklist_checked_at     = Column(DateTime(timezone=True))
in_active_campaign       = Column(Boolean, default=False)
campaign_ids_active      = Column(JSONB)                       # [campaign_id_1, ...]
crm_contact_id           = Column(Integer, ForeignKey('contacts.id'))  # if already in CRM

# Latest analysis reference
latest_analysis_run_id   = Column(Integer, ForeignKey('analysis_runs.id'))
latest_analysis_verdict  = Column(Boolean)                     # cached is_target from latest run
latest_analysis_segment  = Column(String(100))                 # cached segment
```

### `search_jobs` — New Column

```python
gathering_run_id = Column(Integer, ForeignKey('gathering_runs.id'))
```

---

## CRM Blacklist — Project-Scoped Fast Lookup

### Critical Design Decision: Project-Scoped Blacklisting

**Problem**: Company X is being contacted by EasyStaff RU (project 40, payroll offer). Inxy (project 10, crypto payments) starts gathering and finds Company X. Should it be blacklisted?

**Answer: NO.** Different projects sell different products to different ICPs. Company X can legitimately receive outreach from both projects — they're separate value propositions. Auto-blocking across projects would artificially reduce TAM.

**Rule**: Only campaigns belonging to the SAME project trigger auto-rejection. Other projects' campaigns are shown as warnings (never auto-rejected).

### Blacklist Check Layers (in order)

| # | Layer | Scope | Action | What it catches |
|---|-------|-------|--------|-----------------|
| 1 | **Project blacklist** | Per-project | Auto-reject | `project_blacklist` table — manual bans by operator |
| 2 | **Same-project campaigns** | Per-project | Auto-reject | Contacts with domains in THIS project's active campaigns |
| 3 | **Enterprise blacklist** | Global | Auto-reject | `enterprise_blacklist.json` — competitors, banned orgs |
| 4 | **Cross-project campaigns** | All projects | **Warning only** | Domains in OTHER projects' campaigns (informational) |

### What the Operator Sees

For each rejected domain, the response includes:

```json
{
  "rejected_domains": [
    {
      "domain": "acme.com",
      "company_name": "Acme Corp",
      "reason": "same_project_campaign",
      "detail": "3 contacts in 2 campaigns",
      "campaigns": ["EasyStaff - Dubai Agencies v3", "EasyStaff - UAE IT Companies"],
      "contact_count": 3
    }
  ],
  "warning_domains": [
    {
      "domain": "bigcorp.com",
      "company_name": "BigCorp",
      "other_project_name": "Inxy",
      "other_project_id": 10,
      "other_contact_count": 5,
      "other_campaigns": ["Inxy - Crypto Companies Q1"]
    }
  ]
}
```

**Why this matters**: If the system incorrectly assigns a campaign to the wrong project, the operator can see it in the detailed breakdown and fix the campaign → project mapping.

### Materialized View (Project-Scoped)

```sql
CREATE MATERIALIZED VIEW active_campaign_domains AS
SELECT DISTINCT
  lower(c.domain) AS domain,
  c.project_id,
  p.name AS project_name,
  array_agg(DISTINCT camp.id) AS campaign_ids,
  array_agg(DISTINCT camp.name) AS campaign_names,
  count(DISTINCT c.id) AS contact_count
FROM contacts c
JOIN projects p ON p.id = c.project_id
JOIN campaigns camp ON camp.project_id = c.project_id AND camp.status = 'active'
WHERE c.domain IS NOT NULL AND c.domain != ''
GROUP BY lower(c.domain), c.project_id, p.name;

CREATE UNIQUE INDEX ON active_campaign_domains(domain, project_id);
CREATE INDEX ON active_campaign_domains(project_id);
```

**Same-project check**: `WHERE domain = ANY(:domains) AND project_id = :pid`
**Cross-project check**: `WHERE domain = ANY(:domains) AND project_id != :pid`

**Refresh**: After campaign sync in `crm_scheduler.py` + after any campaign push. `REFRESH MATERIALIZED VIEW CONCURRENTLY` (no locks).

### Edge Cases

| Scenario | Behavior |
|----------|----------|
| Domain in project A campaigns, gathering for project B | **Warning** (not rejected) — different value prop |
| Domain in project A campaigns, gathering for project A | **Rejected** — already in outreach |
| Domain in enterprise blacklist | **Rejected** regardless of project |
| Domain in project blacklist for project A, gathering for project B | **Not rejected** — blacklist is per-project |
| Campaign wrongly assigned to project | Operator sees campaign names in detail → can fix mapping |
| Contact has NULL project_id | Ignored — unassigned contacts don't trigger blacklist |

### Also Check: DiscoveredCompanies Already Analyzed

```sql
-- Companies already in the system for THIS project (not globally)
SELECT DISTINCT domain FROM discovered_companies
WHERE domain = ANY(:domains) AND project_id = :pid AND status != 'REJECTED'
```

This prevents re-processing companies from previous gathering runs within the same project.

---

## MCP Adapter Pattern

### Base Class

```python
class GatheringAdapter(ABC):
    """Base class for all gathering source adapters.

    The system is source-agnostic. The DB stores opaque JSONB filters.
    Each adapter owns its filter schema and execution logic.
    Adding a new source = write adapter + register. Zero DB changes.
    """

    source_type: str                              # "apollo.companies.emulator"
    filter_model: Optional[Type[BaseModel]]       # Pydantic model (optional — can be None for fully dynamic)

    @abstractmethod
    async def validate(self, raw_filters: dict) -> dict:
        """Validate & normalize filters. Returns cleaned dict. Raises on invalid.
        If filter_model is set, validates via Pydantic. Otherwise, passes through."""

    @abstractmethod
    async def estimate(self, filters: dict) -> EstimateResult:
        """Estimate cost/results without executing."""

    @abstractmethod
    async def execute(self, filters: dict, on_progress: Callable = None) -> GatheringResult:
        """Execute gathering. Returns companies list + metadata."""

    def get_filter_schema(self) -> Optional[dict]:
        """JSON Schema for MCP tool registration. None if fully dynamic."""
        if self.filter_model:
            return self.filter_model.model_json_schema()
        return None

    def get_capabilities(self) -> dict:
        """What this adapter can do. Used by UI and MCP for discovery."""
        return {
            "source_type": self.source_type,
            "has_estimate": True,       # can estimate before executing
            "has_filter_schema": self.filter_model is not None,
            "cost_model": "free",       # free | per_result | per_page | per_credit
            "requires_auth": False,     # needs API key in integration_settings
        }
```

### Adapter Registry — Open for Extension

```python
# Global registry — adapters self-register on import
ADAPTER_REGISTRY: dict[str, Type[GatheringAdapter]] = {}

def register_adapter(cls: Type[GatheringAdapter]) -> Type[GatheringAdapter]:
    """Decorator. @register_adapter on adapter class auto-registers it."""
    ADAPTER_REGISTRY[cls.source_type] = cls
    return cls

def get_adapter(source_type: str) -> GatheringAdapter:
    cls = ADAPTER_REGISTRY.get(source_type)
    if not cls:
        raise ValueError(f"Unknown source: {source_type}. Available: {sorted(ADAPTER_REGISTRY.keys())}")
    return cls()

def list_adapters() -> list[dict]:
    """Returns all registered adapters + capabilities. Used by /gathering/sources endpoint."""
    return [get_adapter(st).get_capabilities() for st in sorted(ADAPTER_REGISTRY.keys())]
```

### Example: Adding a New Source (Zero DB Changes)

```python
# backend/app/services/gathering_adapters/indeed_jobs.py

@register_adapter
class IndeedJobsAdapter(GatheringAdapter):
    source_type = "indeed.jobs.api"
    filter_model = IndeedJobsFilters  # Pydantic model with Indeed-specific fields

    async def validate(self, raw_filters):
        return IndeedJobsFilters(**raw_filters).model_dump()

    async def estimate(self, filters):
        # Call Indeed API with dry_run flag
        return EstimateResult(estimated_companies=500, estimated_credits=0, cost_usd=0)

    async def execute(self, filters, on_progress=None):
        # Call Indeed API, normalize results to standard company dict
        ...
```

That's it. The system discovers it via registry. UI shows it in source dropdown. MCP exposes it as a tool.

### Adapter Internals (NOT in DB — transparent to pipeline)

- **Clay 5K limit**: Adapter auto-splits by geo, creates multiple `gathering_runs`
- **Apollo pagination**: Adapter iterates pages internally
- **Rate limiting**: Internal per adapter (Apollo 0.3s, Clay export timing)
- **Auth**: Puppeteer adapters handle login. API adapters read keys from `integration_settings`
- **Retry/backoff**: Internal — adapter handles 429s, timeouts, etc.

---

## Gathering Service — Orchestrator

### `gathering_service.py`

```python
class GatheringService:
    """Orchestrates the full TAM gathering pipeline."""

    # ── GATHER ──
    async def start_gathering(
        self, project_id: int, source_type: str, filters: dict,
        triggered_by: str = "operator", notes: str = None
    ) -> GatheringRun:
        """Create GatheringRun, validate filters, execute adapter, store results."""

    # ── DEDUP ──
    async def dedup_and_store(
        self, gathering_run_id: int, companies: list[dict]
    ) -> DedupeResult:
        """Normalize domains, check existing DiscoveredCompanies, create/link."""

    # ── BLACKLIST (deterministic, $0) ──
    async def run_blacklist_check(
        self, gathering_run_id: int
    ) -> BlacklistResult:
        """Check vs project_blacklist, enterprise_blacklist, CRM mat.view, existing DCs."""

    # ── SCRAPE ──
    async def scrape_companies(
        self, gathering_run_id: int, pages: list[str] = ['/'],
        method: str = 'httpx', force: bool = False
    ) -> ScrapeResult:
        """Scrape website content. Skip if current non-expired scrape exists (unless force=True)."""

    # ── ANALYZE ──
    async def start_analysis(
        self, project_id: int, model: str, prompt_text: str,
        scope_filter: dict, triggered_by: str = "operator"
    ) -> AnalysisRun:
        """Create analysis run, process companies, store results."""

    async def compare_analysis_runs(
        self, run_id_1: int, run_id_2: int
    ) -> ComparisonResult:
        """Compare two runs: agreements, disagreements, confidence deltas."""

    # ── APPROVAL ──
    async def create_gate(
        self, project_id: int, gate_type: str, scope: dict, label: str
    ) -> ApprovalGate:
        """Create approval gate. Pipeline pauses until approved."""

    async def approve_gate(self, gate_id: int, operator: str, note: str = None) -> None
    async def reject_gate(self, gate_id: int, operator: str, note: str = None) -> None

    # ── CONTINUE PIPELINE ──
    async def continue_pipeline(
        self, gathering_run_id: int, next_phase: str
    ) -> PhaseResult:
        """Resume pipeline from a specific phase."""

    # ── HISTORY ──
    async def get_runs(self, project_id: int, source_type: str = None) -> list[GatheringRun]
    async def get_run_detail(self, run_id: int) -> GatheringRunDetail
    async def get_run_companies(self, run_id: int, page: int = 1) -> PaginatedCompanies
```

---

## Migrating Existing EasyStaff Data

The existing JSON files from Dubai agency gathering MUST be imported into the new system.

### What exists:

| File | Records | Source |
|------|---------|--------|
| `data/dubai_agency_companies_full.json` | 295 | apollo_people_ui, Strategy A (32 keywords) |
| `data/uae_god_search_companies.json` | 5,602 | apollo_people_ui, Strategy B (seniority) |
| `data/uae_god_search_people.json` | 12,201 | apollo_people_ui, Strategy B (people records) |
| `data/uae_20k_companies.json` | 7,782 | apollo_companies_ui (industry tags + keywords) |

### Migration script: `scripts/migrate_existing_tam.py`

1. **Create GatheringRuns** for each historical search:
   - Run 1: `source_type=apollo.people.emulator, source_subtype=strategy_a, filters={person_locations: ["Dubai, UAE"], q_organization_name: "32 keywords", max_pages: 10}, status=completed`
   - Run 2: `source_type=apollo.people.emulator, source_subtype=strategy_b, filters={person_locations: [...3 UAE cities], person_seniorities: ["founder","c_suite","owner"], organization_num_employees_ranges: ["1,10"..."101,200"], max_pages: 10}, status=completed`
   - Run 3: `source_type=apollo.companies.emulator, source_subtype=industry_tags, filters={organization_locations: ["United Arab Emirates"], organization_industry_tag_ids: [...], organization_num_employees_ranges: [...], max_pages: 100}, status=completed`

2. **Create/update DiscoveredCompanies** for each unique domain:
   - Normalize domain via `domain_service.normalize_domain()`
   - Upsert by `(company_id, project_id, domain)`
   - Set: name, employees, linkedin_url, company_info from richest source

3. **Create company_source_links** for each (company, run) pair:
   - `source_data` = raw record from that source
   - `source_rank` = position in original results

4. **Import people as ExtractedContacts** (from `uae_god_search_people.json`):
   - Link to DiscoveredCompany by domain
   - `source = APOLLO` (extracted via Puppeteer, not API, but same data structure)

5. **Update GatheringRun counters**: raw_results_count, new_companies_count, duplicate_count

### Migration order:
1. Run migration for largest dataset first (uae_god_search = 5,602 companies)
2. Then keyword search (295) — mostly duplicates, creates source_links
3. Then companies tab (7,782) — many new, some overlapping

---

## API Endpoints

```
POST   /api/pipeline/gathering/start                        -- start gathering run
GET    /api/pipeline/gathering/runs                          -- list runs for project (with filters: source_type, status, date range)
GET    /api/pipeline/gathering/runs/{id}                     -- run detail + stats + filter recall
GET    /api/pipeline/gathering/runs/{id}/companies           -- companies from this run (paginated)
POST   /api/pipeline/gathering/continue/{id}                 -- continue to next phase
POST   /api/pipeline/gathering/estimate                      -- cost estimate without executing

GET    /api/pipeline/gathering/sources                       -- list available source adapters + filter JSON schemas
GET    /api/pipeline/gathering/sources/{type}/schema          -- JSON schema for specific source

GET    /api/pipeline/gathering/approval-gates                -- pending gates
POST   /api/pipeline/gathering/approval-gates/{id}/approve
POST   /api/pipeline/gathering/approval-gates/{id}/reject

GET    /api/pipeline/gathering/scrapes/{company_id}           -- all scrapes for a company (all versions, all pages)
POST   /api/pipeline/gathering/scrapes/refresh                -- trigger re-scrape for expired content

GET    /api/pipeline/gathering/analysis-runs                  -- list analysis runs
GET    /api/pipeline/gathering/analysis-runs/{id}             -- run detail with result summary
GET    /api/pipeline/gathering/analysis-runs/{a}/compare/{b}  -- compare two runs (disagreements, confidence deltas)

GET    /api/pipeline/gathering/blacklist-check                -- check domains against CRM + blacklist (dry run)
```

---

## Files to Create

| File | Purpose |
|------|---------|
| `backend/app/models/gathering.py` | GatheringRun, CompanySourceLink, CompanyScrape, AnalysisRun, AnalysisResult, ApprovalGate |
| `backend/app/schemas/gathering.py` | Pydantic filter schemas per source + request/response models |
| `backend/app/services/gathering_service.py` | Pipeline orchestrator |
| `backend/app/services/gathering_adapters/__init__.py` | Adapter registry |
| `backend/app/services/gathering_adapters/base.py` | GatheringAdapter ABC |
| `backend/app/services/gathering_adapters/apollo_people_ui.py` | Wraps apollo_god_search.js |
| `backend/app/services/gathering_adapters/apollo_companies_ui.py` | Wraps apollo_companies_god.js |
| `backend/app/services/gathering_adapters/apollo_org_api.py` | Wraps apollo_service.search_organizations |
| `backend/app/services/gathering_adapters/clay_companies.py` | Wraps clay_service.run_tam_export |
| `backend/app/services/gathering_adapters/clay_people.py` | Wraps clay_service.run_people_search |
| `backend/app/services/gathering_adapters/csv_import.py` | CSV file import |
| `backend/app/services/gathering_adapters/manual.py` | Direct domain list |
| `backend/app/api/gathering.py` | API router |
| `backend/alembic/versions/202603201_gathering_system.py` | Migration |
| `scripts/migrate_existing_tam.py` | Import existing EasyStaff JSON data |

## Files to Modify

| File | Change |
|------|--------|
| `backend/app/models/pipeline.py` | Add columns to DiscoveredCompany |
| `backend/app/models/domain.py` | Add gathering_run_id to SearchJob |
| `backend/app/models/__init__.py` | Import new models |
| `backend/app/services/scraper_service.py` | Add `scrape_to_db()` → writes to company_scrapes |
| `backend/app/api/pipeline.py` | Include gathering router |
| `backend/app/main.py` | Register materialized view refresh in startup/scheduler |

## Files to Reuse As-Is

| File | What it provides |
|------|-----------------|
| `backend/app/services/apollo_service.py` | search_organizations, enrich_by_domain — wrapped by adapters |
| `backend/app/services/clay_service.py` | run_tam_export, run_people_search — wrapped by adapters |
| `backend/app/services/pipeline_service.py` | enrich_apollo_batch, verify_emails_batch, promote_to_crm — post-analysis phases |
| `backend/app/services/domain_service.py` | normalize_domain(), matches_trash_pattern() |
| `backend/app/services/scraper_service.py` | scrape_website(), scrape_batch() — actual scraping logic |
| `easystaff-global/enterprise_blacklist.json` | Loaded by blacklist check |
| `scripts/apollo_god_search.js` | Called by ApolloPeopleUIAdapter |
| `scripts/apollo_companies_god.js` | Called by ApolloCompaniesUIAdapter |

---

## Implementation Order

**Phase A — Data layer (1 day)**
1. SQLAlchemy models in `gathering.py`
2. Pydantic schemas in `schemas/gathering.py`
3. Alembic migration (all new tables + column extensions)
4. Materialized view for CRM blacklist

**Phase B — Core service + Apollo adapter (2 days)**
5. GatheringAdapter ABC + adapter registry
6. ApolloOrgAPIAdapter (simplest — wraps existing service directly)
7. GatheringService: start_gathering + dedup + blacklist
8. API endpoints: start, list runs, run detail

**Phase C — Scraping + analysis (1-2 days)**
9. company_scrapes write path in scraper_service
10. TTL check + re-scrape scheduler
11. analysis_runs/results write path
12. AI analysis extracted from company_search_service into reusable function

**Phase D — Migration + remaining adapters (1-2 days)**
13. `migrate_existing_tam.py` — import EasyStaff JSON data
14. ApolloPeopleUIAdapter, ApolloCompaniesUIAdapter (wrap JS scripts)
15. ClayCompaniesAdapter, CSVImportAdapter

**Phase E — Approval gates + remaining API (1 day)**
16. Approval gate creation/resolution
17. Analysis comparison endpoint
18. Scrape refresh endpoint

**Phase F — MCP prep (1 day)**
19. JSON schema export for all adapters
20. MCP tool auto-registration

---

## Critical Edge Cases & Design Decisions

### 1. Company Identity Resolution (Multi-Domain)

**Problem**: Same company can have multiple domains: `acme.com`, `acme.ae`, `acme.co.uk`. Apollo says "Frizzon Studios", Clay says "Frizzon Productions". Dedup by domain alone misses these.

**Solution**: Two-layer dedup:
- **Layer 1 (instant, free)**: Exact domain match after normalization (strip www, lowercase)
- **Layer 2 (fuzzy, in PRE-FILTER phase)**: Company name similarity (Levenshtein or trigram) + LinkedIn URL match. If two DiscoveredCompanies share a LinkedIn company URL → merge.

**Implementation**: `discovered_companies.linkedin_company_url` as secondary unique identifier. On insert, check both domain AND linkedin URL. If linkedin matches existing with different domain → link as alias, don't create duplicate.

```
-- Optional: company aliases table for multi-domain entities
company_aliases
├── primary_company_id    FK(discovered_companies)
├── alias_domain          VARCHAR(255)
├── alias_linkedin_url    TEXT
├── alias_name            VARCHAR(500)
├── detected_by           VARCHAR(50)   -- domain_match | linkedin_match | name_fuzzy | manual
```

### 2. Domain Resolution Phase

**Problem**: 8,766 companies from Companies tab have LinkedIn URLs but NO domains. Can't scrape websites or check email enrichment without domains.

**Solution**: New pipeline phase RESOLVE between PRE-FILTER and SCRAPE:
1. **LinkedIn → domain**: Apollo `enrich_organization(linkedin_url)` returns `primary_domain` (1 credit per call, but high value)
2. **Company name → domain**: Google search `"{company_name}" site:{country_tld}` → extract domain from first result
3. **Skip if unnecessary**: Only run for companies missing domain after GATHER
4. **Budget-gated**: Operator approves batch size before spending Apollo credits

### 3. Re-Run Lineage

**Problem**: Operator wants to re-run search from 2 weeks ago because "Apollo might have new companies now." But `filter_hash` dedup would reject it as duplicate.

**Solution**: `parent_run_id` on gathering_runs:
```
gathering_runs.parent_run_id  FK(gathering_runs) NULL  -- "this is a re-run of run #42"
```

When `parent_run_id` is set, filter_hash dedup is bypassed. The system compares results: "Run #42 found 5,602 companies. Re-run #65 found 5,840. Net new: 238."

### 4. Conversion Provenance (Full Funnel Tracking)

**Problem**: "Which gathering run actually led to the deal we closed?" Can't answer without tracking the chain: gathering_run → DiscoveredCompany → ExtractedContact → Contact → Campaign → ProcessedReply → Meeting.

**Solution**: Already partially solved:
- `extracted_contacts.discovered_company_id` → links to DiscoveredCompany
- `contacts.provenance` JSON stores `gathering_details` (from `pipeline_service.promote_to_crm()`)
- `DiscoveredCompany → company_source_links → gathering_runs`

**Add**: `contacts.gathering_run_id` FK for direct lineage:
```python
# On Contact model:
gathering_run_id = Column(Integer, ForeignKey('gathering_runs.id'))
```

Full funnel query:
```sql
SELECT gr.source_type, gr.filters->>'person_locations' AS location,
  COUNT(DISTINCT dc.id) AS companies, COUNT(DISTINCT ec.id) AS contacts,
  COUNT(DISTINCT c.id) AS crm_contacts, COUNT(DISTINCT m.id) AS meetings
FROM gathering_runs gr
JOIN company_source_links csl ON csl.gathering_run_id = gr.id
JOIN discovered_companies dc ON dc.id = csl.discovered_company_id
LEFT JOIN extracted_contacts ec ON ec.discovered_company_id = dc.id
LEFT JOIN contacts c ON c.gathering_run_id = gr.id
LEFT JOIN meetings m ON m.contact_id = c.id
WHERE gr.project_id = :project_id
GROUP BY gr.id
ORDER BY meetings DESC;
```

### 5. Central Quota Management

**Problem**: Two operators run Apollo searches simultaneously → both hit 429 rate limit. Or MCP agent burns through all Clay credits in one run.

**Solution**: Adapter-level quota tracker (not DB — in-memory with Redis or simple file lock):
```python
class QuotaManager:
    """Central quota tracker per source platform."""

    async def acquire(self, platform: str, credits: int, timeout: int = 300) -> bool:
        """Request credits. Blocks until available or timeout."""

    async def release(self, platform: str, credits: int) -> None:
        """Return unused credits (e.g., search returned fewer results than expected)."""

    async def get_usage(self, platform: str) -> QuotaUsage:
        """Current usage: {used_today, limit_today, used_this_hour, limit_this_hour}."""
```

Each adapter calls `quota_manager.acquire()` before API calls. The manager respects per-platform limits (Apollo 200/min, Clay 5000 exports/day, etc.).

### 6. Parallel Gathering Strategy

**Problem**: For a new project, operator wants to search Apollo People + Apollo Companies + Clay TAM simultaneously, then merge results.

**Solution**: Multiple `gathering_runs` sharing the same `pipeline_run_id`. The pipeline waits for ALL runs with that `pipeline_run_id` to complete before proceeding to DEDUP.

```python
async def start_parallel_gathering(
    project_id: int,
    searches: list[dict],  # [{source_type, filters}, ...]
) -> PipelineRun:
    """Launch multiple gathering runs in parallel, merge on completion."""
    pipeline_run = PipelineRun(project_id=project_id, status="RUNNING")
    for search in searches:
        gathering_run = GatheringRun(
            pipeline_run_id=pipeline_run.id,
            source_type=search["source_type"],
            filters=search["filters"],
        )
        # Launch adapter.execute() as background task
    # Pipeline continues to DEDUP only when all runs are completed
```

### 7. Effectiveness Learning Loop

**Problem**: After 10 gathering runs, the operator wants to know: "Which source type + filter combination yielded the best target rate?"

**Solution**: Add computed metrics to `gathering_runs` (populated after ANALYZE phase):
```
gathering_runs (additional columns):
├── target_rate            FLOAT     -- targets_found / new_companies_count
├── avg_analysis_confidence FLOAT    -- mean confidence of targets from this run
├── cost_per_target_usd    NUMERIC   -- total_cost_usd / targets_found
├── enrichment_hit_rate    FLOAT     -- emails_found / targets_enriched (populated after ENRICH)
```

**Dashboard query**: "Best performing source types this month":
```sql
SELECT source_type, source_subtype,
  COUNT(*) AS runs,
  AVG(target_rate) AS avg_target_rate,
  AVG(cost_per_target_usd) AS avg_cost_per_target
FROM gathering_runs
WHERE project_id = :pid AND status = 'completed' AND target_rate IS NOT NULL
GROUP BY source_type, source_subtype
ORDER BY avg_target_rate DESC;
```

This feedback loop lets the system (or MCP agent) recommend: "Apollo seniority search has 22% target rate for this project. Clay companies search has 8%. Recommend using Apollo."

### 8. Export Flexibility (Pluggable Outputs)

**Problem**: Results need to go to different destinations: Google Sheets (review), CSV (download), SmartLead (campaign), GetSales (LinkedIn), Clay table (further enrichment), webhook (custom integration).

**Solution**: Output adapters (same pattern as gathering adapters):
```python
class OutputAdapter(ABC):
    output_type: str  # "google_sheets" | "csv" | "smartlead" | "getsales" | "clay_table" | "webhook"

    async def export(self, companies: list, contacts: list, config: dict) -> ExportResult
```

Already partially exists: `clay_service.export_to_google_sheets()`, `pipeline_service.promote_to_crm()`, SmartLead push. Just need to formalize as adapters.

---

## Real-World Example: EasyStaff Global (Project 9)

This pipeline was used to gather, analyze, and verify 7,900+ target companies across 20+ cities.
The pipeline produced 8 new SmartLead campaigns (regional splits: US, UK, Gulf, India, APAC, Australia, LatAm-Africa, plus variants).
EasyStaff Global has ~170 campaigns total — most were created before this pipeline existed, via manual processes.

### Step-by-Step: How It Actually Worked

```
STEP 1: GATHER from Apollo (Puppeteer emulator — free)
   │   Apply keyword + city + size filters to Apollo Companies UI
   │   ~80 keywords × 20 cities = 50+ gathering runs
   │   Each run's filters STORED in gathering_runs.filters (JSONB)
   │   → Tracks which keywords produce the best targets later
   │
   v
STEP 2: DEDUP + BLACKLIST
   │   Domain normalization → company_source_links (multi-source bridge)
   │   Check against 170 existing EasyStaff campaigns → reject overlaps
   │   ★ CHECKPOINT 1: operator confirms project scope
   │
   v
STEP 3: SCRAPE websites (httpx + Apify proxy — free)
   │   50 concurrent connections, streaming per-company commits
   │   Crash-safe: on_result callback saves each company individually
   │
   v
STEP 4: PRE-FILTER algorithmically (no AI — deterministic)
   │   Remove: website unreachable, offline industries (restaurant, hotel,
   │   construction), junk domains (.gov, .edu), empty/parked sites
   │   ~40-60% rejection rate — cheap, fast, no false negatives
   │
   v
STEP 5: ANALYZE by GPT-4o-mini
   │   AI classifies each company: is_target? confidence? segment? reasoning?
   │   Uses ICP prompt specific to this project
   │   Cost: ~$0.01-0.05 per batch of 500 companies
   │
   v
STEP 6: VERIFY by Opus (Claude)
   │   16 parallel Opus agents review ALL GPT targets
   │   Each agent gets ~260 companies, checks GPT's verdict
   │   Identifies false positives: SaaS products, solo consultants,
   │   wrong geography, government entities, game studios building own IP
   │
   v
STEP 7: ADJUST PROMPT → repeat Steps 5-6 until ≥90% accuracy
   │   This is the critical loop. 8 prompt iterations for EasyStaff:
   │
   │   V1: 0%  — complex scoring rubric, wrong segments entirely
   │   V2: 76% — via negativa approach, CAPS_LOCKED segments
   │   V3: 93% (small sample) — geography filter, solo consultant exclusion
   │   V4: 83% (full Opus review) — strict location, investment exclusion
   │   V5: 86% — entity type patterns, gov exclusion, country name detection
   │   V6: 88% — interior design, company formation, fake site detection
   │   V7: 93.6% (645/689 verified) — refined SERVICE vs PRODUCT distinction
   │   V8: 95.1% (2,645/2,782 verified) — final SERVICE business focus ✓
   │
   │   Loop exits when Opus verification shows ≥90% accuracy.
   │   Each iteration: Opus finds FP patterns → add exclusions to prompt → re-analyze → re-verify
   │
   v
STEP 8: PEOPLE SEARCH (Apollo People emulator — free, or API — 1 credit/company)
   │   Find up to 3 decision-makers per verified target company
   │   Filters: founder, c_suite, vp, director seniority
   │   Apollo People UI scrapes contact data from Apollo's UI
   │   Result: ~1.4 contacts per company average
   │
   v
STEP 9: FINDYMAIL email verification ($0.01/email)
   │   For contacts where Apollo doesn't provide verified emails
   │   ★ CHECKPOINT 3: operator approves spend
   │   438 contacts verified in one 88-min batch
   │
   v
STEP 10: GOD_SEQUENCE — generate campaign sequence (Gemini 2.5 Pro)
   │
   │   System assembles knowledge from 3 levels into one Gemini prompt:
   │
   │   LEVEL 1 — UNIVERSAL (campaign_patterns WHERE scope_level='universal')
   │     Cold email mechanics that apply to ALL projects:
   │     Subject: {{first_name}} – [pain point question]
   │     Timing: Day 0/3/4/7/7 (Steps 2+4 tied at 31% warm replies each)
   │     Tone: casual-professional, no hype words
   │     Body: 4-paragraph arc (Hook → Value → Proof → CTA)
   │     CTA: offer value ("calculate cost benefit?"), don't ask for time
   │     Flow: Value → Competition → Price → Channel → Empathy
   │
   │   LEVEL 2 — BUSINESS (campaign_patterns WHERE business_key=sender_company)
   │     Product knowledge shared across projects of SAME business:
   │     Grouped by Project.sender_company (e.g. "easystaff.io" = projects 9+40)
   │     Competitors, pricing, displacement stories, proof points
   │     + ProjectKnowledge (outreach/gtm) from sibling projects
   │
   │   LEVEL 3 — PROJECT (campaign_patterns WHERE project_id=THIS + ProjectKnowledge)
   │     This project's ICP, market, language, sender identity
   │     Target segments, industries, geographic personalization
   │
   │   All 3 levels → ~3,000 token prompt → Gemini 2.5 Pro → 5-step sequence
   │
   │   API calls:
   │     POST /api/campaign-intelligence/generate-sequence/
   │       {"project_id": 9, "campaign_name": "Petr ES Manchester"}
   │     → returns GeneratedSequence (status=draft) with 5 steps + rationale
   │
   │     POST /api/campaign-intelligence/generated/{id}/approve/
   │     → marks as approved, ready to push
   │
   │   Cost: ~$0.08 per generation
   │   Full docs: docs/GOD_SEQUENCE/ARCHITECTURE.md
   │   Knowledge contents: docs/GOD_SEQUENCE/KNOWLEDGE_BASE_SNAPSHOT.md
   │
   v
STEP 11: SMARTLEAD campaign creation + lead upload
   │
   │   API call:
   │     POST /api/campaign-intelligence/generated/{id}/push/
   │     → Creates SmartLead campaign (DRAFT state)
   │     → Sets the GOD_SEQUENCE-generated 5-step sequence
   │     → Registers campaign in DB with resolution_method="god_sequence"
   │
   │   Then manually (operator or separate script):
   │     Upload leads with custom fields: city, segment, sender_name
   │     Add sender email accounts (12 per campaign typical)
   │     Personalization variables: {{first_name}}, {{city}}, {{Sender Name}}
   │     Activate campaign → outreach begins
   │
   │   8 regional campaigns created via this pipeline:
   │   "Petr ES US", "Petr ES UK", "Petr ES Gulf",
   │   "Petr ES India", "Petr ES APAC", "Petr ES Australia",
   │   "Petr ES LatAm-Africa", + variants
```

### The Prompt Iteration Loop (Steps 5-7) Is The Core

This is what separates good gathering from bad. The pipeline is not "run GPT once and push."
It's a closed loop:

```
  ┌──────────────────────────────────────────┐
  │                                          │
  v                                          │
GPT-4o-mini analyzes ──► Opus verifies ──► <90%? ──YES──► Adjust prompt
  │                         │                              (add exclusions
  │                         │                               from FP patterns)
  │                         v
  │                      ≥90%? ──YES──► DONE, proceed to people search
  │
  └── Uses project-specific ICP prompt
      stored in gathering_prompts table
      with effectiveness tracking (target_rate, usage_count)
```

**What Opus catches that GPT misses:**
- Game studios building own IP (not doing client work)
- Management/strategy consulting (uses employees, not freelancers)
- SaaS products (not service businesses)
- Solo consultants / fractional CxOs (1-person operations)
- Wrong geography (Indian "Pvt Ltd" entities, Oman, Lebanon)
- Government subsidiaries
- Investment/VC firms

### Keyword Effectiveness Tracking

Each gathering run stores its filters. After analysis, `target_rate` is computed per run.
This lets us rank keywords by ROI:

| Tier | Target Rate | Keywords |
|------|------------|----------|
| **Tier 1** (35-45%) | Best | staffing agency, design agency, marketing agency |
| **Tier 2** (26-35%) | Good | outsourcing company, digital agency, creative agency |
| **Tier 3** (14-23%) | Low | software development, consulting firm, IT services |
| **DO NOT USE** (<5%) | Waste | fintech, saas, blockchain, crypto |

This data lives in `gathering_runs.target_rate` and informs future runs:
```sql
SELECT source_subtype, AVG(target_rate) FROM gathering_runs
WHERE project_id = 9 AND status = 'completed'
GROUP BY source_subtype ORDER BY avg DESC;
```

### Key Learnings

1. **Puppeteer > API for gathering** — Apollo emulator is free, API costs credits. Used API only for the 10K credits blitz to cover more keywords faster.

2. **The prompt iteration loop is essential** — V1 had 0% accuracy, V8 reached 95.1%. Eight iterations, each driven by Opus false-positive analysis. There is no shortcut.

3. **Keyword effectiveness varies 10x** — "staffing agency" hits 45% target rate, "fintech" hits <5%. Track `target_rate` per run to avoid wasting time on bad keywords.

4. **Streaming scrape is essential** — Old batch scrape lost all progress on crash. New streaming approach commits per-company via `on_result` callback. 50 concurrent connections, ~344 companies/min.

5. **People search fills the gap** — Apollo Companies gives domains, but not contacts. A separate People search step finds 1-3 decision-makers per company. FindyMail only needed for emails Apollo can't verify.

---

## Summary: What Makes This God-Level

| Principle | How |
|-----------|-----|
| **Source-agnostic** | DB stores opaque JSONB. New source = new adapter, zero DB changes |
| **Filter memory** | Every search remembered with exact parameters. Re-runnable. |
| **Multi-source dedup** | Same company found by 5 sources → 1 DiscoveredCompany + 5 source_links |
| **Cheapest first** | Free pattern matching → free blacklist → cheap scraping → expensive AI → costly enrichment |
| **Full provenance** | gathering_run → DiscoveredCompany → ExtractedContact → CRM Contact → Meeting → Deal |
| **Versioned scraping** | Multiple pages per company, TTL-based re-scrape, all versions preserved |
| **Multi-run analysis** | Different models, different prompts, compare results, operator override |
| **Approval gates** | Human-in-the-loop before every credit-spending step |
| **MCP-ready** | Adapters expose JSON schemas. `tam_gather_{source}` tools auto-registered |
| **Learning loop** | target_rate, cost_per_target tracked per run. System recommends best sources |
| **Project-aware** | Reads ICP, products, competitors, case studies, existing contacts. Not a dumb filter machine |
