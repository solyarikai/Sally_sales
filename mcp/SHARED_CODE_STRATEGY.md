# Shared Code Strategy — One Codebase, Two Apps

## ABSOLUTE RULE: DATA ISOLATION

**The two apps NEVER share data. NEVER proxy to each other's API. NEVER read from each other's database.**

- Main app DB: `leadgen-postgres:5432/leadgen` — MAIN APP ONLY
- MCP app DB: `mcp-postgres:5433/mcp_leadgen` — MCP APP ONLY
- MCP nginx: ALL routes go to `mcp-backend:8000` ONLY. ZERO routes to `leadgen-backend`.
- MCP docker-compose: NO connection to main app's Docker network.

**If a user gathers contacts through MCP pipeline, those contacts live ONLY in MCP DB.**
**If a user has contacts in the main app, those are INVISIBLE to MCP.**
**The two systems are completely independent. Breaking this rule is FORBIDDEN.**

## Goal

**Reuse LOGIC (code), never DATA.** Same Python services, same React components — different databases.
Fix a bug in shared code → fixed in both apps. But the data flows are completely separate.

---

## Architecture

```
magnum-opus/
├── shared/                          ← NEW: shared packages
│   ├── models/                      ← SQLAlchemy models (used by BOTH backends)
│   │   ├── __init__.py
│   │   ├── base.py                  ← DeclarativeBase (injected per app)
│   │   ├── gathering.py             ← GatheringRun, ApprovalGate, etc.
│   │   ├── campaign.py              ← Campaign, GeneratedSequence, etc.
│   │   ├── pipeline.py              ← DiscoveredCompany, ExtractedContact
│   │   ├── domain.py                ← Domain, DomainStatus
│   │   └── project.py               ← Project, Company (base fields)
│   │
│   ├── services/                    ← Business logic (used by BOTH backends)
│   │   ├── apollo_service.py        ← Apollo API (per-user key injection)
│   │   ├── smartlead_service.py     ← SmartLead API
│   │   ├── findymail_service.py     ← FindyMail API
│   │   ├── scraper_service.py       ← Website scraper
│   │   ├── domain_service.py        ← Domain filtering + dedup
│   │   ├── gathering_service.py     ← Pipeline orchestrator
│   │   ├── refinement_engine.py     ← Self-refinement loop
│   │   ├── campaign_intelligence.py ← GOD_SEQUENCE
│   │   └── gathering_adapters/      ← All source adapters
│   │
│   └── ui/                          ← Shared React components (used by BOTH frontends)
│       ├── package.json
│       ├── components/
│       │   ├── PipelineStepper.tsx   ← Phase progress visualization
│       │   ├── TargetTable.tsx       ← Sortable target company table
│       │   ├── SequenceViewer.tsx    ← 5-step email sequence display
│       │   ├── IntegrationCard.tsx   ← API key connection widget
│       │   ├── ReplyCard.tsx         ← Reply with draft + actions
│       │   ├── FilterBar.tsx         ← Search/filter controls
│       │   └── StatusBadge.tsx       ← Phase/status indicators
│       ├── hooks/
│       │   ├── useSSE.ts            ← SSE connection hook
│       │   └── useApi.ts            ← Authenticated API calls
│       └── theme/
│           └── tokens.ts            ← Color tokens, spacing, typography
│
├── backend/                         ← MAIN app backend (existing)
│   └── app/
│       ├── models/                  ← Imports from shared/models + adds app-specific models
│       │   ├── reply.py             ← ProcessedReply (main app only)
│       │   ├── user.py              ← User (main app auth — different from MCP auth)
│       │   └── ...
│       └── services/                ← Imports from shared/services + adds app-specific
│           ├── reply_processor.py   ← Reply processing (main app only)
│           ├── notification_service.py
│           └── ...
│
├── mcp/                             ← MCP app
│   ├── backend/
│   │   └── app/
│   │       ├── models/              ← Imports from shared/models + adds MCP-specific
│   │       │   ├── user.py          ← MCPUser, MCPApiToken (MCP auth)
│   │       │   ├── integration.py   ← MCPIntegrationSetting
│   │       │   └── refinement.py    ← RefinementRun, RefinementIteration
│   │       ├── mcp/                 ← MCP protocol (MCP-only)
│   │       └── auth/                ← Token auth (MCP-only)
│   └── frontend/
│       └── src/
│           ├── pages/               ← MCP-specific pages (import shared/ui components)
│           └── ...
│
└── frontend/                        ← MAIN app frontend (existing)
    └── src/
        ├── components/              ← Imports from shared/ui + adds app-specific
        └── pages/
```

## How It Works

### Backend: Python path manipulation

Both backends add `shared/` to their Python path:

```python
# In mcp/backend/app/config.py or main.py
import sys
sys.path.insert(0, "/path/to/shared")

# Then import shared models
from shared.models.gathering import GatheringRun
from shared.services.apollo_service import ApolloService
```

Or use pip editable install:
```
# shared/setup.py or pyproject.toml
pip install -e ../shared
```

### Frontend: Workspace or symlink

```json
// Root package.json (monorepo workspace)
{
  "workspaces": ["shared/ui", "frontend", "mcp/frontend"]
}
```

Or simpler: Vite alias pointing to `shared/ui/`:
```ts
// vite.config.ts
resolve: { alias: { '@shared': '../shared/ui' } }
```

### Database: Same models, different connections

Both apps use the same SQLAlchemy model classes but connect to different databases:

```python
# Main app: DATABASE_URL = postgres://leadgen:...@leadgen-postgres:5432/leadgen
# MCP app:  DATABASE_URL = postgres://mcp:...@mcp-postgres:5433/mcp_leadgen
```

The `Base` class is injected per app — models don't hardcode which DB they use.

---

## Migration Path

### Phase 1: Extract shared models (immediate)
1. Create `shared/models/` with the common models
2. Both backends import from `shared/models/`
3. App-specific models stay in their respective `app/models/`

### Phase 2: Extract shared services (next)
1. Move `apollo_service.py`, `smartlead_service.py`, etc. to `shared/services/`
2. Both backends import from `shared/services/`
3. App-specific services (reply_processor, notification_service) stay local

### Phase 3: Extract shared UI components (later)
1. Create `shared/ui/` with reusable React components
2. Both frontends import via workspace alias
3. App-specific pages stay in their respective `src/pages/`

---

## Rules

1. **Shared code has NO app-specific imports.** It never imports from `backend/app/` or `mcp/backend/app/`.
2. **Shared models use dependency injection** for the Base class — no hardcoded DB connection.
3. **Changes to shared code require testing both apps.** CI should run tests for both.
4. **App-specific models CAN extend shared models** (add columns, relationships) via SQLAlchemy mixins.
5. **The `shared/` directory is NOT a separate service** — it's a Python package / npm workspace imported by both apps.
