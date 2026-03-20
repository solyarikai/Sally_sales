# LeadGen Platform — Claude Code Instructions

## Safety Rules (NON-NEGOTIABLE)

- **NEVER send messages to leads** via SmartLead, GetSales, or any outreach API
- **NEVER call approve-and-send, /send, or any message-sending endpoint**
- **NEVER call FindyMail API without explicit operator approval** (costs real money)
- **NEVER run scripts, scrapers, or DB operations locally.** ALL execution happens on Hetzner (46.62.210.24). Local machine is for code editing only.
- Only operators can send messages through the UI

## Execution Environment — HETZNER ONLY

**All scripts, scrapers, migrations, and DB queries run on Hetzner. Never locally.**

- Production DB, env vars, Puppeteer, Node.js — all on Hetzner
- SSH: `ssh hetzner` (host alias, aggressive rate-limiting — use 10-20s delays between connections)
- Run scripts: `ssh hetzner "cd ~/magnum-opus-project/repo && <command>"`
- DB access: `ssh hetzner "docker exec leadgen-postgres psql -U leadgen -d leadgen -c 'SQL'"`
- Alembic: `ssh hetzner "cd ~/magnum-opus-project/repo/backend && alembic upgrade head"`
- Node scripts: `ssh hetzner "cd ~/magnum-opus-project/repo && node scripts/<script>.js"`
- Deploy: `ssh hetzner "cd ~/magnum-opus-project/repo && git pull origin main && docker-compose up --build -d"`

**Local machine = edit code, commit, push. Hetzner = run everything.**

## Setup (after git pull)

Before using the gathering pipeline, the database migration must be applied:
```bash
cd backend && alembic upgrade head
```
This creates the gathering tables. Without it, all pipeline calls will fail.

## TAM Gathering Pipeline

This repo has a **reusable TAM gathering system**. Use it for ALL lead research tasks. **Never write ad-hoc scripts.**

Full architecture: `docs/pipeline/TAM_GATHERING_ARCHITECTURE.md`

### BEFORE starting: Ask which project

Before any pipeline work, ask the operator which project they're working on. List projects via `GET /api/contacts/projects/names` (header `X-Company-ID: 1`). company_id is ALWAYS 1.

This is a best practice, not a hard gate — **the real project confirmation happens at CHECKPOINT 1** (code-enforced, can't be bypassed). If you get the project wrong here, CP1 will catch it because the operator will see the wrong campaigns.

### BEFORE starting: Check for in-progress runs

Before starting a NEW gathering run, check if this project already has a paused run:
```python
runs = await gathering_service.get_runs(session, project_id=PROJECT_ID)
for r in runs:
    if r.current_phase in ("awaiting_scope_ok", "awaiting_targets_ok", "awaiting_verify_ok"):
        # This run is waiting for operator approval at a checkpoint!
        # Resume it instead of starting a new one.
```

If a run is paused at a checkpoint, find its pending gate:
```python
gates = await gathering_service.get_pending_gates(session, project_id=PROJECT_ID)
# Read gate.scope for the full checkpoint details (blacklist results, target list, etc.)
# Show to operator and ask for approval
```

**NEVER start a new gathering run if an existing run for the same project is waiting at a checkpoint.**

### THE PIPELINE IS STRICT LINEAR — 3 MANDATORY CHECKPOINTS

You MUST execute phases in this exact order. You MUST stop at each checkpoint and wait for operator confirmation. You CANNOT skip phases. You CANNOT proceed past a checkpoint without the operator saying yes.

**The system enforces this in code.** If you try to call scrape before blacklist is approved, the API returns an error. If you try to call analyze before scrape, error. The `current_phase` field on the gathering run tracks where you are.

```
Phase 1: GATHER+DEDUP ──── auto
Phase 2: BLACKLIST ──────── auto
   ★ CHECKPOINT 1 ──────── STOP. Confirm project + show blacklist. Code-enforced.
Phase 3: PRE-FILTER ─────── auto
Phase 4: SCRAPE ─────────── auto (free)
Phase 5: ANALYZE ────────── auto (cheap)
   ★ CHECKPOINT 2 ──────── STOP. Review targets. Code-enforced.
Phase 6: VERIFY (FindyMail) ── BLOCKED until CP2 approved
   ★ CHECKPOINT 3 ──────── STOP. Approve cost. Code-enforced.
Phase 7: PUSH ───────────── BLOCKED until CP3 approved
```

At any point the operator can:
- **Cancel**: `POST /runs/{id}/cancel` — abandons the run, rejects all pending gates
- **Re-analyze** (at CP2 only): `POST /runs/{id}/re-analyze` — tries a different prompt

### Step-by-step API calls

```
POST /api/pipeline/gathering/start                           # Phase 1: gather + dedup
POST /api/pipeline/gathering/runs/{id}/blacklist-check       # Phase 2: blacklist → creates gate
                                                             # ★ CHECKPOINT 1 — STOP. Show results. Wait.
POST /api/pipeline/gathering/approval-gates/{gate_id}/approve  # Operator approves scope
POST /api/pipeline/gathering/runs/{id}/pre-filter            # Phase 3: pre-filter
POST /api/pipeline/gathering/runs/{id}/scrape                # Phase 4: scrape
POST /api/pipeline/gathering/runs/{id}/analyze               # Phase 5: analyze → creates gate
                                                             # ★ CHECKPOINT 2 — STOP. Show targets. Wait.
POST /api/pipeline/gathering/approval-gates/{gate_id}/approve  # Operator approves targets
POST /api/pipeline/gathering/runs/{id}/prepare-verification  # Creates gate with cost estimate
                                                             # ★ CHECKPOINT 3 — STOP. Show cost. Wait.
POST /api/pipeline/gathering/approval-gates/{gate_id}/approve  # Operator approves FindyMail spend
```

Each checkpoint creates an `approval_gate` record. The gate_id is returned in the response.
The pipeline is physically stuck at checkpoint phases until the gate is approved via the API.
This survives session crashes — next session reads `current_phase` from the run and resumes.

### CHECKPOINT 1 — Project confirmation + Blacklist (CODE-ENFORCED, CANNOT BE BYPASSED)

**This is the real project gate.** The API response includes full project context. Show the operator:

**Project identity (operator confirms they're in the right place):**
- Project name and ID
- Total existing contacts in this project
- ALL active campaigns for this project (name, platform, lead count)

**Blacklist results (operator confirms scope is correct):**
- Companies checked / passed / rejected
- Per-campaign rejection breakdown (campaign name, domain count, contact count)
- Enterprise blacklist count
- Cross-project warnings (other projects' campaigns — informational only)

**You MUST ask:** "This run is scoped to **[project name]** (ID [id]) with [N] contacts in [N] campaigns: [list]. Correct? Proceed?"

If the operator says "wrong project" → cancel the run (`POST /runs/{id}/cancel`), start over.
If "wrong campaign" → fix campaign_filters, re-run blacklist.
If "looks good" → approve the gate.

### CHECKPOINT 2 — After Analysis (target list review)

**You MUST show the operator:**
- Total companies analyzed vs total companies that HAD scraped text (some may have been skipped due to scrape failures — report this)
- How many targets found (count, percentage, avg confidence)
- The target list: domain, company name, confidence, segment, 1-line reasoning
- Borderline rejections (confidence 0.4-0.6) so operator can override

**You MUST ask:** "Review the target list. Remove false positives, then confirm to proceed to FindyMail."

**You MUST NOT call FindyMail, Apollo API, or any credit-spending service until the operator confirms the target list.**

### CHECKPOINT 3 — Before FindyMail (cost approval)

**You MUST show the operator:**
- How many emails to verify
- Estimated FindyMail cost ($0.01/email)
- Breakdown by company

**You MUST ask:** "Approve FindyMail spend of ~$X.XX for X emails?"

**You MUST NOT call FindyMail until the operator says yes.**

### Analysis prompt — use the project's ICP

When running Phase 5 (ANALYZE), you need a `prompt_text` that describes the target ICP. **DO NOT ask the operator to write it from scratch.** Instead, build it from the project's existing knowledge:

```python
from sqlalchemy import select
from app.models.contact import Project
from app.models.project_knowledge import ProjectKnowledge

project = await session.get(Project, PROJECT_ID)
target_segments = project.target_segments  # ICP description
target_industries = project.target_industries

# Also get project knowledge for richer context
knowledge = await session.execute(
    select(ProjectKnowledge).where(
        ProjectKnowledge.project_id == PROJECT_ID,
        ProjectKnowledge.category.in_(["icp", "gtm", "outreach"]),
    )
)
kb_items = knowledge.scalars().all()
```

Combine `target_segments` + `target_industries` + relevant knowledge into the analysis prompt. If the project has no ICP defined, THEN ask the operator to describe their ideal customer.

Also check for existing prompts that worked well:
```python
prompts = await gathering_service.list_prompts(session, company_id=1, project_id=PROJECT_ID)
# If prompts exist with high avg_target_rate, suggest reusing them
```

### What "new" and "duplicate" mean

These words change meaning depending on which phase you're in. Always be precise:

| Context | "New" means | "Duplicate" means |
|---------|-------------|-------------------|
| After GATHER+DEDUP | Not in discovered_companies for this project from any previous run | Already known from a previous run (gets a new source_link only) |
| After BLACKLIST | Passed all blacklist checks for THIS project | N/A — use "rejected" instead |
| After ANALYZE | AI marked as target (is_target=true) | N/A — use "rejected" instead |

**NEVER say "1,800 new companies" after DEDUP without clarifying that blacklisting hasn't happened yet.** Say: "1,800 not previously seen for this project. Blacklist check is next."

### Available sources (8 adapters)

| source_type | What it does | Cost |
|-------------|-------------|------|
| `apollo.companies.api` | Apollo org search API | Free |
| `apollo.people.emulator` | Apollo People tab via Puppeteer | Free |
| `apollo.companies.emulator` | Apollo Companies tab via Puppeteer | Free |
| `clay.companies.emulator` | Clay TAM export with ICP text | ~$0.01/company |
| `clay.people.emulator` | Clay People search by domains | ~$0.01/domain |
| `google_sheets.companies.manual` | Import from Google Sheet URL (uses service account, auto-detects columns) | Free |
| `csv.companies.manual` | CSV file/URL import | Free |
| `manual.companies.manual` | Direct domain list | Free |

**Apollo and Clay run ONLY via Puppeteer emulators — NEVER via paid API.** This is to avoid spending credits. The emulators scrape the UI for free. The only credit-spending step in the entire pipeline is FindyMail (CP3). If for any reason you need to use a paid API (Apollo people enrichment, Clay API), you MUST get explicit operator approval first — treat it like a separate checkpoint.

### Blacklisting is PROJECT-SCOPED

Only campaigns from the SAME project trigger auto-rejection. Other projects' campaigns show as warnings (never auto-rejected).

Why: Different projects sell different products. EasyStaff RU (payroll) and Inxy (crypto payments) can legitimately contact the same company — different value propositions.

### Google Sheets input

When someone says "analyze this sheet" or "here's my Apollo/Clay export":
```python
source_type="google_sheets.companies.manual"
filters={
    "sheet_url": "https://docs.google.com/spreadsheets/d/SHEET_ID/edit",
    "tab_name": "Sheet1",  # optional, defaults to first tab
}
# Column mapping auto-detected from headers
```

**The adapter uses the system's Google Service Account** (same as Google Drive integration). If the sheet is in the shared Google Drive folder, it works automatically. No "Anyone with link" needed.

If the service account can't access the sheet, it falls back to public CSV export.

**If access fails**, the error message tells you exactly what to do:
1. Share the sheet with the service account email (check `GET /api/contacts/sheet-config`)
2. Move it to the shared Google Drive folder
3. Or set sharing to "Anyone with link"

**NEVER try to reinvent Google Sheets access.** The `google_sheets_service` is already configured with service account credentials. Use it.

### Rules

1. **Never write one-off scripts for TAM gathering.** Use the adapter pattern.
2. **Every search must create a GatheringRun.** No shadow searches.
3. **3 mandatory checkpoints.** Never skip them. Never proceed without operator confirmation.
4. **Project-scoped always.** Every query needs project_id. Blacklist only checks same-project campaigns.
5. **No FindyMail without approval.** This is the most expensive step. Always checkpoint 3.
6. **Default is Puppeteer, not API.** Apollo/Clay UI emulators are free. API costs credits = separate approval.
7. **Be precise with terminology.** "New" after dedup ≠ "clean". Blacklisting hasn't happened yet.
8. **Check for in-progress runs before starting new ones.** Resume paused checkpoints.
9. **Build analysis prompts from project knowledge.** Don't ask operator to write ICP from scratch.
10. **Report scrape failures at checkpoint 2.** If 40% of companies failed to scrape, operator needs to know.

### Key files

| File | Purpose |
|------|---------|
| `backend/app/services/gathering_service.py` | Pipeline orchestrator with phase enforcement |
| `backend/app/services/gathering_adapters/` | Source adapters (one per source) |
| `backend/app/api/gathering.py` | API endpoints (21 routes under /api/pipeline/gathering/) |
| `backend/app/models/gathering.py` | Data models (7 tables including gathering_prompts) |
| `docs/pipeline/TAM_GATHERING_ARCHITECTURE.md` | Full architecture document |

## General

- Backend: FastAPI + SQLAlchemy at `backend/`, runs on :8001
- Frontend: React + Vite + Tailwind at `frontend/`, runs on :5179
- API needs trailing slash locally (redirects 307 without it)
- API header: `X-Company-ID: 1`
- Deploy: `ssh hetzner "cd ~/magnum-opus-project/repo && git pull origin main && docker-compose up --build -d"`
