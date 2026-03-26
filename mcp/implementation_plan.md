# MCP System — God Implementation Plan

## Context

Sales team currently uses Claude Code directly against the repo, which leads to accidental code creation and wasted time. Building a fully independent MCP server that operators interact with via natural language (Claude Desktop, Cursor). Two flows: gathering pipeline (contacts → campaign) and reply automation. The MCP autonomously refines analysis prompts until 90% accuracy — no manual prompt tuning.

**CRITICAL**: Completely isolated from existing system. Separate containers, separate DB, separate UI. Existing operators unaffected.

**Test flow**: User signs up → connects SmartLead + Apollo keys → gathers DACH SaaS companies for EasyStaff Global (max 100 Apollo credits) → self-refining analysis → GOD_SEQUENCE → SmartLead DRAFT campaign.

---

## Architecture

```
MCP Client (Claude Desktop)          Browser
    │                                    │
    │ SSE (MCP protocol)                 │ HTTP
    │                                    │
    ▼                                    ▼
┌─────────────────────────────────────────────┐
│  mcp-backend (FastAPI, :8002)               │
│  ├── /mcp/sse  — MCP protocol handler       │
│  ├── /api/*    — REST API for frontend      │
│  └── Services  — pipeline, refinement, GOD  │
└──────────────┬──────────────────────────────┘
               │
    ┌──────────┴──────────┐
    ▼                     ▼
mcp-postgres (:5433)   mcp-redis (:6380)
mcp_leadgen DB         cache + progress pub/sub

mcp-frontend (:3000) — minimal React UI
```

**Existing system untouched**: postgres:5432, redis:6379, backend:8000, frontend:80

---

## Isolation Strategy

| Resource | Existing | MCP (New) |
|----------|----------|-----------|
| PostgreSQL | leadgen-postgres :5432, db `leadgen` | mcp-postgres :5433, db `mcp_leadgen` |
| Redis | leadgen-redis :6379 | mcp-redis :6380 |
| Backend | leadgen-backend :8000 | mcp-backend :8002 |
| Frontend | leadgen-frontend :80 | mcp-frontend :3000 |
| Docker network | default | mcp-network |
| Volumes | postgres_data, redis_data | mcp_postgres_data, mcp_redis_data |

**Code strategy**: COPY services from `backend/app/services/` into `mcp/backend/app/services/`, adapt for per-user API keys. No imports from existing backend at runtime. The two systems share ZERO code at runtime — if existing backend changes, MCP is unaffected.

---

## Directory Structure

```
mcp/
├── requirements.md              # plan (current, rewritten)
├── requirements_source.md       # original brain dump (UNTOUCHED)
├── docker-compose.mcp.yml       # all 4 new containers
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   │       └── 001_initial_schema.py
│   └── app/
│       ├── main.py              # FastAPI entry: /mcp/sse + /api/*
│       ├── config.py            # MCP settings (DATABASE_URL, etc.)
│       ├── db/
│       │   └── database.py      # async engine → mcp-postgres:5433
│       ├── models/
│       │   ├── user.py          # MCPUser, MCPApiToken (NEW)
│       │   ├── integration.py   # MCPIntegrationSetting (NEW)
│       │   ├── project.py       # Project (mirrored, simplified)
│       │   ├── company.py       # Company (mirrored)
│       │   ├── gathering.py     # GatheringRun, ApprovalGate, etc. (mirrored)
│       │   ├── pipeline.py      # DiscoveredCompany (mirrored)
│       │   ├── campaign.py      # Campaign, GeneratedSequence (mirrored)
│       │   ├── refinement.py    # RefinementRun, RefinementIteration (NEW)
│       │   └── usage.py         # MCPUsageLog (NEW)
│       ├── auth/
│       │   ├── middleware.py     # API token extraction
│       │   └── dependencies.py  # get_current_user() FastAPI dep
│       ├── mcp/
│       │   ├── server.py        # MCP SSE transport handler
│       │   ├── tools.py         # 26 tool definitions with JSON schemas
│       │   ├── dispatcher.py    # tool_name → service method routing
│       │   └── progress.py      # SSE progress notification emitter
│       ├── services/
│       │   ├── user_context.py       # Per-user API key injection (NEW)
│       │   ├── refinement_engine.py  # Self-refinement loop (NEW — KEY)
│       │   ├── gathering_service.py  # Copied + adapted from existing
│       │   ├── gathering_adapters/   # All 9 adapters copied
│       │   ├── campaign_intelligence.py  # GOD_SEQUENCE copied + adapted
│       │   ├── apollo_service.py     # Copied
│       │   ├── smartlead_service.py  # Copied
│       │   ├── findymail_service.py  # Copied
│       │   ├── scraper_service.py    # Copied
│       │   ├── domain_service.py     # Copied (pure functions)
│       │   ├── openai_service.py     # Copied
│       │   └── gemini_client.py      # Copied
│       └── api/
│           ├── auth.py          # signup, token, me
│           ├── setup.py         # integration key management
│           ├── pipeline.py      # pipeline status, targets
│           └── health.py
│
└── frontend/
    ├── Dockerfile
    ├── nginx.conf               # proxy /api→:8002, /mcp→:8002
    ├── package.json
    ├── vite.config.ts
    └── src/
        ├── App.tsx
        ├── pages/
        │   ├── SetupPage.tsx    # API key entry
        │   ├── PipelinePage.tsx # live progress (SSE)
        │   ├── TargetsPage.tsx  # target review table
        │   └── CampaignPage.tsx # sequence viewer + SmartLead link
        ├── api/
        │   └── client.ts        # axios + X-MCP-Token header
        └── hooks/
            └── useSSE.ts        # SSE progress hook
```

---

## Auth: Simple API Token

No JWT, no OAuth. Token format: `mcp_<32-char-hex>`.

```
POST /api/auth/signup {email, name}
→ creates MCPUser + MCPApiToken
→ returns {user_id, api_token} (token shown ONCE)

All subsequent requests: X-MCP-Token header (REST) or Authorization: Bearer (MCP SSE)
```

Token stored as bcrypt hash. One user can have multiple tokens (revocation support). Token prefix (first 8 chars) displayed in UI for identification.

---

## Self-Refinement Engine (the KEY innovation)

**File**: `mcp/backend/app/services/refinement_engine.py`

Replaces manual operator prompt tuning. Runs autonomously at analysis phase.

```
FOR iteration IN 1..8:
  1. GPT-4o-mini analyzes all companies with current prompt
  2. Stratified sample: 20 targets + 10 borderline + 10 rejected
  3. GPT-4o independently verifies each sample (different prompt, skeptical)
  4. Calculate accuracy = (TP + TN) / total
  5. IF accuracy >= 90%: DONE → proceed to CP2
  6. Extract FP patterns ("marketing agencies serving SaaS clients")
  7. Extract FN patterns ("SaaS product described indirectly")
  8. Gemini 2.5 Pro generates improved prompt with exclusion/inclusion rules
  9. Re-analyze with improved prompt → repeat
```

**Cost per run** (100 companies, ~5 iterations): ~$6 total
- Analysis: 100 * $0.003 * 5 = $1.50
- Verification: 40 samples * $0.02 * 5 = $4.00
- Prompt improvement: $0.05 * 5 = $0.25

**Real benchmark** from existing system: V1: 0% → V2: 76% → V3: 93% → V8: 95.1%

**Key tables**:
- `refinement_runs` — tracks cycle (status, target_accuracy, iterations, final_accuracy)
- `refinement_iterations` — per-iteration (accuracy, FP patterns, prompt diff)
- `gathering_prompts` — versioned prompts (parent_prompt_id chain)

---

## MCP Tools (26 total)

### Account (3)
| Tool | Input | Action |
|------|-------|--------|
| `setup_account` | email, name | Create user, return API token |
| `configure_integration` | integration_name, api_key | Save + test API key |
| `check_integrations` | — | List connected integrations |

### Project (3)
| Tool | Input | Action |
|------|-------|--------|
| `create_project` | name, target_segments, sender_* | Create project with ICP |
| `list_projects` | — | List user's projects |
| `update_project` | project_id, fields | Update ICP/sender info |

### Pipeline (9)
| Tool | Input | Action |
|------|-------|--------|
| `tam_gather` | project_id, source_type, filters | Phase 1: gather+dedup |
| `tam_blacklist_check` | run_id | Phase 2: blacklist → CP1 gate |
| `tam_approve_checkpoint` | gate_id | Approve any checkpoint |
| `tam_pre_filter` | run_id | Phase 3: deterministic filter |
| `tam_scrape` | run_id | Phase 4: website scraping |
| `tam_analyze` | run_id, prompt, **auto_refine**, target_accuracy | Phase 5: analysis + self-refinement |
| `tam_prepare_verification` | run_id | Create CP3 cost estimate |
| `tam_run_verification` | run_id | Phase 6: FindyMail |
| `tam_list_sources` | — | Available adapters + filter schemas |

### Refinement (2)
| Tool | Input | Action |
|------|-------|--------|
| `refinement_status` | run_id | Current iteration, accuracy history |
| `refinement_override` | refinement_run_id | Accept current accuracy, stop loop |

### GOD_SEQUENCE (5)
| Tool | Input | Action |
|------|-------|--------|
| `god_score_campaigns` | project_id? | Campaign quality rankings |
| `god_extract_patterns` | market?, top_n? | Extract reusable patterns |
| `god_generate_sequence` | project_id, campaign_name?, instructions? | Generate 5-step sequence |
| `god_approve_sequence` | sequence_id | Mark approved |
| `god_push_to_smartlead` | sequence_id | Create DRAFT campaign |

### Orchestration (2)
| Tool | Input | Action |
|------|-------|--------|
| `run_full_pipeline` | project_id, source_type, filters, auto_refine | End-to-end autonomous run |
| `pipeline_status` | run_id | Phase progress + next action |

### Utility (2)
| Tool | Input | Action |
|------|-------|--------|
| `estimate_cost` | source_type, filters | Pre-run cost estimate |
| `blacklist_check` | domains | Quick domain check |

---

## Build Order

### Phase 1: Docker + DB (Day 1)
1. `mcp/docker-compose.mcp.yml` — 4 containers, isolated network
2. `mcp/backend/Dockerfile` — Python 3.11-slim, no Chromium
3. All model files (mirrored + new)
4. Alembic migration `001_initial_schema.py`
5. `main.py` with `/api/health` endpoint
6. **Verify**: `docker-compose -f mcp/docker-compose.mcp.yml up --build` boots clean

### Phase 2: Auth + Setup (Day 2)
1. Auth middleware (API token extraction + bcrypt verify)
2. `POST /api/auth/signup`, `GET /api/auth/me`
3. Integration service (encrypt keys, test SmartLead/Apollo connections)
4. `POST /api/setup/integrations`
5. **Verify**: curl signup → get token → save SmartLead key → test connection

### Phase 3: Core Services (Days 3-4)
1. Copy + adapt: domain_service, scraper_service, apollo_service
2. Copy + adapt: openai_service, gemini_client
3. Copy + adapt: gathering_adapters (start with apollo_org_api + manual)
4. Copy + adapt: gathering_service (full pipeline)
5. `UserServiceContext` — per-user API key injection
6. REST API: `/api/pipeline/*`
7. **Verify**: API call → Apollo gather → blacklist → CP1 → filter → scrape → analyze

### Phase 4: MCP Protocol (Days 5-6)
1. MCP SSE server at `/mcp/sse`
2. 26 tool definitions with JSON schemas
3. Dispatcher: tool_name → service method
4. SSE progress notifications for long phases
5. **Verify**: Claude Desktop connects, lists tools, runs `setup_account`

### Phase 5: Self-Refinement Engine (Days 7-8)
1. `refinement_engine.py` — full loop algorithm
2. GPT-4o verification function (skeptical, independent)
3. Gemini prompt improvement function
4. Stratified sampling
5. Wire into `tam_analyze` (auto_refine=true)
6. **Verify**: Run on test data, watch 3+ iterations, converge to 90%+

### Phase 6: GOD_SEQUENCE + SmartLead Push (Day 9)
1. Copy + adapt: campaign_intelligence_service
2. Copy + adapt: smartlead_service (create_campaign, set_sequences)
3. 5 GOD_SEQUENCE tools
4. `run_full_pipeline` orchestrator
5. **Verify**: Full pipeline → DRAFT campaign in SmartLead

### Phase 7: Frontend (Days 10-11)
1. Vite + React + Tailwind scaffold
2. SetupPage (API key entry + connection test)
3. PipelinePage (SSE live progress, phase stepper)
4. TargetsPage (sortable table, approve/reject)
5. CampaignPage (sequence viewer, SmartLead link)
6. **Verify**: Complete test flow via UI

### Phase 8: Deploy + E2E Test (Day 12)
1. Deploy to Hetzner alongside existing system
2. Run full test flow end-to-end
3. Fix edge cases

---

## Test Flow (Acceptance Criteria)

### 1. Claude Desktop connects
Config: `{"url": "http://46.62.210.24:8002/mcp/sse", "transport": "sse"}`

### 2. Account setup
```
User: "Set up my account"
→ setup_account {email: "test@example.com", name: "Test"}
→ {api_token: "mcp_a1b2c3...", user_id: 1}
```

### 3. Connect APIs
```
→ configure_integration {integration_name: "smartlead", api_key: "eaa086b6-..."}
→ {connected: true, message: "47 campaigns found"}

→ configure_integration {integration_name: "apollo", api_key: "..."}
→ {connected: true}
```

### 4. Create project
```
→ create_project {
    name: "EasyStaff Global - DACH Test",
    target_segments: "Series A-B SaaS in DACH, 50-500 emp, hiring remote talent",
    target_industries: "SaaS, Software, IT Services, Fintech",
    sender_name: "Marina Mikhaylova",
    sender_company: "easystaff.io"
  }
→ {project_id: 1}
```

### 5. Gather (max 100 Apollo credits = 4 pages * 25)
```
→ tam_gather {
    project_id: 1,
    source_type: "apollo.companies.api",
    filters: {
      organization_locations: ["Germany", "Austria", "Switzerland"],
      organization_num_employees_ranges: ["51,200", "201,500"],
      organization_latest_funding_stage_cd: ["series_a", "series_b"],
      q_organization_keyword_tags: ["SaaS"],
      max_pages: 4, per_page: 25
    }
  }
→ SSE: "Page 1/4: 25 found" ... "Page 4/4: 88 total"
→ {run_id: 1, new_companies: 83, duplicates: 5}
```

### 6. Blacklist → CP1 → approve
```
→ tam_blacklist_check {run_id: 1}
→ {passed: 81, rejected: 2, checkpoint: {gate_id: 1}}

→ tam_approve_checkpoint {gate_id: 1}
```

### 7. Pre-filter → Scrape
```
→ tam_pre_filter {run_id: 1} → {passed: 78}
→ tam_scrape {run_id: 1} → SSE progress → {scraped: 72, errors: 6}
```

### 8. Analyze with self-refinement
```
→ tam_analyze {
    run_id: 1,
    prompt_text: "Target: SaaS companies in DACH...",
    auto_refine: true,
    target_accuracy: 0.9
  }
→ SSE: "Iter 1: 72% accuracy (8 FP, 3 FN)"
→ SSE: "Iter 2: 85% accuracy (4 FP, 2 FN)"
→ SSE: "Iter 3: 92.5% — TARGET REACHED"
→ {targets_found: 25, accuracy: 0.925, refinement_iterations: 3, checkpoint: {gate_id: 2}}
```

### 9. CP2 approve → CP3 approve → verify
```
→ tam_approve_checkpoint {gate_id: 2}
→ tam_prepare_verification {run_id: 1} → {estimated_cost: $0.25, checkpoint: {gate_id: 3}}
→ tam_approve_checkpoint {gate_id: 3}
→ tam_run_verification {run_id: 1} → {verified: 25, emails_found: 52}
```

### 10. GOD_SEQUENCE → SmartLead DRAFT
```
→ god_generate_sequence {project_id: 1, campaign_name: "ES DACH SaaS Test"}
→ {sequence_id: 1, steps: [5 steps with Day 0/3/4/7/7 timing]}

→ god_approve_sequence {sequence_id: 1}
→ god_push_to_smartlead {sequence_id: 1}
→ {smartlead_url: "https://app.smartlead.ai/app/email-campaigns-v2/12345/analytics"}
```

---

## Key Files to Copy + Adapt

| Source (existing) | Destination (MCP) | Changes |
|---|---|---|
| `backend/app/services/gathering_service.py` | `mcp/backend/app/services/gathering_service.py` | Per-user keys via UserServiceContext, remove telegram/getsales refs |
| `backend/app/services/gathering_adapters/*.py` | `mcp/backend/app/services/gathering_adapters/*.py` | Minimal changes, update imports |
| `backend/app/models/gathering.py` | `mcp/backend/app/models/gathering.py` | Same schema, new Base |
| `backend/app/services/campaign_intelligence_service.py` | `mcp/backend/app/services/campaign_intelligence.py` | Remove scheduler refs, per-user keys |
| `backend/app/services/apollo_service.py` | `mcp/backend/app/services/apollo_service.py` | Per-user API key injection |
| `backend/app/services/smartlead_service.py` | `mcp/backend/app/services/smartlead_service.py` | Per-user API key injection |
| `backend/app/services/gathering_mcp.py` | Reference only | Pattern for tool registration |
| `backend/app/models/campaign_intelligence.py` | `mcp/backend/app/models/campaign.py` | Same schema, new Base |
| `docs/GOD_SEQUENCE/KNOWLEDGE_BASE_SNAPSHOT.md` | Seed script | Seed campaign_patterns table |

## New Files (not copied)

| File | Purpose |
|---|---|
| `mcp/backend/app/services/refinement_engine.py` | Autonomous self-refinement loop |
| `mcp/backend/app/services/user_context.py` | Per-user API key injection |
| `mcp/backend/app/mcp/server.py` | MCP SSE protocol handler |
| `mcp/backend/app/mcp/tools.py` | 26 tool definitions |
| `mcp/backend/app/mcp/dispatcher.py` | Tool → service routing |
| `mcp/backend/app/mcp/progress.py` | SSE notification emitter |
| `mcp/backend/app/auth/*` | API token auth |
| `mcp/backend/app/models/refinement.py` | RefinementRun, RefinementIteration |
| `mcp/backend/app/models/user.py` | MCPUser, MCPApiToken |
| `mcp/backend/app/models/usage.py` | MCPUsageLog |
