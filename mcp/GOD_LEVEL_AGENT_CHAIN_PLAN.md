# God-Level MCP Agent Chain Plan

**Source**: exploration.md, requirements_source.md, EXPLORATION_SYSTEM_PLAN.md, audit29_03.md, Pavel's real usage bugs
**Goal**: Every user query → maximum target companies, zero confusion, full transparency

---

## Real User Bugs (Pavel.l@getsally.io — 2026-03-30)

These are REAL bugs from the first external user. Every one MUST be fixed:

### Bug 2: MCP doesn't confirm filters before gathering
**What happened**: Wrote "gather iGaming technology providers" → MCP immediately ran tam_gather × 2 pipelines without showing filters or asking confirmation.
**Required**: Before gathering, MCP MUST say: "I'll search with these filters: keywords=[...], industries=[...], size=[...], geo=[...]. OK?" and wait for approval.
**Root cause**: `parse_gathering_intent` → `tam_gather` happens without a confirmation step. The agent (Claude/Cursor) decides to call tam_gather directly.

### Bug 5 (CRITICAL): Emulators not implemented
**What happened**: `apollo.companies.emulator`, `apollo.people.emulator`, `clay.companies.emulator` return None/0 results silently.
**Required**: Remove emulator source types from MCP entirely. Only working sources: `apollo.companies.api` (paid), `csv.companies.manual`, `google_sheets.companies.manual`, `google_drive.companies.manual`, `manual.companies.manual`.
**Action**: Remove emulator adapter references. Don't even list them.

### Bug 6: No Apollo credit tracking shown
**What happened**: tam_gather via Apollo API found 502 companies but didn't show: credits spent, credits remaining, cost of next step.
**Required**: Every gathering response MUST include: `credits_spent`, `credits_remaining`, `estimated_next_step_cost`. Account page must show credit usage.

### Bug 10: No Apify field in Setup
**Fixed in this session**: Apify Proxy added to Setup page.

### Bug 11: MCP confused offer with target
**What happened**: User said "gather iGaming technology providers" for Mifort project. MCP thought Mifort IS an iGaming company (confused the user's offer with the user's target market).
**Required**: MANDATORY step before any gathering — understand the user's offer. Ask "What's your website?" → scrape → extract offer. Then classify: who is the CLIENT (target) vs who is the COMPETITOR. Without this, GPT will confuse clients with competitors.

---

## The Agent Chain — Complete Flow

```
USER MESSAGE
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  STEP 0: OFFER VERIFICATION (mandatory, one-time)    │
│                                                       │
│  IF project has NO target_segments (offer unknown):   │
│    → Ask: "What's your company website?"              │
│    → Scrape website, extract: what they sell, to whom │
│    → Show user: "I understand you sell [X] to [Y].    │
│      Is this correct?"                                │
│    → Wait for confirmation                            │
│    → Store in project.target_segments                 │
│                                                       │
│  IF project HAS target_segments:                      │
│    → Skip (already known)                             │
│                                                       │
│  WHY: Without knowing the offer, GPT will confuse     │
│  clients with competitors (Bug 11)                    │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  STEP 1: INTENT SPLITTER                             │
│  Model: gpt-4o-mini                                  │
│                                                       │
│  Input: user message + offer context                  │
│  Output: [{segment, geo, size_hint}]                  │
│                                                       │
│  "Gather IT consulting in Miami and                   │
│   video production in London"                         │
│  → [{segment:"IT consulting", geo:"Miami"},           │
│     {segment:"video production", geo:"London"}]       │
│                                                       │
│  Single segment = single pipeline                     │
│  Multiple segments = ask: "I see 2 segments.          │
│  Want separate pipelines or one?"                     │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼ (per segment)
┌─────────────────────────────────────────────────────┐
│  STEP 2: FILTER MAPPING                              │
│                                                       │
│  STEP 2A: EMBEDDING PRE-FILTER (no GPT)              │
│  - Embed user query via OpenAI text-embedding-3-small │
│  - Compare against apollo_taxonomy keyword embeddings │
│  - Take top 30-50 nearest by cosine similarity        │
│  - Industries: always send full list (112 items)      │
│                                                       │
│  STEP 2B: GPT FILTER MAPPER (gpt-4o-mini)            │
│  - Input: segment query + offer text +                │
│    INDUSTRY MAP (112) + KEYWORD SHORTLIST (30-50) +   │
│    EMPLOYEE RANGES (8)                                │
│  - Output: {industries, keywords, unverified_keywords,│
│    employee_ranges}                                   │
│  - CONSTRAINT: GPT selects FROM lists, never invents  │
│    (except max 2 unverified keywords for cold start)  │
│                                                       │
│  STEP 2C: LOCATION EXTRACTOR (regex/rules, no GPT)   │
│  - "in Miami" → ["Miami"]                             │
│  - "UAE and Saudi" → ["UAE", "Saudi Arabia"]          │
│                                                       │
│  STEP 2D: FILTER ASSEMBLER (no GPT)                  │
│  - Combine: keyword_tags = industries + keywords      │
│  - Validate: ≥1 industry, location non-empty          │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  STEP 3: USER CONFIRMATION (Bug 2 fix)               │
│                                                       │
│  SHOW the user assembled filters BEFORE searching:    │
│                                                       │
│  "I'll search Apollo with these filters:              │
│   Keywords: [IT services, consulting, ...]            │
│   Industries: [information technology, ...]           │
│   Location: Miami, FL                                 │
│   Size: 51-200 employees                             │
│   Estimated cost: 1 Apollo credit                     │
│   Expected results: ~2,000 companies                  │
│                                                       │
│   Proceed?"                                           │
│                                                       │
│  User says yes → proceed                              │
│  User says "also add London" → adjust, re-confirm     │
│  User says "too broad, only 51-200" → adjust          │
│                                                       │
│  NEVER auto-launch gathering without confirmation.    │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  STEP 4: EXPLORATION PHASE (Iteration 1)             │
│                                                       │
│  4A: APOLLO SEARCH (1 credit, 25 companies)           │
│  - Log: exact filters, total_available, results       │
│  - SHOW USER: "Found {N} companies, using 1 credit.   │
│    Credits remaining: {R}"  (Bug 6 fix)               │
│                                                       │
│  4B: SCRAPE TOP 15 (free, Apify proxy)                │
│  - httpx + residential proxy                          │
│  - BeautifulSoup text extraction                      │
│                                                       │
│  4C: CLASSIFY TARGETS (gpt-4o-mini, via negativa)     │
│  - v9 prompt with OFFER CONTEXT (Bug 11 fix)          │
│  - Prompt includes: "User sells [X]. Companies that   │
│    would BUY [X] are targets. Companies that SELL     │
│    similar things are COMPETITORS, not targets."       │
│  - Output: X/15 targets, target rate                  │
│  - Label segments (not just target/not-target)        │
│                                                       │
│  4D: ENRICH TOP 5 TARGETS (5 credits)                 │
│  - Extract keyword_tags, industry, sic_codes           │
│  - UPSERT into apollo_taxonomy (shared map grows)     │
│  - SHOW USER: "Enriched 5 targets. 5 credits used.   │
│    Credits remaining: {R}"                             │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  STEP 5: PROMPT OPTIMIZATION LOOP                    │
│                                                       │
│  Opus (Claude Code agent) reviews classification:     │
│  - Looks at each target: is it REALLY a buyer?        │
│  - Looks at each rejection: was it correctly excluded?│
│  - Adjusts GPT prompt until ≥90% accuracy             │
│  - Loop: classify → opus review → adjust → repeat     │
│  - Max 3 iterations, then proceed                     │
│                                                       │
│  This is the "MCP ALWAYS REFINE ITSELF" requirement.  │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  STEP 6: FILTER OPTIMIZATION                         │
│                                                       │
│  Use new keywords from enrichment to optimize:        │
│  - Original keyword_tags + new relevant ones           │
│  - Remove irrelevant ones (via negativa)              │
│  - Log: original vs optimized filters                 │
│                                                       │
│  SHOW USER: "Optimized filters found 40% more         │
│  relevant companies. Proceed to scale?"               │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  STEP 7: SCALE PHASE (Iteration 2)                   │
│                                                       │
│  Apollo search with optimized filters, multiple pages │
│  Until ≥30 target companies found (= ≥100 contacts)  │
│  Cost: 1-4 credits per page                           │
│                                                       │
│  Scrape all → classify all → targets confirmed        │
│                                                       │
│  SHOW USER: "{N} target companies from {M} total.     │
│  Target rate: {R}%. Credits used: {C}.                │
│  View pipeline: [link]"                               │
│                                                       │
│  → CHECKPOINT 2: User reviews targets                 │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  STEP 8: PEOPLE ENRICHMENT                           │
│                                                       │
│  Apollo people search (FREE for emulator, or API)     │
│  3 contacts per target company, C-level default       │
│  User can customize: "I want HR directors"            │
│                                                       │
│  → CHECKPOINT 3: FindyMail cost approval              │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  STEP 9: CAMPAIGN CREATION                           │
│                                                       │
│  9A: CHECK DESTINATION (M1)                           │
│  - If both SmartLead + GetSales → ask which            │
│  - If only one → use it                               │
│                                                       │
│  9B: EMAIL ACCOUNTS (M5)                              │
│  - "Which email accounts? Here are yours: [list]"     │
│  - Wait for selection                                 │
│                                                       │
│  9C: SEQUENCE GENERATION                              │
│  - gpt-4o-mini using project knowledge + patterns     │
│  - Show preview, ask for approval                     │
│  - User can edit subjects, body, timing               │
│                                                       │
│  9D: PUSH TO PLATFORM (DRAFT)                         │
│  - SmartLead or GetSales push                         │
│  - Settings: reference 3070919 (no tracking,          │
│    plain text, stop on reply, 9-18 contact TZ)         │
│  - Upload contacts with segments + normalized names   │
│  - AUTO-SEND test email to user                       │
│                                                       │
│  9E: "Check your inbox at {email}. Approve to launch."│
│  - User provides feedback or says activate             │
│  - activate_campaign → ACTIVE + monitoring ON         │
│  - "Reply monitoring enabled. Want Telegram notifs?"  │
└─────────────────────────────────────────────────────┘
```

---

## Available Sources (cleaned — emulators REMOVED per Bug 5)

| source_type | Description | Cost |
|-------------|-------------|------|
| `apollo.companies.api` | Apollo org search API | 1 credit/page |
| `csv.companies.manual` | CSV file upload | Free |
| `google_sheets.companies.manual` | Google Sheet import | Free |
| `google_drive.companies.manual` | Google Drive folder import | Free |
| `manual.companies.manual` | Direct domain list | Free |

**REMOVED**: `apollo.companies.emulator`, `apollo.people.emulator`, `clay.companies.emulator` — these were never implemented (Bug 5). Don't list them, don't reference them.

---

## Credit Transparency (Bug 6 fix)

Every tool response that uses Apollo credits MUST include:

```json
{
  "credits_spent": 1,
  "credits_remaining": 487,
  "estimated_next_step_cost": 5,
  "cost_breakdown": "Search: 1 credit | Next: Enrichment of 5 targets = 5 credits"
}
```

Account page must show: total credits used, by date range, by project, by pipeline.

---

## Offer Verification Gate (Bug 11 fix)

Before ANY gathering or analysis, the system MUST know:
1. **What the user sells** (their offer)
2. **Who the user sells TO** (their target market)

This is stored in `project.target_segments`. If empty:
- Ask: "What's your company website?" or "What do you sell?"
- Scrape website → extract offer
- Show user: "I understand you sell [X] to [Y]. Correct?"
- Store confirmed understanding

In the GPT analysis prompt, ALWAYS include:
```
CONTEXT: The user sells {offer}.
TARGET = companies that would BUY {offer}.
COMPETITOR = companies that also sell {offer} or similar.
NEVER classify competitors as targets.
```

---

## apollo_taxonomy Map — Self-Learning System

### How it grows:
1. **Every enrichment** → extract `keyword_tags[]`, `industry` → UPSERT into apollo_taxonomy
2. **Every search** → log which keywords produced results → update `apollo_result_count`
3. **Cross-user benefit** → user A enriches "IT consulting" companies → user B gets better keyword suggestions for similar queries

### Cold start (new segment with 0 keyword matches):
1. Use industry names only (always work, guaranteed results)
2. GPT suggests up to 2 "unverified" keywords (flagged)
3. Iteration 1 enrichment reveals real keywords → map populated
4. Iteration 2 uses real keywords → better results

---

## Multi-Source Pipeline (Tests 09-11)

When user provides CSV/Sheet/Drive:
1. Import companies → dedup against existing in project
2. Blacklist check (project-scoped)
3. User can add to EXISTING pipeline or create NEW one
4. Cross-source dedup: CSV ∩ Sheet ∩ Drive → only unique companies kept
5. Each import = new iteration in the same pipeline (if user chose "add to existing")

---

## Session Continuity

When user reconnects with same MCP key:
1. `get_context` returns: active project, pending checkpoints, draft campaigns
2. System auto-resumes: "You have a pending checkpoint for [project]. Approve or reject?"
3. No re-login, no re-selecting project (auto-set if 1 project)

---

## Testing Strategy

**ONLY real MCP SSE tests.** No REST mocks.

```bash
# Launch fresh Claude session connected to MCP
echo "test prompt" | claude --print --dangerously-skip-permissions
```

Each test:
1. Login as test user
2. Configure integrations
3. Run full conversation flow
4. Verify EVERY step's response
5. Write results to `tests/tmp/{timestamp}_{test_name}.txt`
6. Verify UI state (conversations page shows all tool calls)

---

## Implementation Priority

### P0 — Blocking real users NOW:
1. **Bug 2**: Add confirmation step before gathering (filter preview)
2. **Bug 5**: Remove emulator sources from tools list and adapters
3. **Bug 6**: Add credit tracking to every Apollo response
4. **Bug 11**: Mandatory offer verification before analysis

### P1 — Core exploration system:
5. apollo_taxonomy table + embedding infrastructure
6. Filter mapper with embedding pre-filter + GPT selection
7. Exploration → enrichment → filter optimization loop
8. Credit budget enforcement (user-configurable max per pipeline)

### P2 — Scale + campaign:
9. Multi-page gathering until ≥30 targets
10. Prompt optimization loop (Opus review)
11. Campaign creation with full SmartLead push
12. Reply monitoring auto-enable

### P3 — Polish:
13. Custom processing steps (add/remove columns)
14. Iteration tracking with historical filter/prompt comparison
15. Performance metrics (Account page credit breakdown)
