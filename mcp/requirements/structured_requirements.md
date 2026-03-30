# MCP Server — Requirements & MVP Plan

## Product Vision

Turn the LeadGen platform into a **no-code AI-operated system**. Sales operators interact via natural language through any MCP-compatible client (Claude Desktop, Cursor, etc.) — the MCP server translates intent into pipeline actions, campaign creation, and reply management. No repo access, no code writing, no wasted time.

**Two audiences:**
1. **Internal** — agency sales team (currently uses Claude Code directly against the repo)
2. **External** — future SaaS users who connect their own API keys

## Architecture Decision: Cloud-Hosted (MVP)

The MCP server runs on existing Hetzner infrastructure alongside the backend. Operators connect via MCP client → Hetzner MCP server → FastAPI backend → DB/services.

```
┌──────────────────────┐     ┌──────────────────────────────────┐
│  MCP Client          │     │  Hetzner (46.62.210.24)          │
│  (Claude Desktop,    │────▶│                                  │
│   Cursor, etc.)      │ SSE │  MCP Server (:8002)              │
└──────────────────────┘     │    │                             │
                             │    ▼                             │
                             │  FastAPI Backend (:8001)         │
                             │    │                             │
                             │    ▼                             │
                             │  PostgreSQL + Services           │
                             │                                  │
                             │  Frontend UI (:5179)             │
                             │  (links provided by MCP)         │
                             └──────────────────────────────────┘
```

**Why cloud, not local:**
- DB, Puppeteer, env vars already on Hetzner — no local setup burden
- Operators don't clone repos or run Docker
- Single deployment, instant updates for all users
- External users just connect MCP client to a URL

**Why NOT wrap another MCP (e.g. Apollo MCP):**
- We already have all Apollo endpoints as adapters with validation, dedup, blacklisting
- Wrapping MCP adds latency, schema translation overhead, and dependency on their availability
- Direct API integration via our adapters is faster, more reliable, and already built

---

## MVP Scope

### What's IN
1. **Auth & onboarding** — signup, API key management (SmartLead, GetSales, OpenAI, FindyMail)
2. **Pipeline flow** — gather contacts → blacklist → analyze → verify → campaign creation (full 12-phase)
3. **Reply automation** — view replies, approve/dismiss drafts, regenerate, follow-ups
4. **UI links** — every MCP response includes a link to the relevant UI page
5. **Usage logging** — every operator prompt and tool call logged for future model training

### What's OUT (post-MVP)
- Telegram outreach tool integration
- Multi-tenant billing / usage metering
- Custom adapter creation by external users
- MCP-to-MCP composition (Apollo MCP, Clay MCP)
- Mobile client support
- Self-hosted / local deployment option

---

## Use Cases

### UC-1: Onboarding — First-time setup

**Actor:** New operator
**Trigger:** Operator connects MCP client for the first time

```
Operator: "Hey, I want to set up my account"
MCP: "Welcome! Let's get you started.
      1. I've created your account.
      2. Now connect your integrations — open this page:
         → http://46.62.210.24/projects/new

      Required API keys:
      - SmartLead (for email campaigns)
      - GetSales (for LinkedIn outreach)
      - OpenAI (for AI classification & drafts)
      - FindyMail (for email verification — pay-per-use)

      You can paste them here or enter them in the UI."
Operator: "Here's my SmartLead key: abc123..."
MCP: "SmartLead connected. 47 campaigns found.
      Still need: GetSales, OpenAI, FindyMail.
      Or skip for now — you can add them later in:
      → http://46.62.210.24/projects/{id}/settings"
```

**Acceptance criteria:**
- [ ] MCP detects first-time user (no project, no API keys)
- [ ] Validates each API key by calling the respective service health endpoint
- [ ] Stores keys in `integration_settings` table scoped to user/company
- [ ] Returns link to project setup page

---

### UC-2: Gather prospects

**Actor:** Operator with configured project
**Trigger:** Natural language request for contacts

```
Operator: "Find me 2000 SaaS companies in DACH region, 50-500 employees,
           series A-B. I'm selling payroll automation."

MCP: "Got it. Let me plan this gathering run for project 'EasyStaff Global'.

      Source: Apollo Companies (Puppeteer emulator, free)
      Filters I'll apply:
      - Region: Germany, Austria, Switzerland
      - Employee count: 50-500
      - Industry: SaaS / Software
      - Funding: Series A, Series B

      Estimated results: ~2,500 companies
      Cost: $0 (scraping via Puppeteer)

      Shall I start?"

Operator: "Yes"

MCP: "Pipeline started. Run #142.
      → See live progress: http://46.62.210.24/pipeline/142

      Phase 1 (Gather+Dedup): Running...
      Phase 1 complete: 2,347 companies found, 1,891 new, 456 already known.

      Phase 2 (Blacklist): Running...
      Phase 2 complete. Results:

      ★ CHECKPOINT 1 — Please confirm:
      ┌──────────────────────────────────────────────────┐
      │ Project: EasyStaff Global (ID 9)                 │
      │ Total existing contacts: 12,450                  │
      │ Active campaigns: 3                              │
      │   - ES Global DACH v2 (SmartLead, 2,100 leads)   │
      │   - ES Global UK Tech (SmartLead, 1,800 leads)   │
      │   - ES Global LI DACH (GetSales, 900 leads)      │
      │                                                  │
      │ Blacklist results:                               │
      │   Checked: 1,891 | Passed: 1,654 | Rejected: 237 │
      │   - ES Global DACH v2: 189 domains overlap       │
      │   - ES Global LI DACH: 48 domains overlap        │
      │   - Enterprise blacklist: 12                     │
      └──────────────────────────────────────────────────┘

      Is this the right project and scope? Proceed?"
```

**Acceptance criteria:**
- [ ] Parses natural language into adapter filters (model-assisted mapping)
- [ ] Shows filter plan before executing
- [ ] Runs full pipeline with mandatory stops at CP1, CP2, CP3
- [ ] Each checkpoint shows structured data matching CLAUDE.md spec
- [ ] Provides UI links at every stage

---

### UC-3: Analysis with auto-prompt tuning

**Actor:** Operator at checkpoint 2
**Trigger:** Pipeline reaches analysis phase

```
MCP: "Phase 5 (Analyze) complete.

      ★ CHECKPOINT 2 — Review targets:
      Analyzed: 1,402 of 1,654 (252 skipped — scrape failed)
      Targets found: 312 (22.3%, avg confidence 0.78)

      Top targets:
      | Domain           | Company          | Conf  | Segment      | Reasoning                    |
      |-----------------|------------------|-------|--------------|------------------------------|
      | acme-saas.de    | ACME SaaS GmbH   | 0.95  | Mid-market   | 200 employees, HR tech stack |
      | cloudpay.ch     | CloudPay AG       | 0.91  | Enterprise   | Multi-country payroll need   |
      | ...             | ...              | ...   | ...          | ...                          |

      Borderline (0.4-0.6 confidence): 47 companies
      → Full list: http://46.62.210.24/pipeline/142/targets

      Review and confirm, or I can re-analyze with adjusted prompt."

Operator: "The confidence is too low. Too many marketing agencies slipping in.
           Tighten the ICP — only companies that clearly need payroll for remote teams."

MCP: "Re-analyzing with refined prompt. Excluding marketing/creative agencies,
      focusing on companies with remote/distributed team signals.

      ...Re-analysis complete.
      Targets: 198 (14.1%, avg confidence 0.85)
      Removed: 114 false positives (mostly agencies, consultancies)

      → Updated list: http://46.62.210.24/pipeline/142/targets
      Review again?"
```

**Acceptance criteria:**
- [ ] Builds analysis prompt from project's `target_segments` + `target_industries` + `ProjectKnowledge`
- [ ] Presents target table with confidence, segment, 1-line reasoning
- [ ] Reports scrape failures transparently
- [ ] Supports re-analysis (`POST /runs/{id}/re-analyze`) with operator feedback
- [ ] Agent can iteratively refine prompt aiming for >85% precision target

---

### UC-4: Campaign creation with GOD_SEQUENCE

**Actor:** Operator after target approval + verification
**Trigger:** Pipeline reaches push phase

```
MCP: "Verification complete. 198 companies → 423 verified emails.

      Generating campaign sequence using best-practice patterns...

      Knowledge applied:
      - Universal: 5-step cadence, Day 0/3/4/7/7, thread replies
      - Business (easystaff.io): payroll positioning, compliance angle, case studies
      - Project (EasyStaff Global): DACH market, English language, remote-first focus
      → View knowledge: http://46.62.210.24/projects/9/knowledge

      Draft sequence:
      ┌─────────────────────────────────────────────────────────────┐
      │ Step 1 (Day 0): Subject: {{first_name}} — remote payroll   │
      │   Body: Hi {{first_name}}, noticed {{company_name}} is...  │
      │                                                             │
      │ Step 2 (Day 3): [thread reply, no subject]                  │
      │   Body: Quick thought — companies like [case study]...      │
      │                                                             │
      │ ... (3 more steps)                                          │
      └─────────────────────────────────────────────────────────────┘

      Create as DRAFT campaign in SmartLead? You'll add leads + activate manually."

Operator: "Create it."

MCP: "Campaign created: 'ES Global DACH SaaS Q1-2026' (DRAFT)
      → SmartLead: https://app.smartlead.ai/app/email-campaigns-v2/54321/analytics
      → CRM view: http://46.62.210.24/crm?project=9

      Next steps (manual):
      1. Review sequence in SmartLead UI
      2. Add leads from the verified list
      3. Activate when ready"
```

**Acceptance criteria:**
- [ ] Generates sequence from 3-level knowledge (universal + business + project)
- [ ] Shows what knowledge was applied (transparency)
- [ ] Creates SmartLead campaign as DRAFT only (never auto-activates)
- [ ] Returns both SmartLead URL and internal CRM link
- [ ] Knowledge base link provided for operator to review/edit source material

---

### UC-5: Reply management

**Actor:** Operator checking replies
**Trigger:** Operator asks about replies or gets notified

```
Operator: "What replies do I have today?"

MCP: "Project 'EasyStaff RU' — 12 new replies since yesterday:

      🟢 Meetings (2):
        - Марина Козлова (Acme Corp) — wants a call Thursday
        - Дмитрий Петров (CloudTech) — confirmed demo

      🟡 Interested (4):
        - Анна Соколова — asking about pricing
        - ...

      🔴 Not Interested (3): auto-archived
      ❓ Questions (3): drafts ready for review

      → Open replies: http://46.62.210.24/tasks?tab=replies&project=easystaff-ru

      Want me to show the draft replies for the 3 questions?"

Operator: "Show me the questions"

MCP: "1. Сергей Иванов (TechCorp): 'Какая стоимость для команды из 50 человек?'
        Draft: 'Сергей, добрый день! Для команды из 50...'
        → Review: http://46.62.210.24/tasks?tab=replies&lead=sergey@techcorp.com&project=easystaff-ru

      2. ...

      Approve, edit, or regenerate?"

Operator: "Approve #1, regenerate #2 with more detail about compliance"
```

**Acceptance criteria:**
- [ ] Summarizes replies grouped by category (meetings, interested, questions, etc.)
- [ ] Shows AI-generated drafts inline
- [ ] Supports approve, dismiss, regenerate with operator instructions
- [ ] Deep links to specific replies in UI with correct project context
- [ ] Never sends messages directly — only queues approved drafts for operator to send in UI

---

### UC-6: Check pipeline / project status

**Actor:** Operator checking progress
**Trigger:** Operator asks about status

```
Operator: "What's the status of my DACH gathering?"

MCP: "Run #142 (EasyStaff Global → Apollo DACH SaaS):
      Current phase: awaiting_targets_ok (Checkpoint 2)

      Progress:
      ✅ Gathered: 2,347 companies (1,891 new)
      ✅ Blacklisted: 1,654 passed
      ✅ Pre-filtered: 1,654 → 1,402 (252 offline/junk)
      ✅ Scraped: 1,150 of 1,402 (252 failed)
      ✅ Analyzed: 312 targets (22.3%)
      ⏸️ Waiting for your approval on target list
      ⬜ Verify (FindyMail)
      ⬜ Campaign creation

      → Pipeline view: http://46.62.210.24/pipeline/142
      → Target list: http://46.62.210.24/pipeline/142/targets

      Ready to review targets?"
```

**Acceptance criteria:**
- [ ] Shows phase-by-phase progress with counts
- [ ] Identifies paused checkpoints and prompts operator to resume
- [ ] Links to pipeline and target views

---

### UC-7: Usage logging (passive)

**Actor:** System (background)
**Trigger:** Every operator interaction

**What gets logged:**
- Timestamp, user ID, session ID
- Raw operator prompt text
- MCP tool called + arguments
- MCP response (structured)
- Latency per tool call
- Operator action on result (approved / rejected / modified)

**Storage:** `mcp_usage_logs` table

```sql
CREATE TABLE mcp_usage_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    session_id TEXT NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT now(),
    prompt_text TEXT,              -- raw operator input
    tool_name TEXT,                -- MCP tool invoked
    tool_arguments JSONB,          -- tool input
    tool_result JSONB,             -- tool output (truncated)
    latency_ms INTEGER,
    operator_action TEXT,          -- approve/reject/modify/ignore
    operator_feedback TEXT         -- free-text if they modified
);
```

**Acceptance criteria:**
- [ ] Every tool call logged automatically (middleware)
- [ ] Raw prompts stored for training data
- [ ] Operator actions on MCP suggestions tracked
- [ ] Query interface for analyzing usage patterns

---

## MCP Tools Inventory

### Pipeline Tools (extend existing `gathering_mcp.py`)

| Tool | Description | Phase |
|------|-------------|-------|
| `pipeline_start` | Start a gathering run with NL or structured filters | Phase 1 |
| `pipeline_status` | Get current status of a run | Any |
| `pipeline_list_runs` | List runs for a project | Any |
| `pipeline_checkpoint_review` | Get checkpoint details for operator review | CP1/CP2/CP3 |
| `pipeline_checkpoint_approve` | Approve a checkpoint gate | CP1/CP2/CP3 |
| `pipeline_checkpoint_reject` | Reject/cancel at a checkpoint | CP1/CP2/CP3 |
| `pipeline_reanalyze` | Re-run analysis with adjusted prompt | CP2 |
| `pipeline_advance` | Advance to next phase (blacklist → prefilter → scrape → analyze) | Auto phases |

### Campaign Tools

| Tool | Description |
|------|-------------|
| `campaign_generate_sequence` | Generate GOD_SEQUENCE for approved targets |
| `campaign_create_draft` | Create draft campaign in SmartLead/GetSales |
| `campaign_list` | List campaigns for a project |
| `campaign_status` | Get campaign analytics (send/open/reply rates) |

### Reply Tools

| Tool | Description |
|------|-------------|
| `replies_summary` | Get reply counts by category for a project |
| `replies_list` | List replies with filters (category, needs_reply, date range) |
| `replies_get_draft` | Get AI draft for a specific reply |
| `replies_approve` | Queue draft for sending (operator sends in UI) |
| `replies_dismiss` | Dismiss a reply (mark as handled) |
| `replies_regenerate` | Regenerate draft with operator instructions |
| `replies_followups` | List pending follow-up drafts |

### Project Tools

| Tool | Description |
|------|-------------|
| `project_list` | List all projects |
| `project_create` | Create a new project |
| `project_setup` | Configure project (ICP, segments, sender identity) |
| `project_knowledge` | View/edit project knowledge base |
| `project_integrations` | Manage API keys for a project |

### System Tools

| Tool | Description |
|------|-------------|
| `auth_signup` | Create new account |
| `auth_status` | Check connected integrations |
| `ui_link` | Generate deep link to any UI page with correct context |

---

## MVP Build Plan

### Phase 0: Foundation (Week 1)

**Goal:** MCP server skeleton, auth, and transport.

1. **MCP server setup** (`mcp/server.py`)
   - Python MCP SDK (`mcp` package)
   - SSE transport (HTTP, not stdio — cloud-hosted)
   - Tool registration framework
   - Session management (stateful per user)

2. **Auth layer**
   - User signup/login → JWT tokens
   - MCP session tied to authenticated user
   - API key storage (encrypted) in `integration_settings`
   - Key validation on connect (SmartLead health check, etc.)

3. **Usage logging middleware**
   - `mcp_usage_logs` table + Alembic migration
   - Auto-log every tool call with prompt, args, result, latency
   - Store raw operator prompts from MCP messages

4. **UI link helper**
   - `ui_link(page, params)` → full URL with project context
   - Every tool response includes `_links` field

**Deliverable:** MCP client can connect, authenticate, and call a `ping` tool.

---

### Phase 1: Pipeline Tools (Week 2)

**Goal:** Full gathering pipeline operable via MCP.

1. **Refactor `gathering_mcp.py`** — current code is tool definitions only; add full phase orchestration
2. **`pipeline_start`** — accept NL description, map to adapter + filters (use LLM for NL→filters)
3. **`pipeline_advance`** — single tool that runs the next auto-phase (blacklist, prefilter, scrape, analyze)
4. **`pipeline_checkpoint_review`** — format checkpoint data for MCP response (structured, not HTML)
5. **`pipeline_checkpoint_approve / reject`** — gate approval via MCP
6. **`pipeline_reanalyze`** — re-run analysis with modified prompt
7. **`pipeline_status` / `pipeline_list_runs`** — status queries

**Key design:** Pipeline tools don't bypass the existing phase enforcement. They call the same API endpoints. The 3-checkpoint model is preserved exactly as-is.

**Deliverable:** Operator can run entire gathering pipeline from MCP client.

---

### Phase 2: Campaign Creation (Week 3)

**Goal:** Generate and create campaigns from MCP.

1. **`campaign_generate_sequence`** — calls GOD_SEQUENCE with 3-level knowledge assembly
2. **`campaign_create_draft`** — push to SmartLead/GetSales as DRAFT
3. **`campaign_list` / `campaign_status`** — read-only campaign queries
4. **Sequence preview** — show draft sequence in MCP response before creating

**Key design:** Campaigns are always DRAFT. MCP never activates or adds leads. Operator does that in SmartLead/GetSales UI.

**Deliverable:** End-to-end flow: gather → analyze → verify → create campaign draft.

---

### Phase 3: Reply Tools (Week 3-4)

**Goal:** Reply management via MCP.

1. **`replies_summary`** — category counts per project
2. **`replies_list`** — paginated reply list with drafts
3. **`replies_approve / dismiss / regenerate`** — operator actions on drafts
4. **`replies_followups`** — pending follow-up drafts
5. **Deep links** — every reply includes UI link with `?lead=&project=` params

**Key design:** `replies_approve` queues the draft — it does NOT send. Operator sends via UI. This is the same safety model as the current system.

**Deliverable:** Operator can review and act on replies from MCP client.

---

### Phase 4: Project & Onboarding (Week 4)

**Goal:** Self-service project setup.

1. **`project_create`** — create project with ICP, segments, sender identity
2. **`project_integrations`** — connect/validate API keys
3. **`project_knowledge`** — view and edit knowledge base entries
4. **Onboarding flow** — detect new user, guide through setup
5. **`auth_signup` / `auth_status`** — account management

**Deliverable:** New operator can go from zero to first pipeline run via MCP.

---

### Phase 5: Polish & Deploy (Week 5)

1. **Error handling** — clear error messages for common failures (bad API key, rate limit, etc.)
2. **Progress updates** — long-running phases (scrape, analyze) send progress via MCP notifications
3. **Usage analytics** — dashboard query on `mcp_usage_logs`
4. **Documentation** — MCP tool descriptions, onboarding guide
5. **Production deploy** — MCP server in docker-compose alongside backend

---

## Technical Decisions

### Transport: SSE over HTTP

MCP supports stdio and SSE. Since this is cloud-hosted:
- **SSE** — works over HTTP, no local process needed, firewall-friendly
- Operator configures MCP client with `http://46.62.210.24:8002/mcp` endpoint
- Auth via Bearer token in headers

### MCP Server Framework

Use the official Python MCP SDK (`mcp` package). It handles:
- Tool registration with JSON Schema
- SSE transport
- Session management
- Progress notifications

### Tool Responses: Always Structured

Every tool response follows this shape:
```json
{
  "status": "success",
  "data": { ... },
  "_links": {
    "pipeline": "http://46.62.210.24/pipeline/142",
    "targets": "http://46.62.210.24/pipeline/142/targets"
  },
  "_next_action": "Review the target list and approve or request re-analysis"
}
```

- `_links` — always present, relevant UI pages
- `_next_action` — hint for what the operator should do next
- Structured data — MCP client (Claude, etc.) can format nicely

### NL → Filters Mapping

For `pipeline_start`, the operator writes natural language. The MCP server:
1. Sends the NL request + available adapter schemas to the LLM
2. LLM returns structured `{source_type, filters}`
3. MCP validates filters against adapter schema
4. Shows the interpreted plan to operator for confirmation before executing

This uses the operator's own OpenAI key (already stored). Cost: ~$0.01 per interpretation.

### Safety Model (unchanged)

- 3 mandatory checkpoints survive MCP exactly as they are
- `replies_approve` queues but never sends
- Campaign creation is always DRAFT
- FindyMail requires explicit cost approval
- All existing `CLAUDE.md` safety rules apply

---

## File Structure

```
mcp/
├── requirements.md          ← this file
├── server.py                ← MCP server entry point (SSE transport)
├── auth.py                  ← JWT auth, session management
├── tools/
│   ├── __init__.py
│   ├── pipeline.py          ← gathering pipeline tools
│   ├── campaign.py          ← campaign creation tools
│   ├── replies.py           ← reply management tools
│   ├── project.py           ← project setup tools
│   └── system.py            ← auth, status, ui_link
├── middleware/
│   ├── __init__.py
│   ├── logging.py           ← usage logging middleware
│   └── links.py             ← UI link injection
├── nlp/
│   ├── __init__.py
│   └── filter_mapper.py     ← NL → adapter filters (LLM-assisted)
└── migrations/
    └── add_mcp_tables.py    ← Alembic migration for mcp_usage_logs
```

## Essential Filters — Mandatory Before Gathering

When an operator says something vague like "find production media companies in Dubai", the system MUST NOT execute immediately. It must clarify essential filters first.

### Why this matters

Apollo MCP (community) just fires with whatever the AI guesses — "production media" + "UAE" → returns 4,000+ companies across 160 pages, burns 160 credits silently. No size filter, no page cap, no confirmation. Our system rejects this.

### Required filters for Apollo/Clay API sources

| Filter | Why essential | What happens without it |
|--------|--------------|------------------------|
| **Company size range** (`organization_num_employees_ranges`) | A 5-person startup and a 10,000-person enterprise are different ICPs. This is the #1 filter that determines result quality. | Returns everything — wastes analysis credits on irrelevant companies |
| **Max pages** (`max_pages`) | Controls credit spend. Each page = 1 Apollo credit, 25 companies. | Could burn 100+ credits on a single search |
| **Keywords OR locations** | At least one required for meaningful results | Returns random companies globally |

### Recommended additional filters (AI should suggest)

| Filter | When to suggest |
|--------|----------------|
| **Funding stage** | When ICP mentions "startup", "growth stage", "Series A" |
| **Industry keywords** | Always — refine beyond the initial query |
| **Revenue range** | When targeting enterprise or mid-market specifically |
| **Technologies used** | When ICP is tech-specific (e.g. "companies using Salesforce") |

### How it works

1. User: "Find production media companies in Dubai"
2. System detects missing: company size, max pages
3. System responds: "Before I search, I need to know:
   - What company size? (e.g. 10-50, 50-200, 200-1000 employees)
   - How many pages to fetch? (each page = 25 companies, 1 Apollo credit)
   - Any funding stage preference? (optional)"
4. User: "10-50 employees, 4 pages, any funding"
5. System executes with validated filters, returns: "~100 companies, ~4 credits"

### Server-side enforcement

The `tam_gather` tool rejects API source calls missing essential filters with a structured error:
```json
{
  "error": "missing_essential_filters",
  "message": "Cannot proceed — essential filters missing. Ask the user to specify:\n  - company size range\n  - max_pages",
  "hint": "Example: organization_num_employees_ranges: ['11,50'] for 11-50 employees"
}
```

This is enforced at the dispatcher level — the AI cannot bypass it even if it tries. Manual/CSV/Sheets sources skip this validation since they don't use credits.

### Comparison with Apollo MCP

| Behavior | Apollo MCP | Our MCP |
|----------|-----------|---------|
| Vague query handling | Executes immediately with whatever AI guesses | Rejects, asks for essential filters |
| Credit spend warning | None | Shows estimated credits before executing |
| Company size default | None — returns all sizes | REQUIRED — must be specified |
| Page limit | None — fetches all pages | REQUIRED for API sources |
| Confirmation before execution | None | Response shows exact filters applied + credit estimate |
| Result dedup | None — duplicates across calls | Dedup by domain per project |

---

## Open Questions

1. **Auth for external users** — JWT vs API key vs OAuth? MVP can start with simple API key per user.
2. **Multi-project scope** — Should MCP tools require `project_id` on every call, or should there be a "current project" context?  Recommendation: current project context set once, overridable per call.
3. **Progress during long phases** — Scraping 1000+ websites takes minutes. Use MCP progress notifications or polling? Recommendation: SSE notifications (MCP spec supports `notifications/progress`).
4. **Rate limiting** — Should MCP calls be rate-limited per user? Yes for external, no for internal MVP.
5. **Prompt auto-tuning at CP2** — Should the MCP agent autonomously refine the analysis prompt until >85% precision, or always ask the operator? Recommendation: suggest refinements but always confirm before re-running.
