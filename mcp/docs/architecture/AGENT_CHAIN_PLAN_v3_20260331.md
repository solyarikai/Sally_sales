# Agent Chain v3 — Approval-First Architecture

**Date**: 2026-03-31
**Principle**: MCP NEVER executes destructive actions without explicit user approval. Preview first, confirm second.

---

## Core Rule

Every tool that **changes state**, **spends credits**, or **affects campaigns** follows the same pattern:

```
User request → MCP shows EXACTLY what will happen → User says "yes" → MCP executes
```

No exceptions. No "smart auto-execution". No batch operations without per-item approval.

---

## Approval Matrix — Every Tool Classified

### TIER 1: EXPLICIT APPROVAL (user must say "yes" / "approve" / "go")

These tools show a preview and WAIT. They do NOT execute until the user explicitly confirms.

| Tool | What it does | What MCP shows before executing |
|------|-------------|------|
| `tam_gather` (Apollo) | Spends Apollo credits | Filter preview + cost estimate + "Proceed?" |
| `run_auto_pipeline` | Runs full background pipeline | KPIs + estimated cost + filters + "Approve to start?" |
| `control_pipeline` (pause) | Pauses a running pipeline | "I will pause pipeline #{id} ({name}, {progress}). Approve?" |
| `control_pipeline` (resume) | Resumes a paused pipeline | "I will resume pipeline #{id} from {state}. Approve?" |
| `set_pipeline_kpi` | Changes target count / contacts per company | "I will change target from {old} to {new}. Cost impact: {est}. Approve?" |
| `set_people_filters` | Changes search roles/titles | "I will change roles to {new_roles}. Takes effect on next batch. Approve?" |
| `smartlead_push_campaign` | Creates SmartLead campaign | Sequence preview + email accounts + contacts count + "Push as DRAFT?" |
| `gs_push_to_getsales` | Creates GetSales flow | Flow preview + sender profiles + "Push as DRAFT?" |
| `activate_campaign` | ACTIVATES sending to real leads | Full campaign summary + `user_confirmation` required (exact quote) |
| `gs_activate_flow` | ACTIVATES LinkedIn automation | Full flow summary + `user_confirmation` required (exact quote) |
| `import_smartlead_campaigns` | Downloads contacts for blacklist | "I found {N} matching campaigns: [{list}]. Import {total} contacts?" |
| `tam_re_analyze` | Re-classifies with different prompt | "I will re-analyze {N} companies with this prompt: [{preview}]. Same companies, new classification. Approve?" |
| `provide_feedback` + `tam_re_analyze` | User corrects targets | Show updated prompt diff + "Re-analyze with these corrections?" |

### TIER 2: CHECKPOINT GATES (pipeline auto-stops, waits for review)

These are NOT triggered by user — the pipeline hits them automatically and STOPS.

| Gate | When | What user sees | User action |
|------|------|---------------|-------------|
| CP1: `awaiting_scope_ok` | After blacklist check | Project context + blacklisted domains + campaign list | `tam_approve_checkpoint` or cancel |
| CP2: `awaiting_targets_ok` | After analysis | Target list + segments + target rate + borderline rejections | Approve, re-analyze, or explore |
| CP3: `awaiting_verify_ok` | Before FindyMail | Email count + cost estimate | Approve cost or skip |

### TIER 3: AUTO (no approval needed)

Read-only or deterministic operations that don't spend credits or change user-facing state.

| Tool | Why no approval needed |
|------|----------------------|
| `login` | Authentication |
| `get_context` | Read-only status |
| `check_integrations` | Read-only |
| `list_projects` | Read-only |
| `select_project` | Sets context, not destructive |
| `pipeline_status` | Read-only progress check |
| `list_email_accounts` | Read-only listing |
| `gs_list_sender_profiles` | Read-only listing |
| `list_smartlead_campaigns` | Read-only listing |
| `query_contacts` | Read-only CRM query |
| `crm_stats` | Read-only |
| `replies_list` / `replies_summary` | Read-only |
| `tam_pre_filter` | Deterministic, free, reversible |
| `tam_scrape` | Free, no credits |
| `tam_analyze` | Cheap + auto-creates CP2 gate (user reviews after) |
| `extract_people` | Free endpoint |
| `refinement_status` | Read-only |
| `tam_list_sources` | Read-only |
| `tam_explore` | 5 credits but always follows a user request |

### TIER 4: ONE-TIME GATES (mandatory once, then done)

| Gate | When | Flow |
|------|------|------|
| Offer verification | After `create_project` | "I understand you sell {X} to {Y}. Correct?" → loop until confirmed |
| Previous campaigns | After offer confirmed | "Have you launched campaigns for this project before?" → import or skip |

---

## Multi-Pipeline Disambiguation

When user has 2+ running pipelines and gives an ambiguous command:

```
User: "pause the pipeline"

MCP: "You have 2 running pipelines:
  1. #101 — IT consulting Miami (67/100 contacts, 4m elapsed)
  2. #102 — Video production London (12/100 contacts, 1m elapsed)

Which one to pause?"

User: "the IT consulting one"

MCP: "I will pause pipeline #101 (IT consulting Miami).
  Current progress: 67/100 contacts, 23 target companies, page 16.
  Progress will be saved — resume anytime.
  Approve?"

User: "yes"

MCP: [executes pause] "Pipeline #101 paused. Progress saved."
```

**Rules for disambiguation:**
1. If user provides run_id → use it directly
2. If user provides segment name / geo / keyword → match against run filters
3. If ambiguous → list all matching pipelines, ask user to pick
4. NEVER guess. ALWAYS confirm before executing.

---

## The Full User Flow — Step by Step

### Phase 0: Account Setup
```
User connects → login(token)                                    [AUTO]
MCP checks keys → shows missing integrations                    [AUTO]
User sets up keys in UI                                          [UI]
```

### Phase 1: Project & Offer
```
User: "my website is easystaff.io"
→ create_project(website="easystaff.io")                        [AUTO — creates project]
→ MCP scrapes website, extracts offer
→ "I understand EasyStaff provides payroll services              [GATE — offer verification]
   to SMEs hiring internationally. Correct?"
→ User confirms or corrects → loop until approved
→ "Have you launched campaigns before?"                          [ONE QUESTION]
→ User: "campaigns with petr"
→ import_smartlead_campaigns → "Found 5 campaigns, 2,400        [TIER 1 — shows preview]
   contacts. Import for blacklist?" → User approves
```

### Phase 2: Gathering
```
User: "find IT consulting in Miami"
→ tam_gather (without confirm_filters)                           [TIER 1 — preview]
→ "Apollo preview: Keywords=[...], Size=[10-200],
   Total: 3,200 companies. Cost: 4 credits. Proceed?"
→ User: "yes"
→ tam_gather (with confirm_filters=true)                         [executes]
→ Companies gathered, pipeline run #{id} created
```

### Phase 3: Auto Pipeline
```
→ run_auto_pipeline                                              [TIER 1 — preview]
→ "I will run auto pipeline on #{id}: target 100 contacts,
   3/company, ~34 target companies. Est cost: 10 credits.
   Approve?"
→ User: "yes"
→ Pipeline runs in BACKGROUND
→ User can check: pipeline_status                                [AUTO — read-only]
→ User can change: set_pipeline_kpi → preview + confirm          [TIER 1]
→ User can pause: control_pipeline(pause) → preview + confirm    [TIER 1]
→ Pipeline auto-stops at CP2 → user reviews targets              [GATE]
```

### Phase 4: Campaign
```
→ "Which email accounts for the campaign?"                       [ONE QUESTION]
→ User selects
→ smartlead_generate_sequence → shows preview                    [TIER 1 — preview]
→ User reviews sequence, says "looks good"
→ smartlead_push_campaign → "Push as DRAFT with                  [TIER 1]
   3 accounts, 102 contacts? Test email to you@email.com"
→ User: "yes"
→ Campaign created as DRAFT, test email sent
→ "Check inbox. Approve to launch."
→ User: "activate"
→ activate_campaign(user_confirmation="activate")                [TIER 1 — explicit quote]
→ Campaign ACTIVE, reply monitoring ON
→ If no Telegram: "Connect Telegram for notifications:           [PROMPT]
   http://46.62.210.24:3000/setup"
```

---

## Agent Responsibility Matrix

| Agent | Model | Task | Approval? |
|-------|-------|------|-----------|
| A0: Intent Router | gpt-4o-mini | Parse user message → determine which tool(s) to call | NO |
| A1: Industry Picker | gpt-4o-mini | Select industries from Apollo taxonomy | NO |
| A2: Keyword Picker | gpt-4.1-mini + embeddings | Select keywords from taxonomy | NO |
| A3: Size Inferrer | gpt-4o-mini | Infer company size from offer | NO |
| A4: Location Extractor | regex | Extract geo from query | NO |
| A5: Company Classifier | gpt-4o-mini | Classify companies as target/not-target | NO (result reviewed at CP2) |
| A6: Filter Optimizer | gpt-4.1-mini | Optimize filters after enrichment | NO (result shown in preview) |
| A7: People Filter Mapper | gpt-4o-mini | Infer roles/titles from offer | NO (shown in preview) |
| A8: Cost Estimator | math (no GPT) | Calculate credits, pages, dollars | NO |
| A9: Prompt Crafter | gpt-4o | Craft via negativa classification prompt | NO (prompt reviewed at CP2) |
| **DISAMBIGUATOR** | MCP logic | When 2+ pipelines/campaigns match → ask user | **YES — always asks** |
| **CONFIRMATION GATE** | MCP logic | Before any TIER 1 action → show preview + ask | **YES — always asks** |

---

## Implementation: `confirm` Parameter Pattern

All TIER 1 tools get a `confirm` boolean parameter:

```python
# Without confirm → return preview (what WILL happen)
control_pipeline(run_id=101, action="pause")
→ {"status": "awaiting_confirmation", "preview": "Pause pipeline #101 (IT consulting Miami, 67% complete)", ...}

# With confirm=true → execute
control_pipeline(run_id=101, action="pause", confirm=true)
→ {"status": "paused", "message": "Pipeline #101 paused. Progress saved."}
```

Tools that need this pattern added:
- `control_pipeline` (pause/resume)
- `set_pipeline_kpi`
- `set_people_filters`
- `run_auto_pipeline`
- `import_smartlead_campaigns` (already has preview for 0 matches, needs it for >0 too)

Tools that already have it:
- `tam_gather` (`confirm_filters` parameter)
- `activate_campaign` (`user_confirmation` parameter)
- `gs_activate_flow` (`user_confirmation` parameter)

---

## KPI Naming & Alignment Math

Three KPIs, explicit names:

| Field | Meaning | Default |
|-------|---------|---------|
| `target_people` | Total contacts to gather | 100 |
| `max_people_per_company` | Maximum contacts per company | 3 |
| `target_companies` | Target companies needed (DERIVED, optimistic) | ceil(100/3) = 34 |

**Formula**: `target_companies = ceil(target_people / max_people_per_company)`

**Alignment rules** — changing one recalculates the others:
- Change `target_people` → `target_companies` recalculated
- Change `max_people_per_company` → `target_companies` recalculated
- Change `target_companies` → `target_people` = `target_companies * max_people_per_company`

**Stop condition**: Pipeline stops when `total_people_found >= target_people`. `target_companies` is for display/estimation only.

Full math spec + all 7 change scenarios: `mcp/tests/test_kpi_alignment.md`

---

## Key Principle: ONE Question Per Turn

MCP asks exactly ONE thing at a time. Never:
- "What's your website AND which email accounts?"
- "Approve the pipeline AND choose the sequence?"

Always:
- "What's your website?" → wait → "Have you launched campaigns before?" → wait → "Proceed with these filters?" → wait

The `next_question` field in tool responses guides the agent to the single next question.
