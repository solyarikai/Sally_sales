# MCP Agent Chain Plan v2 — 2026-03-30

## What the previous plan (AGENT_CHAIN_PLAN.md) misses

| Gap | Impact | Details |
|-----|--------|---------|
| **No pre-flight checklist** | User launches gathering without essential data → pipeline breaks or produces garbage | Plan assumes sequential steps but doesn't define what MUST be collected before ANY gathering can start |
| **No "brief mode" for power users** | User provides a 160-line strategy doc (like cases/IGAMING_PROVIDERS_BRIEF.md) and says "use this" — MCP doesn't know how to extract all needed info at once | Plan only covers "user types a few words" case |
| **No responsibility matrix** | Unclear who does what: MCP tool vs user's agent (Opus) vs GPT-4o-mini | Some tasks need Opus (big file summarization), some need GPT-4.1 (prompt crafting), some need GPT-4o-mini (classification at scale) |
| **No "one question at a time" enforcement** | default_requirements.md says "only one flow-blocking question each time" but plan shows multiple questions | MCP should ask one thing, get answer, proceed — never dump 5 questions |
| **Exploration not triggered automatically** | Plan shows tam_explore as separate tool user must call — should auto-run after Checkpoint 2 | Lost 70%→55% target rate because user doesn't know to call it |
| **No orchestrator for full auto mode** | Power user says "launch everything for EasyStaff-Global IT consulting Miami" — MCP can't do it in one shot | Need run_full_pipeline meta-tool |
| **Campaign readiness not verified** | SmartLead push can fail silently if email accounts not selected, sequence not approved, etc. | Need pre-push checklist |

---

## Pre-Flight Checklist — REQUIRED before any gathering

Every pipeline needs ALL of these. MCP must collect each one before proceeding. Ask ONE at a time.

| # | Data point | How MCP gets it | Blocks |
|---|-----------|----------------|--------|
| 1 | **MCP token** | User pastes token or signs up | Everything |
| 2 | **API keys** (Apollo, OpenAI, SmartLead, Apify) | User sets in Setup UI or via configure_integration | Gathering (Apollo), Classification (OpenAI), Campaign (SmartLead), Scraping (Apify) |
| 3 | **Project** (name) | User tells name or MCP creates from website | Everything pipeline-scoped |
| 4 | **Offer** (what user sells) | Scrape website OR user describes | Classification (without it, GPT confuses clients vs competitors) |
| 5 | **Previous campaigns** (for blacklist) | User tells campaign name pattern OR says "none" | Blacklist — without it, may re-contact existing leads |
| 6 | **Segment** (what to gather) | User describes: "IT consulting in Miami" | Filter mapping |
| 7 | **Geo** (where) | Extracted from segment OR asked | Apollo location filter |
| 8 | **Size** (company size) | Auto-inferred from offer OR asked | Apollo size filter |
| 9 | **Destination** (SmartLead / GetSales / both) | Auto if only one key, ask if both | Campaign creation |
| 10 | **Email accounts** | User selects from list of their SmartLead accounts | Campaign creation + test email |

### What can be auto-inferred (user doesn't need to provide):
- **Size**: from offer analysis (payroll → 10-200; enterprise SaaS → 200-5000)
- **Destination**: from which keys are configured
- **Geo**: from segment description ("in Miami" → Miami)
- **Blacklist**: from campaign_filters on project (if campaigns already loaded)

### What MUST come from user:
- Token, API keys (security — can't auto-discover)
- Offer/website (critical for classification quality)
- Segment description (what to gather)
- Email accounts for campaign (which sender identity)

---

## Single Adaptive Flow — No Modes

There are no "modes." MCP always runs the same pre-flight checklist. The only difference is how much data the user provides upfront:

- User sends 3 words → 1/10 items filled → MCP asks 9 questions (one at a time)
- User sends a strategy doc → Opus extracts 9/10 items → MCP asks 1 question
- User says "launch for EasyStaff-Global, same as before" → 10/10 from context → MCP confirms and runs

**MCP never decides a "mode." It checks the checklist. Whatever's missing, it asks. Whatever's provided, it uses.**

### Example: minimal input
```
User: "I want to gather IT consulting companies"
MCP:  [checks: offer=❌] "What's your company website?"
User: "easystaff.io"
MCP:  [checks: geo=❌] "Got it — EasyStaff does payroll. Where should we look?"
User: "Miami, 50-200 employees"
MCP:  [checks: all ✅] → shows filter preview → proceeds
```

### Example: strategy doc
```
User: "Use cases/IGAMING_PROVIDERS_BRIEF.md — launch in SmartLead"
  → User's Opus reads the 160-line doc, extracts structured data, calls MCP tools
MCP:  [checks: email_accounts=❌] "All ready. Which SmartLead email accounts?"
User: "from Mifort campaigns"
MCP:  [checks: all ✅] → proceeds with exploration from examples → full pipeline
```

### File processing boundary
- **<2K tokens**: MCP's gpt-4o-mini handles it (short user messages, small CSVs)
- **>2K tokens**: User's agent (Opus) must read and extract structured data before calling MCP tools. MCP can't process huge strategy docs — it's the agent's job to summarize.

---

## Agent Responsibility Matrix

| Step | Agent | Model | Input | Output |
|------|-------|-------|-------|--------|
| **File parsing** (>2K tokens) | User's agent (Opus) | Claude Opus | Strategy doc, CSV, brief | Structured JSON for MCP |
| **File parsing** (<2K tokens) | MCP internal | gpt-4o-mini | Short user message | Structured segments |
| **Intent splitting** | MCP: parse_gathering_intent | gpt-4o-mini | "IT consulting Miami + video London" | [{segment, geo}] |
| **Filter mapping** | MCP: filter_mapper.py | gpt-4.1-mini | Segment + taxonomy maps | Apollo filter set |
| **Filter optimization** (from examples) | MCP: tam_enrich_from_examples | Apollo API + gpt-4o-mini | 5 example domains | Optimized keyword_tags |
| **Classification prompt CREATION** | MCP: gathering_service | gpt-4.1-mini | Offer + segment + exclusions | Via negativa rules |
| **Classification prompt APPLICATION** | MCP: gathering_service | gpt-4o-mini | Rules + 500 company texts | target/not-target per company |
| **Exploration enrichment** | MCP: tam_explore | Apollo API | Top 5 targets | New keywords for taxonomy |
| **Sequence generation** | MCP: campaign_intelligence | gpt-4o-mini | Offer + patterns | 4-5 email sequence |
| **Quality review** | User's agent (Opus) | Claude Opus | Target list + websites | Corrections, feedback |

---

## Full Automated Flow (when all data is available)

```
USER: "Use cases/IGAMING_PROVIDERS_BRIEF.md — launch in SmartLead"
  │
  ├─ User's Opus extracts structured brief → passes to MCP
  │
  ▼
MCP: PREFLIGHT CHECK
  │  ✅ Token: present
  │  ✅ Apollo key: configured
  │  ✅ OpenAI key: configured
  │  ✅ SmartLead key: configured
  │  ✅ Apify key: configured
  │  ✅ Project: "Mifort-iGaming" (create if needed)
  │  ✅ Offer: "IT outsourcing for iGaming" (from website scrape)
  │  ✅ Segment: "iGaming technology providers"
  │  ✅ Geo: Malta, Gibraltar, Cyprus, UK, ...
  │  ✅ Size: 11-1000
  │  ❓ Email accounts: MISSING → ask user
  │  ✅ Destination: SmartLead
  │
  ▼
MCP: "All ready except email accounts. Which SmartLead accounts
      to use? Here are yours: [list]"
  │
  ├─ User: "Use the ones from Mifort campaigns"
  │
  ▼
MCP: EXPLORATION (from examples)
  │  → Enrich softswiss.com, pragmaticplay.com, betconstruct.com,
  │    digitain.com, evoplay.games in Apollo (5 credits)
  │  → Extract their keyword_tags + industries
  │  → Build optimized filter set
  │
  ▼
MCP: FILTER PREVIEW
  │  "Apollo search preview:
  │   Keywords: igaming platform, casino software, game provider, ...
  │   Location: Malta, Gibraltar, Cyprus, UK, ...
  │   Size: 11-1000
  │   Total available: 2,847 companies
  │   Default (≈30 targets): 4 credits
  │   Full run: 114 credits → ≈996 targets
  │   (35% estimated conversion)
  │   Proceed?"
  │
  ├─ User: "yes, default"
  │
  ▼
MCP: GATHERING + PIPELINE
  │  → Apollo search (4 credits, ~100 companies)
  │  → Blacklist check (project-scoped)
  │  → Scrape websites (Apify proxy)
  │  → Classify (domain-specific rules from gpt-4.1-mini,
  │    applied by gpt-4o-mini)
  │  → Show results: "35 targets from 100 companies (35% rate)"
  │
  ▼
MCP: EXPLORATION (auto after classify)
  │  → Enrich top 5 NEW targets (5 credits)
  │  → Discover more keywords → update taxonomy
  │  → "Optimized filters found 40% more relevant companies. Re-search?"
  │
  ├─ IF user says yes → re-search with optimized filters (iteration 2)
  ├─ IF user says no → proceed to campaign
  │
  ▼
MCP: CAMPAIGN CREATION
  │  → Generate sequence (gpt-4o-mini + project knowledge)
  │  → Show preview → user approves
  │  → Push to SmartLead (DRAFT)
  │  → Upload contacts with segments + normalized names
  │  → Auto-send test email to user
  │  → "Check your inbox at {email}. Approve to launch."
  │
  ├─ User: "activate"
  │
  ▼
MCP: LAUNCH
  │  → Activate campaign (DRAFT → ACTIVE)
  │  → Enable reply monitoring
  │  → "Campaign active. Reply monitoring ON.
  │    SmartLead: [link] | CRM: [link] | Pipeline: [link]"
```

---

## Critical Rules

1. **ONE question at a time** — never dump multiple questions. Ask, get answer, proceed.
2. **Never gather without offer context** — GPT will confuse clients with competitors.
3. **Never spend Apollo credits without user confirmation** — show filter preview + cost first.
4. **Exploration runs AUTOMATICALLY after Checkpoint 2** — don't wait for user to call tam_explore.
5. **File processing boundary**: <2K tokens = MCP handles it. >2K tokens = user's agent must summarize.
6. **Campaign pre-push checklist**: sequence approved? email accounts selected? contacts uploaded? ALL must be true.
7. **Every response includes links** — pipeline page, CRM, SmartLead campaign, wherever relevant.
8. **Credits tracked in every response** — spent, remaining, next step cost.
9. **Target count configurable** — default 100 contacts (34 companies × 3). User can set any number.
10. **Roles configurable** — default inferred from offer, user can override anytime.
11. **Continue/scale** — user says "find more" → resume from last page, show cost for next batch.

---

## User Control Flows

### Flow: Set Target Count
```
User: "I want 1000 contacts"
MCP (A8): target_count=1000, contacts_per_company=3 → 334 companies needed
           at 35% rate → 954 from Apollo → 10 pages = 10 credits ($0.10)
MCP → User: "For 1000 contacts: 10 credits ($0.10) + 5 enrichment ($0.05).
             Total: $0.15. Proceed?"
```

### Flow: Continue Gathering
```
User: "find more" / "I need more contacts" / "continue"
MCP: Detects existing run #249 with 102 contacts from 34 targets
MCP (A8): Current page=4, next batch=pages 5-8 = 4 credits
MCP → User: "Current: 102 contacts. Next 4 pages: 4 credits ($0.04).
             Estimated: +35 targets → +105 contacts. Total ~207.
             Same filters? Or adjust?"
User: "same, go ahead"
→ tam_gather(reuse_run_id=249, page_offset=5)
```

### Flow: Change Roles
```
User: "change roles to VP Marketing and CMO"
MCP (A7): Maps → person_titles=["VP Marketing", "CMO", "Head of Marketing"]
                  person_seniorities=["vp", "director", "c_suite"]
MCP → User: "Updated roles. Will apply to next people search.
             Current 34 target companies × 3 contacts = 102 contacts.
             People search is FREE. Want me to re-gather contacts with new roles?"
User: "yes"
→ Re-run people search on existing targets with new filters
```

### Flow: Change Contacts Per Company
```
User: "5 contacts per company instead of 3"
MCP: contacts_per_company=5
MCP → User: "Updated: 5 per company. 34 targets × 5 = 170 contacts (was 102).
             People search is FREE."
```

### Flow: Provide Sequence Approach
```
User: "use this approach for emails: [paste or file path]"
  → If file: User's Opus reads file, extracts approach
  → If paste: MCP stores directly
MCP: Stores in ProjectKnowledge(category="sequence_approach")
MCP → User: "Saved your sequence approach. It'll be used for email generation.
             Key elements: [tone, structure, CTA style extracted]."

Later, when smartlead_generate_sequence runs:
  → Reads sequence_approach from ProjectKnowledge
  → Generates emails following the user's style
```

### Flow: Change Filters
```
User: "also include 201-500 size" / "add London to locations"
MCP: Updates filters, re-probes Apollo
MCP → User: "Updated filters:
             Size: 11-50, 51-200, 201-500 (added 201-500)
             Apollo total: 5,230 (was 3,864)
             Cost for 100 contacts: 2 credits ($0.02). Proceed?"
```

### Flow: Change KPIs
```
User: "I want at least 50 targets, not 30"
MCP: min_targets=50
MCP → User: "Updated: minimum 50 targets.
             Current run has 34. Need 16 more.
             Next 2 pages = 2 credits. Shall I continue?"
```

---

## Edge Cases Handled

| Case | Agent | Response |
|------|-------|----------|
| User says "find more" with no run | MCP | "No pipeline running. Start gathering first: tell me the segment." |
| User changes roles after campaign created | MCP | "Campaign already created with previous roles. Create a new campaign?" |
| User provides file >2K tokens | User's Opus | Opus reads, extracts, calls MCP tools with structured data |
| User wants different roles per campaign | MCP | Stores per-run people_filters, each campaign can have different roles |
| User asks cost mid-pipeline | MCP | "Credits spent so far: 6. Estimated remaining: 5. Total: $0.11." |
| User cancels mid-gathering | MCP | "Pipeline paused. Resume anytime with 'continue gathering'." |
| 0 targets found | MCP | "No targets found with these filters. Suggestions: broaden keywords, expand size range, try different segment." |
| Target rate <10% | MCP | "Only 3 targets from 100 companies (3%). Filters may be too broad. Want to explore to find better keywords?" |
| Apollo returns 0 companies | MCP | "No companies in Apollo matching these filters. Check: keywords too specific? Location too narrow? Size too restrictive?" |
| User asks about credits/cost | MCP | Shows account page link + current run costs |

---

## Updated Agent Registry

| Agent | Model | Task | Added |
|-------|-------|------|-------|
| A0 | gpt-4o-mini | Intent router | v1 |
| A1 | gpt-4o-mini | Industry picker | v1 |
| A2 | gpt-4.1-mini | Keyword picker + embedding pre-filter | v1 |
| A3 | gpt-4o-mini | Size inferrer from offer | v1 |
| A4 | regex | Location extractor | v1 |
| A5 | gpt-4o-mini (tuned prompt) | Company classifier | v1 |
| A6 | gpt-4.1-mini | Filter optimizer (post-enrichment) | v1 |
| **A7** | **gpt-4o-mini** | **People filter mapper (roles, titles, seniority)** | **v2** |
| **A8** | **none (math)** | **Cost estimator (credits, pages, dollars)** | **v2** |
| U1 | Claude Opus | File processor (user side) | v1 |
| U2 | Claude Opus | Quality reviewer / target selector (user side) | v1 |
