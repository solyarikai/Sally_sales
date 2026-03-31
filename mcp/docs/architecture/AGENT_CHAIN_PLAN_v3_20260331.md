# Agent Chain v3 — Complete Specification

**Date**: 2026-03-31
**Merges**: v1 (exploration + bugs) + v2 (user flows + agents) + v3 (approval-first)
**Principle**: MCP NEVER executes destructive actions without explicit user approval. Full transparency at every step.

---

## Core Rules

1. **Approval-first**: Every credit-spending, state-changing, or campaign-affecting action shows preview → waits for user "yes" → executes.
2. **One question per turn**: Never dump 2+ questions. Ask one, wait, proceed.
3. **Full transparency**: Credits spent, remaining, estimated cost — shown at EVERY step.
4. **Offer context always**: GPT classification prompts ALWAYS include user's offer to prevent client/competitor confusion.
5. **KPIs always visible**: target_people, max_people_per_company, target_companies shown in UI and every response.
6. **CRM links always filtered**: Every response with a CRM link includes `project_id` filter.

---

## Approval Matrix

### TIER 1: EXPLICIT APPROVAL (preview → user says "yes" → execute)

| Tool | What it does | Preview shows |
|------|-------------|------|
| `tam_gather` (Apollo) | Spends credits | Filters + cost + total_available + "Proceed?" |
| `run_auto_pipeline` | Runs full background pipeline | KPIs + cost estimate + filters + "Approve?" |
| `control_pipeline` (pause) | Pauses a pipeline | "I will pause #{id} ({name}, {progress}). Approve?" |
| `control_pipeline` (resume) | Resumes a pipeline | "I will resume #{id} from {state}. Approve?" |
| `set_pipeline_kpi` | Changes KPI targets | "Change from {old} to {new}. Cost impact: {est}. Approve?" |
| `set_people_filters` | Changes search roles | "Change roles to {new}. Takes effect next batch. Approve?" |
| `import_smartlead_campaigns` | Downloads contacts for blacklist | "Found {N} campaigns, {total} contacts. Import?" (warns if 0 matches) |
| `smartlead_push_campaign` | Creates SmartLead DRAFT | Sequence preview + email accounts + contacts + settings + "Push as DRAFT?" |
| `gs_push_to_getsales` | Creates GetSales DRAFT | Flow preview + sender profiles + "Push as DRAFT?" |
| `activate_campaign` | ACTIVATES sending | Full summary + `user_confirmation` (exact quote) |
| `gs_activate_flow` | ACTIVATES LinkedIn sending | Full summary + `user_confirmation` (exact quote) |
| `tam_re_analyze` | Re-classifies with new prompt | "Re-analyze {N} companies with updated prompt: [{preview}]. Approve?" |

### TIER 2: CHECKPOINT GATES (pipeline auto-stops, user reviews)

| Gate | When | What user reviews |
|------|------|---------------|
| CP1: `awaiting_scope_ok` | After blacklist | Project context + blacklisted domains + campaign list |
| CP2: `awaiting_targets_ok` | After analysis | Target list + segments + target rate + borderline |
| CP3: `awaiting_verify_ok` | Before FindyMail | Email count + cost ($0.01/email). Skip = no verification |

### TIER 3: AUTO (no approval needed)

All read-only and deterministic tools: `login`, `get_context`, `pipeline_status`, `check_integrations`, `list_projects`, `select_project`, `list_email_accounts`, `gs_list_sender_profiles`, `list_smartlead_campaigns`, `query_contacts`, `crm_stats`, `replies_list`, `replies_summary`, `tam_pre_filter`, `tam_scrape`, `tam_analyze`, `extract_people`, `refinement_status`, `tam_list_sources`, `tam_explore`.

### TIER 4: ONE-TIME GATES

| Gate | When | Flow |
|------|------|------|
| Offer verification | After `create_project` | LOOP: "You sell {X} to {Y}. Correct?" → if no → "What's different?" → update → ask again → loop until "yes" |
| Previous campaigns | After offer confirmed | "Have you launched campaigns before?" → import or "none" |

---

## KPI System

| Field | Meaning | Default |
|-------|---------|---------|
| `target_people` | Total contacts to gather | 100 |
| `max_people_per_company` | Maximum contacts per company | 3 |
| `target_companies` | Target companies (DERIVED, optimistic) | ceil(100/3) = 34 |

**Formula**: `target_companies = ceil(target_people / max_people_per_company)`

**Alignment when user changes one**:
- Change `target_people` → recalc `target_companies`
- Change `max_people_per_company` → recalc `target_companies`
- Change `target_companies` → recalc `target_people = target_companies * max_people_per_company`

**Stop condition**: `total_people_found >= target_people`

Full math spec: `mcp/tests/test_kpi_alignment.md`

---

## The Full User Flow

### Phase 0: Account Setup
```
User connects → login(token)                                     [AUTO]
  ↓
MCP checks keys → returns: "Missing: apollo, openai.             [AUTO]
  Set up at http://46.62.210.24:3000/setup"
  ↓
User sets up keys in UI                                           [UI]
```

### Phase 1: Project & Offer
```
User: "my website is easystaff.io"
  ↓
create_project(website="easystaff.io")                            [AUTO]
  → Scrapes website via Apify residential proxy
  → Extracts offer to project.target_segments
  → Stores in DB, shows link to project page
  ↓
OFFER ALIGNMENT LOOP:                                             [TIER 4 GATE — LOOPS]
  MCP: "I understand EasyStaff provides payroll and contractor
        management to SMEs hiring internationally. Correct?"
  ↓
  User: "not quite, we focus on payroll only"
  → MCP updates project.target_segments
  → MCP: "Updated: EasyStaff provides payroll services
          to SMEs hiring internationally. Correct now?"
  → User: "yes"
  → offer_confirmed = true
  ↓
"Have you launched campaigns for this project before?"            [ONE QUESTION]
  ↓
User: "campaigns with petr"
  ↓
import_smartlead_campaigns(contains=["petr"])                     [TIER 1 — preview]
  → "Found 5 campaigns (2,400 contacts). Import for blacklist?"
  → (If 0 found: "No matches. Available: [...]. Try different rules.")
  → User: "yes"
  → Contacts imported, blacklist built
  → Reply analysis started in background for warm replies
  → "View contacts: http://46.62.210.24:3000/crm?project_id={id}"
```

### Phase 2: Gathering (Filter Discovery + Confirmation)
```
User: "find IT consulting in Miami"
  ↓
A0: Intent Router splits into segments                            [AUTO]
  → 1 segment: {segment: "IT consulting", geo: "Miami"}
  → (If 2+ segments: "I see 2 segments. Separate pipelines?" → user confirms)
  ↓
A1-A4: Filter Mapping                                             [AUTO]
  → A1: Industry picker → ["information technology & services"]
  → A2: Keyword picker (embeddings + GPT) → ["IT consulting", "managed services", ...]
  → A3: Size inferrer from offer → "10,200" (payroll = SMB)
  → A4: Location extractor → ["Miami, FL"]
  ↓
tam_gather (without confirm_filters)                              [TIER 1 — PREVIEW]
  → Probes Apollo: 3,200 companies available
  → Cost: 4 credits search + 5 credits exploration = $0.09
  → People defaults: VP HR, CHRO, Head of People (from offer)
  → "Apollo search preview:
       Keywords: IT consulting, managed services, ...
       Location: Miami, FL
       Size: 10-200 employees
       Total available: 3,200 companies
       Cost: 4 credits ($0.04) search + 5 credits ($0.05) exploration
       People roles: VP HR, CHRO, Head of People
       Max 3 per company, target 100 contacts (~34 companies)
     Proceed?"
  ↓
User: "yes" (or adjusts: "also add London" → re-preview)
  ↓
tam_gather (with confirm_filters=true)                            [EXECUTES]
  → Pipeline run #{id} created
  → "Gathering started. Pipeline: http://46.62.210.24:3000/pipeline/{id}"
```

### Phase 3: Exploration + Scale (Auto Pipeline)
```
run_auto_pipeline(run_id, target_people=100, max_people_per_company=3)  [TIER 1]
  → "Run auto pipeline: 100 contacts, max 3/company, ~34 targets.
     Estimated: 10 credits. Approve?"
  → User: "yes"
  → Pipeline runs in BACKGROUND
  ↓
=== ITERATION 1: Exploration (1 page, 25 companies) ===
  → Apollo search (1 credit)
  → Scrape websites (Apify residential proxy, free)
  → Classify via GPT-4o-mini (offer context included in prompt):
      "CONTEXT: User sells payroll services.
       TARGET = companies that would BUY payroll.
       COMPETITOR = companies that also sell payroll. NOT a target."
  → X/25 targets found
  ↓
=== EXPLORATION: Enrich top 5 targets (5 credits) ===              [AUTO]
  → Apollo enrichment → discover real keyword_tags, industries
  → Optimize filters: original keywords + discovered keywords
  → "Optimized filters found 40% more relevant companies."
  ↓
  (Exploration runs ONCE — 1 max. Then scale.)
  ↓
=== ITERATIONS 2+: Scale (4 pages per batch) ===
  → Apollo search with optimized filters
  → Scrape → Classify → Extract people (in PARALLEL)
  → Loop until target_people reached
  ↓
  (User can check: pipeline_status → KPIs, progress, elapsed, ETA)
  (User can change: set_pipeline_kpi → preview + confirm)
  (User can pause: control_pipeline → preview + confirm)
  (User can change roles: set_people_filters → preview + confirm)
  ↓
Pipeline auto-stops at target_people KPI
  → "Pipeline complete: 34 target companies, 102/100 contacts.
     Pages: 16. Credits: 16. View: [pipeline link]"
```

### Phase 3.5: Continue Gathering ("find more")
```
User: "find more" / "I need more contacts" / "continue"
  ↓
MCP detects existing run #{id} with 102 contacts
  ↓
set_pipeline_kpi(run_id, target_people=200)                       [TIER 1 — preview]
  → "Change target from 100 to 200. Need 98 more contacts.
     Estimated: 8 more pages = 8 credits ($0.08). Approve?"
  → User: "yes"
  ↓
control_pipeline(run_id, action="resume")                         [TIER 1 — preview]
  → "Resume pipeline #{id} from page 16. Target: 200 contacts. Approve?"
  → User: "yes"
  → Pipeline continues in background
```

### Phase 4: Campaign Creation
```
"While pipeline was gathering, which email accounts?"             [ONE QUESTION]
  ↓
list_email_accounts → shows available accounts                    [AUTO]
  → User selects accounts
  ↓
smartlead_generate_sequence                                       [AUTO — generates draft]
  → Uses project knowledge + patterns from top campaigns
  → If user provided sequence approach file → uses it
      (stored in ProjectKnowledge category="sequence_approach")
  → Returns 4-5 step sequence preview
  ↓
User reviews. Can edit:                                           [USER REVIEW]
  - "change subject of step 2"
  - "make it shorter"
  - "use this approach: [paste/file]" → stored in ProjectKnowledge
  ↓
smartlead_approve_sequence(sequence_id)                           [AUTO — marks approved]
  ↓
smartlead_push_campaign(sequence_id, email_account_ids)            [TIER 1 — preview]
  → "Push as DRAFT campaign:
       Sequence: 4 steps, plain text, no tracking
       Email accounts: 3 selected
       Contacts: 102 from pipeline #{id}
       Settings: stop on reply, 40% follow-up, Mon-Fri 9-18 target TZ
       Test email → your@email.com
     Push?"
  → User: "yes"
  → Campaign created as DRAFT, test email sent
  ↓
"Check your inbox at {email}. Approve to launch."
  → CRM link: http://46.62.210.24:3000/crm?campaign={id}&project_id={pid}
  → SmartLead link: https://app.smartlead.ai/app/email-campaigns-v2/{id}/analytics
  ↓
User: "activate"
  ↓
activate_campaign(campaign_id, user_confirmation="activate")      [TIER 1 — exact quote]
  → Campaign ACTIVE, reply monitoring ON
  → If Telegram not connected:
      "Connect Telegram for notifications: http://46.62.210.24:3000/setup"
  → "Campaign active. Reply monitoring ON.
     SmartLead: [link] | CRM: [link] | Pipeline: [link]"
```

### Phase 5: Post-Campaign
```
Reply monitoring runs in background (3-min poll)
  → Classifies: warm / meeting / interested / OOO / not-interested
  → Telegram notification for warm replies (if connected)
  ↓
User: "show warm replies"
  → replies_list(category="interested")                           [AUTO]
  → "3 warm replies. View: http://46.62.210.24:3000/tasks?project={name}&category=interested"
  ↓
User: "which leads need follow-ups?"
  → replies_followups                                             [AUTO]
  → List of leads needing follow-up + CRM link with filters
```

---

## Multi-Segment Parallel Pipelines

```
User: "Find IT consulting in Miami and video production in London"
  ↓
A0: Intent Router                                                  [AUTO]
  → [{segment: "IT consulting", geo: "Miami"},
     {segment: "video production", geo: "London"}]
  ↓
MCP: "I see 2 segments. Run as separate pipelines?                [ONE QUESTION]
  1. IT consulting — Miami
  2. Video production — London"
  ↓
User: "yes" → 2x tam_gather (each with preview + confirm)
  ↓
Both run in parallel as separate pipeline runs
```

**Disambiguation when 2 pipelines running:**
```
User: "pause the pipeline"
  ↓
MCP: "You have 2 running pipelines:                               [DISAMBIGUATE]
  1. #101 — IT consulting Miami (67/100 contacts, 4m elapsed)
  2. #102 — Video production London (12/100 contacts, 1m elapsed)
Which one to pause?"
  ↓
User: "the IT consulting one"
  ↓
MCP: "I will pause pipeline #101 (IT consulting Miami).           [TIER 1 — confirm]
  Progress: 67/100 contacts, 23 target companies, page 16.
  Approve?"
  ↓
User: "yes" → executes pause
```

**Rules:**
1. If run_id provided → use directly
2. If segment/geo/keyword matches 1 pipeline → use it, but still confirm
3. If ambiguous → list all, ask user to pick
4. NEVER guess. ALWAYS confirm before executing.

---

## Cost Transparency

Every credit-spending response MUST include:

```
Credits used: 6 (Apollo search: 4, enrichment: 2)
Credits remaining: 494
Estimated next step: 4 credits ($0.04)

Cost breakdown:
  Apollo: 6 credits ($0.06) — search + enrichment
  Apify: 0.02 GB ($0.01) — 47 websites scraped
  OpenAI: 12K tokens ($0.002) — classification (gpt-4o-mini)
  Total: $0.07
```

Account page shows all costs with datepicker: apollo credits+$, apify GB+$, openai tokens per model+$.

---

## Exploration Phase (Detailed)

After iteration 1 (25 companies gathered + classified):

1. **Pick top 5 targets** by confidence
2. **Enrich in Apollo** (5 credits) → extract `keyword_tags`, `industry`, `sic_codes`
3. **Upsert into apollo_taxonomy** → shared map grows for future users
4. **Optimize filters**: original keywords + discovered keywords from targets
5. **Show optimized filters**: "Optimized filters found 40% more relevant companies."

Exploration runs ONCE (1 max), then scale phase uses optimized filters.

**Offer context in classification prompt (MANDATORY)**:
```
CONTEXT: The user sells {project.target_segments}.
TARGET = companies that would BUY this product/service.
COMPETITOR = companies that also SELL similar products. NEVER classify competitors as targets.
If company USES the technology but doesn't BUILD it → NOT_A_MATCH.
```

---

## Agent Responsibility Matrix

| Agent | Model | Task | Approval? |
|-------|-------|------|-----------|
| A0: Intent Router | gpt-4o-mini | Parse message → tool(s) to call, multi-segment split | NO |
| A1: Industry Picker | gpt-4o-mini | Select industries from taxonomy (112 items) | NO |
| A2: Keyword Picker | gpt-4.1-mini + embeddings | Select keywords from taxonomy (pre-filtered by embedding similarity) | NO |
| A3: Size Inferrer | gpt-4o-mini | Infer company size from offer (payroll→10-200) | NO |
| A4: Location Extractor | regex | Extract geo from query | NO |
| A5: Company Classifier | gpt-4o-mini | Classify target/not-target with offer context | NO (reviewed at CP2) |
| A6: Filter Optimizer | gpt-4.1-mini | Optimize filters from enrichment data | NO (shown in preview) |
| A7: People Filter Mapper | gpt-4o-mini | Infer roles from offer (payroll→VP HR) | NO (shown in preview) |
| A8: Cost Estimator | math | Credits, pages, dollars | NO |
| A9: Prompt Crafter | gpt-4o | Craft via negativa classification prompt | NO (reviewed at CP2) |
| **DISAMBIGUATOR** | MCP logic | Multi-pipeline → ask which | **YES** |
| **CONFIRMATION GATE** | MCP logic | All TIER 1 → preview + confirm | **YES** |

---

## Feedback & Re-Analysis Loop

```
User sees targets at CP2: "48% accuracy — too many false positives"
  ↓
provide_feedback(feedback_type="targets",                          [AUTO — stores]
  feedback_text="Roobet is an operator, not a tech provider")
  ↓
tam_re_analyze(run_id, prompt_text=improved_prompt)                [TIER 1 — preview]
  → "Re-analyze 100 companies with updated prompt. 
     New exclusion: casino OPERATORS (not tech providers). Approve?"
  → User: "yes"
  → New iteration created (visible in UI, before/after comparison)
  → New target list + accuracy at CP2 again
  → Loop until user satisfied
```

---

## Sequence Approach from File

```
User: "use this approach for emails: [paste or file path]"
  ↓
If file (>2K tokens): User's agent (Opus) reads and extracts structured data
If paste (<2K tokens): MCP handles directly
  ↓
Store in ProjectKnowledge(category="sequence_approach")            [AUTO]
  → "Saved your sequence approach. Key elements: [tone, structure, CTA style]."
  ↓
When smartlead_generate_sequence runs → reads from ProjectKnowledge
```

---

## SmartLead Campaign Settings (Reference)

Every campaign pushed with these settings:
- **Plain text** (no HTML, no images)
- **No tracking** (no open/click pixels)
- **Stop on reply** (lead removed from sequence after replying)
- **40% follow-up** percentage
- **Schedule**: Mon-Fri 9:00-18:00 in target company timezone
- **Custom fields**: segment, normalized company name from pipeline
- **Test email**: auto-sent to user's email after creation
