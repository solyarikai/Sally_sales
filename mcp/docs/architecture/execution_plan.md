# MCP System — Execution Plan (Same-Day Build)

## Step 0: Test Apollo MCP (30 min)

**Goal**: Install Apollo's official MCP, run real queries (50 credits max), document UX patterns.

**What to document in `mcp/APOLLO_MCP_BEHAVIOUR.md`**:
- Does it ask for confirmation before spending credits?
- What approval/confirmation UX exists?
- How are results structured?
- Rate limiting behavior
- Error handling patterns
- When does it proceed autonomously vs ask the user?
- Tool names, schemas, response shapes

**Test query**: "Find digital creator agencies and media production agencies in Dubai and UK, 10-50 employees"

**Why this matters**: Steal the best UX patterns. Avoid their mistakes. Know when to confirm vs just go.

---

## Architecture: Total Isolation

```
EXISTING (UNTOUCHED)                    NEW MCP SYSTEM
leadgen-postgres :5432                  mcp-postgres :5433
leadgen-redis :6379                     mcp-redis :6380
leadgen-backend :8000                   mcp-backend :8002
leadgen-frontend :80                    mcp-frontend :3000
network: default                        network: mcp-network
volumes: postgres_data                  volumes: mcp_postgres_data
```

Zero shared containers, zero shared volumes, zero shared networks. If the MCP system crashes, existing system doesn't notice.

---

## Step 1: Docker Foundation (1 hour)

### 1.1 Create `mcp/docker-compose.mcp.yml`

```yaml
version: '3.8'
services:
  mcp-postgres:
    image: pgvector/pgvector:pg16
    container_name: mcp-postgres
    environment:
      POSTGRES_DB: mcp_leadgen
      POSTGRES_USER: mcp
      POSTGRES_PASSWORD: mcp_secret
    ports:
      - "5433:5432"
    volumes:
      - mcp_postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U mcp -d mcp_leadgen"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  mcp-redis:
    image: redis:7-alpine
    container_name: mcp-redis
    ports:
      - "6380:6379"
    volumes:
      - mcp_redis_data:/data
    command: redis-server --appendonly yes --maxmemory 128mb --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  mcp-backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: mcp-backend
    ports:
      - "8002:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://mcp:mcp_secret@mcp-postgres:5432/mcp_leadgen
      - REDIS_URL=redis://mcp-redis:6379
      - MCP_MODE=true
    env_file:
      - ../.env
    volumes:
      - ./backend:/app
    depends_on:
      mcp-postgres:
        condition: service_healthy
      mcp-redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "python -c 'import urllib.request; urllib.request.urlopen(\"http://localhost:8000/api/health\")'"]
      interval: 30s
      timeout: 30s
      retries: 5
      start_period: 60s
    restart: unless-stopped

  mcp-frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: mcp-frontend
    ports:
      - "3000:80"
    depends_on:
      - mcp-backend
    restart: unless-stopped

networks:
  default:
    name: mcp-network

volumes:
  mcp_postgres_data:
  mcp_redis_data:
```

### 1.2 Create `mcp/backend/Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y libpq-dev gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
```

### 1.3 Create `mcp/backend/requirements.txt`

```
fastapi==0.109.0
uvicorn[standard]==0.27.0
sqlalchemy[asyncio]==2.0.25
asyncpg==0.29.0
alembic==1.13.1
httpx==0.26.0
openai==1.12.0
google-genai==0.4.0
bcrypt==4.1.2
pydantic-settings==2.1.0
redis==5.0.1
beautifulsoup4==4.12.3
python-multipart==0.0.6
mcp==1.0.0
cryptography==42.0.2
```

### 1.4 Database models + Alembic migration

Create all models (mirrored from existing + new MCP-specific tables):

**New tables:**
- `mcp_users` (id, email, name, is_active, created_at)
- `mcp_api_tokens` (id, user_id, token_prefix, token_hash, name, is_active, last_used_at, created_at)
- `mcp_integration_settings` (id, user_id, integration_name, api_key_encrypted, is_connected, created_at)
- `refinement_runs` (id, gathering_run_id, status, target_accuracy, max_iterations, current_iteration, final_accuracy)
- `refinement_iterations` (id, refinement_run_id, iteration_number, accuracy, false_positive_patterns, prompt_adjustments)
- `mcp_usage_logs` (id, user_id, action, tool_name, metadata, created_at)

**Mirrored tables (same schema, new DB):**
- companies, projects, contacts, campaigns
- gathering_runs, company_source_links, company_scrapes, gathering_prompts
- analysis_runs, analysis_results, approval_gates
- discovered_companies
- campaign_snapshots, campaign_patterns, generated_sequences

### 1.5 Basic FastAPI app with health endpoint

`mcp/backend/app/main.py` → `/api/health` returns 200

**Verify**: `cd mcp && docker-compose -f docker-compose.mcp.yml up --build` → all 4 containers healthy

---

## Step 2: Auth + Integration Setup (1 hour)

### 2.1 API Token Auth

Token format: `mcp_<32-char-hex>` (e.g., `mcp_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6`)

```
POST /api/auth/signup {email, name}
→ {user_id, api_token}  // token shown ONCE

GET /api/auth/me
→ {user_id, email, name, integrations: [...]}

All requests: X-MCP-Token header (REST) or Authorization: Bearer (MCP SSE)
```

Middleware: extract token → bcrypt hash → lookup in mcp_api_tokens → inject user into request.

### 2.2 Integration Management

```
POST /api/setup/integrations {integration_name: "smartlead", api_key: "eaa086b6-..."}
→ tests connection (SmartLead: GET /campaigns, Apollo: GET /health)
→ encrypts key (AES-256-GCM)
→ {connected: true, message: "47 campaigns found"}

GET /api/setup/integrations
→ [{name: "smartlead", connected: true}, {name: "apollo", connected: false}, ...]
```

### 2.3 Per-User API Key Injection

`UserServiceContext` class: takes user_id + session, returns service instances with user's API keys injected.

```python
ctx = UserServiceContext(user_id=1, session=session)
apollo = await ctx.get_apollo_service()  # has user's Apollo key
smartlead = await ctx.get_smartlead_service()  # has user's SmartLead key
```

**Verify**: curl signup → get token → save SmartLead key → verify connected

---

## Step 3: Core Pipeline Services (2 hours)

Copy + adapt from existing `backend/app/services/`:

| Service | Source | Key Changes |
|---------|--------|-------------|
| `domain_service.py` | Pure functions | No changes |
| `scraper_service.py` | httpx scraper | Remove Crona fallback |
| `apollo_service.py` | Apollo API client | Per-user key via `set_api_key()` |
| `smartlead_service.py` | SmartLead API | Per-user key, keep: create_campaign, set_sequences, get_campaigns |
| `findymail_service.py` | FindyMail API | Per-user key |
| `openai_service.py` | GPT analysis | Use user's OpenAI key |
| `gemini_client.py` | Gemini API | Read from env (shared, OK for MVP) |
| `gathering_adapters/*.py` | All 9 adapters | Update imports to local paths |
| `gathering_service.py` | Pipeline orchestrator | Per-user keys, remove telegram/getsales refs, add refinement hook |
| `campaign_intelligence.py` | GOD_SEQUENCE | Per-user keys, remove scheduler refs |

### Key simplifications for MCP:
- Remove all Telegram DM code
- Remove all GetSales webhook handling
- Remove all Slack integration
- Remove all scheduler/cron loops
- Remove follow-up generation
- Remove reply processing (phase 2)
- Keep ONLY: gathering pipeline + GOD_SEQUENCE + SmartLead push

**Verify**: Can call gathering_service.start_gathering() via REST API, get results from Apollo

---

## Step 4: MCP Protocol Server (1.5 hours)

### 4.1 SSE Transport

`mcp/backend/app/mcp/server.py` — implements MCP protocol over SSE:
- `GET /mcp/sse` — SSE endpoint (client connects here)
- Handles: `initialize`, `tools/list`, `tools/call`
- Sends: `notifications/progress` for long-running ops

Uses `mcp` Python SDK (pip package) which handles protocol details.

### 4.2 Tool Definitions (26 tools)

`mcp/backend/app/mcp/tools.py` — JSON schemas for each tool:

**Account (3)**: setup_account, configure_integration, check_integrations
**Project (3)**: create_project, list_projects, update_project
**Pipeline (9)**: tam_gather, tam_blacklist_check, tam_approve_checkpoint, tam_pre_filter, tam_scrape, tam_analyze (with auto_refine flag), tam_prepare_verification, tam_run_verification, tam_list_sources
**Refinement (2)**: refinement_status, refinement_override
**GOD_SEQUENCE (5)**: god_score_campaigns, god_extract_patterns, god_generate_sequence, god_approve_sequence, god_push_to_smartlead
**Orchestration (2)**: run_full_pipeline, pipeline_status
**Utility (2)**: estimate_cost, blacklist_check

### 4.3 Dispatcher

`mcp/backend/app/mcp/dispatcher.py` — routes tool calls to service methods. Pattern from existing `gathering_mcp.py`.

### 4.4 Progress Notifications

`mcp/backend/app/mcp/progress.py` — emits SSE progress for:
- Apollo page fetching ("Page 2/4: 47 companies")
- Website scraping ("Scraped 15/72 companies")
- Analysis iterations ("Iteration 2: 85% accuracy")
- FindyMail verification ("Verified 10/25 emails")

**Verify**: Claude Desktop connects to `/mcp/sse`, lists 26 tools, calls `setup_account`

---

## Step 5: Self-Refinement Engine (1.5 hours)

`mcp/backend/app/services/refinement_engine.py` — THE KEY DIFFERENTIATOR

### Algorithm
```
FOR iteration IN 1..8:
  1. GPT-4o-mini analyzes all companies with current prompt
  2. Stratified sample: 20 targets + 10 borderline + 10 rejected
  3. GPT-4o INDEPENDENTLY verifies each sample (skeptical verifier prompt)
  4. Calculate accuracy = (TP + TN) / total
  5. IF accuracy >= 90%: DONE → proceed to CP2
  6. Extract FP patterns ("marketing agencies serving SaaS clients")
  7. Extract FN patterns ("SaaS product described indirectly")
  8. Gemini 2.5 Pro generates improved prompt with new exclusion/inclusion rules
  9. Call gathering_service.re_analyze() with new prompt → repeat
```

### Verification function (GPT-4o, NOT mini)
```python
system = """You are a VERIFICATION EXPERT. Independently assess whether each company
matches the ICP. Be SKEPTICAL. Look for false positives the analysis missed.
For each company: independent_verdict (bool), confidence (0-1), error_pattern (if disagree)."""
```

### Prompt improvement (Gemini 2.5 Pro)
```python
prompt = f"""Current prompt achieved {accuracy}%. Target: 90%.
FP patterns: {fp_list}
FN patterns: {fn_list}
Generate improved prompt with explicit exclusion/inclusion rules."""
```

### Cost per run (~100 companies, ~5 iterations): ~$6 total

**Verify**: Run analysis with auto_refine=true, watch it iterate 3+ times, converge to 90%+

---

## Step 6: GOD_SEQUENCE + SmartLead Push (1 hour)

### 6.1 Campaign Intelligence

Copy from existing `campaign_intelligence_service.py`:
- `generate_sequence()` — 3-level knowledge assembly + Gemini generation
- `push_sequence_to_smartlead()` — create DRAFT campaign + set sequences

### 6.2 Seed Knowledge

Seed `campaign_patterns` table with the 11 patterns from `docs/GOD_SEQUENCE/KNOWLEDGE_BASE_SNAPSHOT.md`:
- Universal: timing (Day 0/3/4/7/7), subject format, tone, CTA, opener
- Business (easystaff.io): competitor displacement, specific savings
- Project: city personalization

### 6.3 SmartLead Integration

`smartlead_service.create_campaign(name)` → `POST /api/v1/campaigns/create`
`smartlead_service.set_campaign_sequences(id, steps)` → `POST /api/v1/campaigns/{id}/sequences`

Campaign is ALWAYS DRAFT. MCP never adds leads or activates.

**Verify**: Full pipeline → SmartLead DRAFT campaign with 5-step sequence

---

## Step 7: Minimal Frontend (1 hour)

React 19 + Vite + Tailwind. 4 pages at `http://46.62.210.24:3000/`:

### SetupPage (`/setup`)
- API token display (from URL param after signup)
- SmartLead / Apollo / FindyMail key inputs
- "Test Connection" button for each
- Green/red status indicators

### PipelinePage (`/pipeline/:runId`)
- Vertical stepper: all 12 phases (green/blue/gray)
- SSE-powered live progress bar
- Refinement section: accuracy chart (iteration vs %)
- Target count, scrape stats

### TargetsPage (`/pipeline/:runId/targets`)
- Sortable table: domain, company, confidence, segment, reasoning
- Approve/reject checkboxes

### CampaignPage (`/campaigns/:sequenceId`)
- 5-step sequence viewer (subject + body per step)
- "Push to SmartLead" button
- SmartLead URL after push

**Verify**: Complete test flow navigable in browser

---

## Step 8: Deploy + Test Flow (30 min)

Deploy to Hetzner:
```bash
ssh hetzner "cd ~/magnum-opus-project/repo && git pull origin main"
ssh hetzner "cd ~/magnum-opus-project/repo/mcp && docker-compose -f docker-compose.mcp.yml up --build -d"
```

### Full Test Flow

1. **Claude Desktop config**: `{"url": "http://46.62.210.24:8002/mcp/sse"}`

2. **Signup**: `setup_account {email: "test@test.com", name: "Test"}`

3. **Connect APIs**:
   - `configure_integration {name: "smartlead", api_key: "eaa086b6-..."}`
   - `configure_integration {name: "apollo", api_key: "..."}`

4. **Create project**:
   ```json
   create_project {
     name: "EasyStaff Global - DACH Test",
     target_segments: "Series A-B SaaS in DACH, 50-500 emp",
     target_industries: "SaaS, Software, Fintech",
     sender_name: "Marina Mikhaylova",
     sender_company: "easystaff.io"
   }
   ```

5. **Gather** (max 100 credits = 4 pages x 25):
   ```json
   tam_gather {
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
   ```

6. **Pipeline**: blacklist → CP1 approve → pre-filter → scrape

7. **Self-refining analysis**:
   ```json
   tam_analyze {
     run_id: 1,
     prompt_text: "Target: DACH SaaS, 50-500 emp...",
     auto_refine: true,
     target_accuracy: 0.9
   }
   ```
   → Iterations until 90%+ accuracy

8. **CP2 approve → CP3 approve → FindyMail verify**

9. **GOD_SEQUENCE**: `god_generate_sequence {project_id: 1}` → 5-step sequence

10. **Push**: `god_push_to_smartlead {sequence_id: 1}` → SmartLead DRAFT URL

---

## Files to Copy from Existing Backend

| Source | Destination | Size | Priority |
|--------|-------------|------|----------|
| `backend/app/services/gathering_service.py` | `mcp/backend/app/services/` | 1225 lines | P0 |
| `backend/app/models/gathering.py` | `mcp/backend/app/models/` | ~300 lines | P0 |
| `backend/app/services/gathering_adapters/*.py` | `mcp/backend/app/services/gathering_adapters/` | 9 files | P0 |
| `backend/app/services/apollo_service.py` | `mcp/backend/app/services/` | ~200 lines | P0 |
| `backend/app/services/smartlead_service.py` | `mcp/backend/app/services/` | ~400 lines | P0 |
| `backend/app/services/campaign_intelligence_service.py` | `mcp/backend/app/services/` | ~700 lines | P1 |
| `backend/app/models/campaign_intelligence.py` | `mcp/backend/app/models/` | ~150 lines | P1 |
| `backend/app/services/scraper_service.py` | `mcp/backend/app/services/` | ~300 lines | P1 |
| `backend/app/services/domain_service.py` | `mcp/backend/app/services/` | ~100 lines | P0 |
| `backend/app/services/findymail_service.py` | `mcp/backend/app/services/` | ~150 lines | P2 |
| `backend/app/services/gathering_mcp.py` | Reference only | — | — |
| `docs/GOD_SEQUENCE/KNOWLEDGE_BASE_SNAPSHOT.md` | Seed script | — | P1 |

## New Files to Create

| File | Purpose | Priority |
|------|---------|----------|
| `mcp/backend/app/services/refinement_engine.py` | Self-refinement loop | P0 |
| `mcp/backend/app/services/user_context.py` | Per-user API key injection | P0 |
| `mcp/backend/app/mcp/server.py` | MCP SSE protocol | P0 |
| `mcp/backend/app/mcp/tools.py` | 26 tool definitions | P0 |
| `mcp/backend/app/mcp/dispatcher.py` | Tool → service routing | P0 |
| `mcp/backend/app/mcp/progress.py` | SSE notifications | P1 |
| `mcp/backend/app/auth/middleware.py` | Token auth | P0 |
| `mcp/backend/app/auth/dependencies.py` | FastAPI deps | P0 |
| `mcp/backend/app/models/user.py` | MCPUser, MCPApiToken | P0 |
| `mcp/backend/app/models/refinement.py` | RefinementRun, Iteration | P1 |
| `mcp/backend/app/models/usage.py` | MCPUsageLog | P2 |
| `mcp/APOLLO_MCP_BEHAVIOUR.md` | Apollo UX patterns doc | P0 (Step 0) |

---

## Timeline (Same Day)

| Step | Duration | Cumulative |
|------|----------|------------|
| 0. Test Apollo MCP + document | 30 min | 0:30 |
| 1. Docker + DB + health | 1 hr | 1:30 |
| 2. Auth + integrations | 1 hr | 2:30 |
| 3. Core pipeline services | 2 hr | 4:30 |
| 4. MCP protocol server | 1.5 hr | 6:00 |
| 5. Self-refinement engine | 1.5 hr | 7:30 |
| 6. GOD_SEQUENCE + SmartLead | 1 hr | 8:30 |
| 7. Frontend (minimal) | 1 hr | 9:30 |
| 8. Deploy + E2E test | 30 min | 10:00 |

**Total: ~10 hours of implementation**

---

## Safety Rules (inherited from CLAUDE.md)

- NEVER send messages to leads via SmartLead or GetSales
- Campaign creation is ALWAYS DRAFT — never add leads, never activate
- FindyMail requires explicit CP3 approval (costs money)
- Apollo credits capped at user-specified max (test: 100 credits)
- All existing system data untouched — completely separate DB
