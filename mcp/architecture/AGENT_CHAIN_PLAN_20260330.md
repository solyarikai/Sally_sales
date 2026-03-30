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

## Two Modes of Operation

### Mode A: Step-by-step (casual user)

User provides info one piece at a time. MCP asks ONE question, processes, asks next.

```
User: "I want to gather IT consulting companies"
MCP:  "What's your company website? I need to understand your offer first."
User: "easystaff.io"
MCP:  [scrapes, extracts offer] "Got it — EasyStaff does payroll & contractor
       management. Where should we look? Which geo?"
User: "Miami, 50-200 employees"
MCP:  [maps filters] "Here's what I'll search:
       Keywords: it consulting, management consulting, ...
       Location: Miami
       Size: 51-200
       Total available: 3,908 companies
       Cost: 4 credits (≈35 targets) or 157 credits (all 3,908, ≈1,368 targets)
       Proceed with default (4 credits)?"
User: "yes"
MCP:  [gathers, scrapes, classifies, shows results]
```

### Mode B: Brief mode (power user)

User provides a strategy document (like cases/IGAMING_PROVIDERS_BRIEF.md) with everything: offer, segment, examples, exclusions, geo, size.

```
User: "Use this file: cases/IGAMING_PROVIDERS_BRIEF.md — launch everything"
```

**Who processes the file?** The user's agent (Opus in Claude Code) — NOT MCP's gpt-4o-mini. Opus reads the 160-line file, extracts structured data, and calls MCP tools with it.

**Boundary rule**: If data fits in <2000 tokens → MCP's GPT-4o-mini can process it. If >2000 tokens → user's agent (Opus) must summarize and pass structured data to MCP.

**What Opus extracts from the brief and passes to MCP:**

```json
{
  "project_name": "Mifort-iGaming",
  "website": "mifort.org",
  "offer_summary": "IT outsourcing for iGaming. Web/Mobile/ML dev teams. Anti-fraud cases.",
  "segment": "iGaming technology providers",
  "geo": ["Malta", "Gibraltar", "Cyprus", "UK", "Estonia", "Armenia", "Israel"],
  "size": ["11,50", "51,200", "201,500", "501,1000"],
  "example_domains": ["softswiss.com", "pragmaticplay.com", "betconstruct.com", "digitain.com", "evoplay.games"],
  "exclusion_rules": [
    "Casino operators (run casinos, don't build tech)",
    "Affiliate/SEO review sites",
    "Land-based only / lottery",
    "IT outsourcing competitors",
    "Regulators and industry bodies"
  ],
  "email_accounts": "from previous Mifort campaigns",
  "destination": "smartlead"
}
```

**MCP receives this and auto-runs**:
1. create_project → scrape mifort.org
2. tam_enrich_from_examples (5 domains) → discover real Apollo keywords
3. tam_gather with discovered filters → show preview → user confirms
4. Full pipeline: blacklist → scrape → classify → explore → scale
5. Sequence generation → push to SmartLead → test email

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
