# Document-Based Pipeline Flow — Implementation & Testing Plan

## What This Is

User provides a strategy document filename in MCP chat. System extracts everything, asks clarifying questions, launches pipeline(s). Silently skips what can't be automated.

## The Flow

```
User: "outreach-plan-fintech.md"

1. Claude Code reads file from disk
2. GPT extracts: offer, roles, filters, sequence, campaign settings
3. Silently skips what can't be automated
4. Agent asks: "I found 6 segments. Launch as 1 campaign or 6 separate?"
5. User: "one campaign"
6. System merges all 6 segments into ONE pipeline with combined filters
7. Classification prompt includes ALL 6 segments as possible categories
8. Standard flow: blacklist → accounts → pipeline → SmartLead
```

## Pre-Testing Implementation Requirements

### MUST implement before any testing begins:

**1. People enrichment retry logic (apollo_service.py enrich_by_domain)**
```
Current: top 3 candidates → bulk_match → keep verified → done (even if 0-1 verified)
New: top 3 → bulk_match → if <3 verified → retry with next candidates

Retry rules:
  - Go back to full candidate list (25 from seniority search)
  - Pick NEXT candidates that MATCH target_roles from document
  - Priority: exact role match > same seniority > lower seniority with role match
  - NEVER enrich someone with no role relevance (no random directors)
  - Repeat until 3 verified OR all role-matching candidates exhausted
  - Max 3 retry rounds (max 12 credits per company worst case)

Example (fintech doc target roles: VP Sales, CRO, Head of Growth, CMO, CEO):
  Round 1: VP Sales ✓, CRO ✗ (no email), CEO ✗ → 1 verified
  Round 2: pick Head of Growth, CMO, Co-founder → bulk_match → 2 verified
  Total: 3 verified contacts from this company ✓
```

**2. SmartLead accounts pre-cache on key connect**
```
When user connects SmartLead API key (Setup page or configure_integration):
  → Immediately paginate ALL accounts (2400+)
  → Cache in DB table: smartlead_accounts_cache (user_id, account_id, from_email, from_name)
  → Future lookups are instant (no 30s API pagination)

When user says "all with rinat in name":
  → Query local cache, not SmartLead API
  → Instant response

Tests:
  1. Connect SmartLead key → verify cache populated (count matches API)
  2. "all with rinat" → verify finds correct accounts from cache
  3. "all with petr" → verify finds different accounts from cache
```

**3. Pipeline V2 fixes — VERIFY each against current code + pipeline_spec.md, fix only what's broken**
```
These were identified as bugs earlier. Some may already be fixed.
Before testing: check each one against actual code. Fix only what fails.

VERIFY FIX 2: Single Pipeline Run
  Was: preview creates run #441, confirm creates #442 (duplicate)
  Check: run tam_gather preview + confirm, count GatheringRuns in DB
  If still 2 runs → fix. If 1 run → mark verified.

VERIFY FIX 3: Probe = 1 page, reused on confirm
  Was: probe fetches 100 companies but confirm re-fetches from page 1
  Check: run tam_gather preview, check probe companies in DB. 
  Then confirm, check page_offset starts at 2.
  If probe wasted → fix. If reused → mark verified.

VERIFY FIX 4: Tool Schema Fixes
  4.1 create_project: does it work without "name"? Test it.
  4.2 confirm_offer: does it accept string "424"? Test it.
  4.3 align_email_accounts: does it accept project_id without run_id? Test it.
  4.4 list_email_accounts: does it dump 247K chars or return count+link? Test it.
  Fix only what fails.

VERIFY + IMPLEMENT FIX 5: Email Accounts UX (full spec below)
  - Does list_email_accounts return count + link (not all accounts)?
  - Is pre-cache implemented?
  - Is account lists UI built?
  - See "Email Accounts Subpage UX" section below for full design.

VERIFY FIX 7: Total Company Count
  - Open pipeline page, check if it shows total or page size.
  - If page size only → fix.

Each verification logged in document_based_flow_results.md with:
  - What was checked
  - Current state (fixed / still broken)
  - What was done (if anything)
```

**4. Document extraction service (document_extractor.py)**
Must be implemented before model comparison test can run.

**5. Dynamic classification system (NEVER hardcode ANYTHING)**
```
The ENTIRE classification system is dynamic — works for ANY document:
  - outreach-plan-fintech.md → 8 fintech segments
  - pavel_example_of_target_companies_description.md → whatever segments it has
  - "fashion brands in Italy" → 1 segment

THREE dynamic components:

A. Document Extractor (GPT agent #1):
   Reads ANY document → extracts segments, roles, filters.
   No hardcoded segment names. Output is purely from document context.

B. Classification Prompt Generator (GPT agent #2 — NEW):
   Takes extracted segments + offer text → generates the PERFECT
   classification prompt for the streaming pipeline.
   Tests multiple prompt variations, picks highest accuracy.
   This agent runs ONCE per project, before pipeline starts.
   Output stored on project.offer_summary.classification_prompt

C. Streaming Pipeline Classifier:
   Reads classification_prompt from project (set by agent #2).
   NEVER has hardcoded segments. Always dynamic from project context.
   If no custom prompt → falls back to generic:
     "Classify if this company is a target customer.
      Offer: {offer_text}
      Return JSON: {is_target, segment, reasoning}"

The system handles ANY document because:
  - Agent #1 extracts whatever segments exist (0, 1, 6, 20)
  - Agent #2 creates the optimal prompt for THOSE specific segments
  - Pipeline uses that prompt — no hardcoding anywhere

Test on multiple documents to verify generality:
  - outreach-plan-fintech.md (8 segments, B2B fintech)
  - pavel_example_of_target_companies_description.md (different domain)
  - simple "fashion brands in Italy" (1 implicit segment)
```

### API Keys for Testing
```
SmartLead: eaa086b6-b7c0-4b2f-a6e9-b183c81122d5_638f7e5
Apollo: 9yIx2mZegixXHeDf6mWVqA
OpenAI: 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
Apify: apify_proxy_zZ12PNY7illL44MXT8Cf3vKetkI5I62Oupn2
```

---

## What GPT Extracts

| Data | Value |
|------|-------|
| Offer | "Sally's done-for-you lead gen — qualified appointments" |
| ICP | B2B fintech, 20-500 employees, Series A-D |
| Geography | US, UK, EU, UAE, Singapore |
| Employee range | 20-500 |
| Primary roles | VP Sales, Head of Sales, CRO |
| Secondary roles | Head of Growth, VP Marketing, CMO |
| Tertiary roles | CEO, Co-founder |
| Sequence A | "Pipeline Pain" — 4 emails (day 1, 3, 7, 14) |
| Campaign settings | No tracking, stop on reply, 35/mailbox/day |
| 6 segments | Payments, Lending, BaaS, RegTech, WealthTech, Crypto |

## One Campaign with 6-Segment Classification

When user says "one campaign":
- Apollo filters: COMBINED keywords + industries from all 6 segments (OR logic — separate API calls, never combined)
- Classification prompt: "Is this company a target? If yes, classify into one of: PAYMENTS, LENDING, BAAS, REGTECH, WEALTHTECH, CRYPTO"
- Each company gets a segment label
- All go into ONE SmartLead campaign with Sequence A
- Segment label stored for future personalization

## Apollo Funding Filter Testing

### What to Test
The document says "Series A through Series D" and "raised funding in last 90 days".
Apollo has `organization_latest_funding_stage_cd` filter.

### Funding Filter as PRIORITIZATION Layer

Funding filter is NOT a hard requirement — it's a prioritization layer.
Funded companies are higher quality (actively scaling), so search them FIRST.
If funding pool exhausts before KPI, fall back to non-funded companies.

```
Strategy cascade when document mentions funding (e.g. "Series A-D"):

Level 0 (highest priority): Keywords/Industries + Funding filter
  - Apollo: q_organization_keyword_tags=["fintech","payments",...] 
            + organization_latest_funding_stage_cd=["series_a","series_b","series_c","series_d"]
  - NEVER combine industry_tag_ids + keywords in same call (AND kills results)
  - But DO combine keywords + funding_stage (they work together)
  - Result: ~540 companies (tested). High quality, funded, scaling.
  - Process: scrape → classify → people until KPI met or exhausted

Level 1 (if Level 0 exhausted): Keywords/Industries WITHOUT funding filter
  - Same keywords, same locations, same size — just drop funding filter
  - Opens up 17,000+ companies (the full fintech pool)
  - Lower priority (includes bootstrapped, stagnant companies)
  - Continue until KPI met

Level 2+: Standard exhaustion cascade (per pipeline_spec.md)
  - Strategy switching, keyword regeneration, etc.
```

### Test Results (Phase 2)
```
Without funding filter: 17,318 companies
With Series A-D filter: 540 companies (3%)
Recommendation: USE funding as Level 0 priority, fall back to no-funding at Level 1
```

## GPT Model Testing Plan

### Agent Being Tested
The **document extraction agent** — reads full strategy doc, outputs structured JSON.

### 7 Models to Test

| Model | Family |
|-------|--------|
| gpt-4o-mini | GPT-4o |
| gpt-4.1-mini | GPT-4.1 |
| gpt-4.1-nano | GPT-4.1 |
| gpt-5-nano | GPT-5.0 |
| gpt-5-mini | GPT-5.0 |
| gpt-5.4-nano | GPT-5.4 |
| gpt-5.4-mini | GPT-5.4 |

### Scoring (13 points)

| Field | Points |
|-------|--------|
| Offer extracted correctly | 1 |
| Target audience correct | 1 |
| Roles: all 3 tiers correct | 3 |
| Keywords: 10+ fintech-relevant | 1 |
| Locations: 5+ countries | 1 |
| Employee range correct | 1 |
| Sequence A: all 4 emails matching document's exact subjects + bodies | 4 |
| Campaign settings correct | 1 |
| **Total** | **13** |

### Test Method
1. Send full document to each model with extraction prompt
2. Parse JSON response
3. Score against ground truth
4. Log: model, tokens, cost, time, score per field
5. Save to `mcp/tests/results/doc_extract_{MODEL}_{TIMESTAMP}.json`

## Verification — Opus Reviews ALL Results

**CRITICAL: Every test result is verified by Claude Opus (this agent).**

After each pipeline run, Opus reviews ALL gathered data by comparing against the original document:

### Companies verification (all 100+)
```
Split into batches of 25. Launch parallel agents.
Each agent checks: is this company a real B2B fintech?
  - Payments/Lending/BaaS/RegTech/WealthTech/Crypto?
  - 20-500 employees? Series A-D?
  - SEGMENT LABEL: every target company MUST have one of exactly 6 labels:
    PAYMENTS, LENDING, BAAS, REGTECH, WEALTHTECH, CRYPTO
  - Is the label CORRECT for what this company actually does?
    (e.g. Stripe → PAYMENTS not LENDING, Plaid → BAAS not REGTECH)
Score: % of companies that are REAL targets per document ICP.
Segment score: % of companies with CORRECT segment label.
```

### People verification (all 100+)
```
Split into batches of 25. Launch parallel agents.
Each agent checks: is this person a real decision-maker?
  - VP Sales / CRO / Head of Growth / CMO / CEO?
  - At a real fintech company?
  - Verified email?
Score: % of people matching document's persona criteria.
```

### Sequence verification
```
Compare extracted sequence against document word-by-word:
  - Subject lines match?
  - Email bodies match (allow minor formatting differences)?
  - Day spacing correct (1, 3, 7, 14)?
  - Personalization variables preserved ({{company}}, {{firstName}})?
Score: exact match % per email.
```

### Campaign settings verification
```
  - No tracking? ✓/✗
  - Stop on reply? ✓/✗
  - Plain text? ✓/✗
  - Daily limit 35/mailbox? ✓/✗
  - Rinat accounts connected? ✓/✗
```

### Final Score Per Test Run
```
Companies accuracy: X% (N/100 real targets)
People accuracy: X% (N/100 correct roles at target companies)
Sequence accuracy: X% (N/4 emails matching document)
Settings accuracy: X/5 correct settings
Total: weighted average
```

## Testing Strategy — Step by Step

### Phase 1: Model Comparison (extraction accuracy)
```
For each of 7 models:
  1. Extract from outreach-plan-fintech.md
  2. Score against ground truth (13 points)
  3. Log results
  4. Pick winner = highest score, lowest cost
```

### Phase 2: Apollo Funding Filter Test
```
1. Test funding_stage filter on "fintech + payments" segment
2. Check if search response includes funding data
3. Determine: filter only, or also need enrichment?
4. Log results
```

### Phase 3: Payment Providers Segment (first test)
```
Using best model from Phase 1:
  1. Extract filters for "Payments/PSPs" sub-segment
  2. Run pipeline with best Apollo approach (with/without funding filter)
  3. Measure: time, companies, targets, people, accuracy
  4. Target: 100 people in <5 minutes
  5. Log results
```

### Phase 4: Full E2E — One Campaign, 6 Segments
```
1. Extract from document (best model)
2. Agent asks: "6 segments found. One campaign or separate?"
3. User: "one campaign"
4. Combined Apollo filters (all 6 segments' keywords merged)
5. Classification: each target → one of 6 segment labels
6. Pipeline runs: scrape → classify → people
7. SmartLead campaign with Sequence A + Rinat accounts
8. Verify: 100+ people, correct segment labels, correct roles
```

## Logging & Results Directory

All test results saved to: `mcp/tests/results/`

### File naming convention:
```
doc_extract_{MODEL}_{YYYYMMDD_HHMMSS}.json     — model comparison
apollo_funding_{YYYYMMDD_HHMMSS}.json           — funding filter tests
pipeline_payments_{YYYYMMDD_HHMMSS}.json        — payments segment test
e2e_fintech_{YYYYMMDD_HHMMSS}.json             — full E2E result
issues_{YYYYMMDD_HHMMSS}.md                     — issues found with solutions
```

### What each log contains:
- Timestamp
- Model used
- Input (prompt or filters)
- Output (extracted data or pipeline results)
- Score (if applicable)
- Cost (tokens, credits, USD)
- Time elapsed
- Issues found
- Solutions applied

## Implementation Order

1. **Document extraction service** (`document_extractor.py`)
2. **Model comparison test** — run all 7 models, pick winner
3. **Apollo funding filter test** — does it work for fintech?
4. **Payments segment pipeline test** — full run, measure accuracy
5. **Segment clarification agent** — "one campaign or separate?"
6. **Combined classification prompt** — 6 segments as categories
7. **Full E2E test** — document → one campaign with 6 segments
8. **Extend create_project** — accept document_text param

## Pipeline Integration Test — NOT Step-by-Step, REAL Pipeline

**CRITICAL: Don't test each step separately. Test the REAL pipeline as MCP would trigger it.**

### What This Means
```
1. Hardcode user approvals (blacklist: "no", accounts: "rinat", approve: true)
2. Call the SAME tool endpoints MCP would call, in EXACT order:
   a. create_project(website: "getsally.io", document_text: <content>)
   b. confirm_offer(project_id: X, approved: true)
   c. align_email_accounts(project_id: X, account_filter: "rinat", confirm: true)
   d. tam_gather(project_id: X, ...) — NO confirm_filters
      → PREVIEW: creates pipeline in pending_approval, probes Apollo, returns filters
      → Verify: exactly 1 pipeline created, status=pending_approval
   e. tam_gather(project_id: X, ..., confirm_filters: true)
      → CONFIRM: gathers companies + starts pipeline automatically
      → Verify: same pipeline updated (not a second one created!)
3. Pipeline runs per pipeline_spec.md:
   - Probe 100 companies → scrape starts INSTANTLY
   - Apollo pages 2-10 in parallel while scraping
   - Each scraped site → classify immediately (100 concurrent)
   - Each target → people search immediately (20 concurrent)
   - KPI checked after each person
   - SmartLead push on completion
4. Do NOT manually call scrape/classify/people — pipeline does it all
5. Just poll pipeline_status until completed/insufficient
```

### What to Verify After Pipeline Completes
```
Per pipeline_spec.md requirements:
  - Companies flow through scrape→classify→people (no skipping)
  - Scraping uses Apify proxy (100 concurrent)
  - Classification uses scraped website text (not Apollo industry)
  - Only verified emails kept
  - Strategy cascade works (industry → keywords → regen)
  - 10 consecutive empty = exhausted
  - SmartLead campaign auto-created with contacts + accounts + sequence
```

### ESSENTIAL: Check DB + Logs After EVERY Test
```
After each test run, query DB and verify:
  1. Exactly 1 GatheringRun exists for this project (NO duplicates!)
  2. Run status progressed: pending_approval → running → completed/insufficient
  3. All companies have scraped_text (none skipped scraping)
  4. All classified companies have scraped_text (classified from website, not Apollo)
  5. All extracted contacts have email_verified=true
  6. Campaign linked to run (campaign_id not NULL)
  7. SmartLead campaign created (external_id not NULL)
  8. Credits tracked correctly (pages + people enrichment)
  
Check server logs:
  9. No "session conflict" or "InterfaceError" errors
  10. No "another operation in progress" errors
  11. Pipeline completed without crash (no "failed" status)
  12. Workers received poison pills (clean shutdown)
```

### Compliance Check Against pipeline_spec.md
```
After each test run, verify these pipeline_spec.md rules:
  ✓ Probe companies reused (not re-fetched)
  ✓ Apollo pages parallel with scraping
  ✓ Feed pages as they arrive
  ✓ 100 concurrent scrape, 100 concurrent classify, 20 concurrent people
  ✓ Separate DB session per worker
  ✓ Never combine industry + keywords in same API call
  ✓ Only verified emails in final contacts
  ✓ Pipeline never changes user's location/size filters
  ✓ Classification never uses Apollo industry label
```

---

## Email Accounts Subpage UX — Full Design

### The Problem
- SmartLead has 2400+ email accounts
- `list_email_accounts` dumps all 247K chars into MCP → crashes
- User says "all with rinat" but has to wait 30s for API pagination
- No way to save/reuse account selections across campaigns

### The Solution: Account Lists

**New entity: `EmailAccountList`** — a saved, named selection of accounts.

```
Table: email_account_lists
  id: int (PK)
  user_id: int (FK → mcp_users)
  name: str (e.g. "Rinat TFP accounts", "Petr Crona accounts")
  filter_pattern: str (e.g. "rinat", "petr crona")
  account_ids: JSONB (list of SmartLead account IDs)
  account_count: int
  created_at: datetime
  updated_at: datetime
```

### Where Account Lists Appear in UI

#### 1. Campaigns Page → "Email Accounts" tab/button
```
URL: /campaigns/accounts

Shows:
  - Total accounts: 2,411 (from cache)
  - Search bar: type to filter by name/email
  - Saved Lists section:
    [Rinat TFP] 14 accounts | [Petr Crona] 26 accounts | [+ New List]
  
  Click a list → expands to show all accounts:
    ✉ rinat@thefashionpeopletech.com (Rinat Gabdolla)
    ✉ rinat@thefashionpeoplesolutions.com (Rinat Gabdolla)
    ... 14 accounts

  Click [+ New List] → name it, type filter pattern, save
```

#### 2. Campaign Details Page → Accounts section
```
URL: /campaigns/568

Shows:
  Campaign: The Fashion People — Rinat Campaign
  Status: MCP_DRAFT
  
  Email Accounts: [Rinat TFP] (14 accounts) [View] [Change]
  
  Click [View] → links to /campaigns/accounts?list=rinat-tfp
  Click [Change] → dropdown of saved lists or create new
```

#### 3. MCP Tool: align_email_accounts
```
When user says "all with rinat in name":
  1. Search local cache (instant) → find 14 accounts
  2. Auto-create EmailAccountList: name="rinat", filter="rinat", 14 accounts
  3. Return: "14 accounts matched. View: http://host/campaigns/accounts?list=rinat"
  4. Link is clickable in MCP chat

When user says "use list rinat-tfp":
  1. Look up saved list by name
  2. Return accounts from list (instant)
```

### Pre-Cache Flow (on SmartLead key connect)

```
1. User connects SmartLead API key on Setup page
2. Backend immediately starts background task:
   - Paginate ALL accounts (offset=0, limit=100, repeat until done)
   - Save to: smartlead_accounts_cache table (user_id, account_id, from_email, from_name)
   - Log: "Cached 2,411 accounts in 12s"
3. Future lookups query local cache, not SmartLead API
4. Cache refreshed: daily background job OR on-demand via "Refresh" button
```

### Database Schema

```sql
-- Cache of all SmartLead accounts (populated on key connect)
CREATE TABLE smartlead_accounts_cache (
  id SERIAL PRIMARY KEY,
  user_id INT REFERENCES mcp_users(id),
  account_id INT NOT NULL,           -- SmartLead account ID
  from_email VARCHAR(255) NOT NULL,
  from_name VARCHAR(255),
  cached_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(user_id, account_id)
);

-- Saved account selections (reusable across campaigns)
CREATE TABLE email_account_lists (
  id SERIAL PRIMARY KEY,
  user_id INT REFERENCES mcp_users(id),
  name VARCHAR(255) NOT NULL,
  filter_pattern VARCHAR(255),
  account_ids JSONB NOT NULL,       -- [{id: 123, email: "...", name: "..."}]
  account_count INT DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);
```

### MCP Flow After Implementation

```
User: "all emails with rinat in name"

1. Query smartlead_accounts_cache WHERE from_email ILIKE '%rinat%' OR from_name ILIKE '%rinat%'
2. Found 14 accounts (instant, no API call)
3. Create email_account_lists entry: name="rinat", 14 accounts
4. Return: "14 accounts. View: http://host/campaigns/accounts?list=1"
5. User: "yes" → link list to campaign
```

---

## Results File

All discoveries, issues, and final results written to:
**`mcp/tests/results/document_based_flow_results.md`**

Contents:
- Model comparison winner + scores
- Apollo funding filter test results
- Pipeline run metrics (time, companies, people, credits)
- Opus verification scores (companies %, people %, sequences %)
- Issues found during testing (with timestamps)
- Solutions applied (with timestamps)
- Final recommendation

Referenced from this document (DOCUMENT_BASED_FLOW.md).

---

---

## Definition of Done — CLEAR EXIT CRITERIA

### This task is DONE when ALL of these files exist and meet quality:

#### Files that must exist after completion:

| File | What it contains |
|------|-----------------|
| `mcp/backend/app/services/document_extractor.py` | Document extraction service (best model chosen) |
| `mcp/backend/app/services/apollo_service.py` | Updated with people enrichment retry logic |
| `mcp/backend/app/services/streaming_pipeline.py` | Updated with multi-segment classification |
| `mcp/tests/results/doc_extract_MODEL_TIMESTAMP.json` | 7 files — one per model comparison |
| `mcp/tests/results/model_comparison_summary.json` | Winner model + scores table |
| `mcp/tests/results/apollo_funding_TIMESTAMP.json` | Funding filter test results |
| `mcp/tests/results/e2e_fintech_TIMESTAMP.json` | Full E2E pipeline result |
| `mcp/tests/results/document_based_flow_results.md` | Final report: all discoveries, issues, solutions |
| `mcp/tests/results/verification_companies_TIMESTAMP.json` | Opus review of all 100+ companies |
| `mcp/tests/results/verification_people_TIMESTAMP.json` | Opus review of all 100+ people |
| `mcp/tests/results/verification_sequences_TIMESTAMP.json` | Opus review of sequence vs document |
| `mcp/tests/results/iteration_log.md` | All iterations with timestamps, scores, changes |

#### Quality Targets (iterate until met):

| Metric | Target | Minimum Acceptable | How Measured |
|--------|--------|-------------------|-------------|
| Companies accuracy | 95% real fintech targets | 90% (after 10 iterations) | Opus reviews all 100+ companies against document ICP |
| People accuracy | 95% correct roles at target companies | 90% (after 10 iterations) | Opus reviews all 100+ people against document personas |
| Sequence accuracy | 100% match to document's Sequence A | 95% (minor formatting) | Word-by-word comparison of 4 emails |
| Segment classification | 95% correct segment labels | 90% | Opus checks each company's label vs its actual business |
| Campaign settings | 100% match | 100% (no compromise) | Checklist: tracking, reply-stop, accounts, plain text |
| People per target company | avg 2.5+ (out of 3 max) | avg 2.0 | Retry logic fills 3 slots per company |
| Pipeline completes | No crash, no stuck | Always | Status = completed or insufficient, never running/failed |
| No duplicate pipelines | Exactly 1 GatheringRun | Always | DB check after every run |
| KPI hit | 100+ verified contacts | 80+ (if Apollo exhausted) | Pipeline result total_people |
| **Generality test** | **Works with 3 different documents** | **All 3 pass** | **Run full pipeline with each, all hit quality targets** |

#### Generality Test — MANDATORY before declaring "done":

The system must be dynamic and NOT hardcoded to fintech. Test with ALL three documents:

| # | Document | Domain | What it proves |
|---|----------|--------|---------------|
| 1 | `outreach-plan-fintech.md` | B2B fintech, 8 segments | Multi-segment extraction, industry-based filtering |
| 2 | `pavel_example_of_target_companies_description.md` | Different domain entirely | Classification/roles/filters are dynamic, not fintech-specific |
| 3 | Simple one-liner: "fashion brands in Italy" | Single implicit segment | Works with minimal input, no explicit segments |

**If any document fails → the system is hardcoded, not dynamic. Fix it before shipping.**

All classification prompts, role exclusions, segment labels, and filter strategies must come from the document extraction — never from Python constants.

#### Iteration Protocol:
```
NEVER STOP below 90%. There is NO maximum iteration count.

Phase A: aim for 95% (up to 10 iterations)
  If 95% reached → DONE ✓
  If not reached after 10 iterations → lower target to 90%, continue

Phase B: aim for 90% (UNLIMITED iterations until hit)
  Keep iterating until 90% reached. No cap. No stopping.
  90% is the absolute minimum. Below 90% = task NOT done.

After each iteration:
  1. Run full pipeline
  2. Opus verifies ALL companies (batches of 25, parallel agents)
  3. Opus verifies ALL people (batches of 25, parallel agents)
  4. Opus verifies sequences
  5. Calculate scores
  6. Log to iteration_log.md: timestamp, scores, what changed
  7. If <target%: identify worst category, fix prompt/logic, iterate

Score formula:
  overall = (companies_pct * 0.3) + (people_pct * 0.3) + 
            (sequence_pct * 0.2) + (segments_pct * 0.1) + 
            (settings_pct * 0.1)
```

#### What "iterate" means:
```
Iteration 1: Run with initial prompts/models → score
Iteration 2: Improve worst metric (e.g. fix classification prompt) → re-run → score
Iteration 3: Fix next worst → re-run → score
...continue until target met or 10 iterations exhausted

Each iteration changes EXACTLY ONE thing (scientific method).
Log what changed and the impact on ALL metrics.
```

---

## Reference Data

- **Website**: getsally.io
- **Document**: `mcp/outreach-plan-fintech.md`
- **Email accounts**: all with "rinat" in name (campaign 3070916)
- **Expected**: 1 campaign, 6 segment labels, Sequence A, 100+ people
- **KPI**: default (100 people, 3/company)
- **Time target**: <5 minutes per segment

---

## STUPID MISTAKES — NEVER REPEAT

Hard-learned lessons from the April 2, 2026 testing disaster. Every single one of these wasted 20+ minutes of debugging time that could have been avoided.

### 1. DEPLOYED TO WRONG CONTAINER (leadgen-backend instead of mcp-backend)

**What happened**: Claude deployed code fixes (via negativa classification, EXCLUDE_ROLES filtering) to `leadgen-backend` instead of `mcp-backend`. Then couldn't figure out why nothing changed. Spent ages debugging "why doesn't the fix work" when the fix was sitting in the wrong container entirely.

**Why it was stupid**: The MCP codebase is a SEPARATE application running in `mcp-backend`. It has its OWN code at `/app/app/` inside that container. `leadgen-backend` is the main app — completely unrelated to MCP pipeline execution.

**The rule**:
- MCP code lives in `mcp-backend` container. ALWAYS.
- Deploy with: `docker cp file mcp-backend:/app/...` then `docker restart mcp-backend`
- NEVER touch `leadgen-backend` for MCP work
- If you catch yourself typing `leadgen-backend` during MCP work, STOP

### 2. PATCHED FILES ONE-BY-ONE INSTEAD OF FULL DEPLOY

**What happened**: Instead of doing a proper deploy, Claude was `scp`-ing individual `.py` files to the server, `docker cp`-ing them into the container. This led to mismatched code — some files updated, some not — and broken imports because the server had a different codebase version than local.

**Why it was stupid**: The server code was out of sync with local. Different model locations (`contact.py` not `project.py`), different constructor signatures, missing modules. Patching individual files into a mismatched codebase is guaranteed to break.

**The rule**:
- Full deploy, not file patches: `docker restart mcp-backend` after copying ALL changed files
- If the server code structure differs from local, you need to understand the SERVER's structure first
- `docker exec mcp-backend ls /app/app/` to check what's actually there before deploying

### 3. USED MAIN APP CODE INSTEAD OF MCP TOOLS

**What happened**: Claude tried to import and run main app functions, hack scripts onto the main leadgen-backend, use main app service code — instead of just calling MCP tools through the SSE connection as intended.

**Why it was stupid**: The entire point of MCP is that you test through MCP tools. The pipeline runs inside `mcp-backend`, triggered by MCP tool calls. Running scripts on `leadgen-backend` tests nothing relevant.

**The rule**:
- Test through MCP tools ONLY (create_project, run_full_pipeline, etc.)
- Never import from the main app's codebase for MCP testing
- If an MCP tool doesn't exist for what you need, that's a feature gap to discuss — not a reason to hack around it

### 4. WRONG DATABASE NAME

**What happened**: Tried `psql -U mcp -d mcp` — database "mcp" does not exist. The actual database is `mcp_leadgen`. Also tried ALTER TABLE on the nonexistent database.

**Why it was stupid**: The DATABASE_URL is right there in the container's env vars: `postgresql+asyncpg://mcp:mcp_secret@mcp-postgres:5432/mcp_leadgen`. One `docker exec mcp-backend env | grep -i database` would have shown this.

**The rule**:
- MCP database: `mcp_leadgen` (NOT `mcp`)
- MCP DB user: `mcp` with password `mcp_secret`
- MCP DB container: `mcp-postgres`
- Check env vars first: `docker exec mcp-backend env | grep DATABASE`

### 5. ASSUMED SCHEMA WITHOUT CHECKING

**What happened**: Wrote a test script that assumed `mcp_users` table has a `company_id` column. It doesn't — `company_id` is on the `projects` table. Script crashed with a SQL error.

**Why it was stupid**: Takes 5 seconds to check: `SELECT column_name FROM information_schema.columns WHERE table_name='...'`

**The rule**:
- ALWAYS check actual schema before writing SQL or scripts
- `docker exec mcp-postgres psql -U mcp -d mcp_leadgen -c "SELECT column_name FROM information_schema.columns WHERE table_name='TABLE_NAME'"`
- Never assume column existence from memory or from the main app's schema — MCP has its OWN database with its OWN schema

### 6. HAD TO REVERT DAMAGE TO PRODUCTION leadgen-backend

**What happened**: After deploying wrong files to `leadgen-backend`, had to `git checkout` multiple files on the production server to undo the damage. This is a production system serving real users.

**Why it was stupid**: Could have broken the live production app. The files that were modified (`gathering.py`, `apollo_service.py`, `doc...`) are actively used by the main application.

**The rule**:
- `leadgen-backend` is PRODUCTION. Never deploy experimental MCP code there.
- If you accidentally modify production files, revert IMMEDIATELY with `git checkout -- <files>`
- Triple-check the container name before every `docker cp` or `docker exec`

### 7. MCP SSE SESSION BREAKS ON CONTAINER RESTART

**What happened**: After restarting `mcp-backend` to apply fixes, the MCP SSE connection broke. Log showed: `Received request before initialization was complete`. The MCP tools stopped working mid-test.

**Why it was stupid**: Of course the SSE connection breaks when you restart the server. The client needs to reconnect.

**The rule**:
- After `docker restart mcp-backend`, the SSE session is dead
- Must re-authenticate with `get_context` using a fresh token
- Plan for this: make your fixes, restart ONCE, reconnect, then test

### 8. CONSTRUCTED RAW APOLLO FILTERS INSTEAD OF USING THE PIPELINE'S OWN FILTER SYSTEM

**What happened**: Claude manually constructed `keyword_tags` and raw Apollo API filters in test scripts. The pipeline returned only 2 orgs from Apollo despite 50K+ total. Meanwhile, the previous successful run (iteration 3, run 450) used `filter_strategy: "keywords_first"` with `industry_tag_ids` AND `keywords_selected` — the pipeline's full filter mapper system via `_feed_apollo_pages`.

**Why it was stupid**: The pipeline has a complete filter system that handles pagination, keyword expansion, industry mapping, and all Apollo API quirks. Bypassing it with hand-crafted filters means you get 2 results instead of thousands. The working run's filters were RIGHT THERE in the database — just query them.

**The rule**:
- NEVER construct raw Apollo filters manually — use the pipeline's filter system
- Check what previous successful runs used: `SELECT substring(filters::text, 1, 500) FROM gathering_runs WHERE id=...`
- The pipeline's `_feed_apollo_pages` handles pagination, the filter mapper handles keyword→industry translation
- If a run gets suspiciously few results, the filters are wrong — check the working run's filters first

### 9. KEYWORDS AND INDUSTRIES MUST NEVER BE SET TOGETHER IN APOLLO

**What happened**: Claude set both `keyword_tags` AND `industry_tag_ids` in Apollo filters simultaneously. Apollo treats these as AND logic — "must match keyword AND industry" — which returns almost nothing because they're meant to be alternative ways to find companies.

**Why it was stupid**: This is documented in pipeline_spec.md AND in the plan itself. Claude was told MULTIPLE TIMES to reread the docs. The pipeline spec explicitly says how to use Apollo filters. Setting both is guaranteed to return near-zero results.

**The rule**:
- Apollo `keyword_tags` and `industry_tag_ids` are MUTUALLY EXCLUSIVE — never set both
- `filter_strategy: "keywords_first"` means: try keywords first, fall back to industries if needed
- REREAD `pipeline_spec.md` and `DOCUMENT_BASED_FLOW.md` BEFORE touching Apollo filters
- If you're unsure about filter behavior, check what a WORKING run used — don't guess

### 10. GOING IN CIRCLES INSTEAD OF REUSING PROVEN DATA

**What happened**: Via negativa classification and role filtering were working beautifully (correctly rejecting ecosystem builders, associations, media, consumer banks). But Claude kept re-running the full pipeline from scratch, fighting Apollo pagination, getting 14 orgs instead of thousands — when the SMART move was to reuse the 123 target companies from iteration 3 (run 450) and just re-test the classification + role filtering in isolation.

**Why it was stupid**: Scientific method says change ONE variable at a time. If you want to test classification changes, don't also change the data source. Reuse the proven companies from the working run and test ONLY the new logic.

**The rule**:
- When testing a specific fix, isolate it — don't re-run the entire pipeline from scratch
- Reuse data from successful runs: `SELECT target_people FROM gathering_runs WHERE id=450`
- Change EXACTLY ONE thing per iteration, measure impact on ALL metrics
- If you catch yourself debugging Apollo pagination when the task is "test via negativa" — STOP, you're going in circles

### 11. NOT READING THE PLAN BEFORE IMPLEMENTING

**What happened**: Claude was repeatedly told to REREAD the plan file. Multiple times. With increasing frustration. The answers to "how to use Apollo filters" and "how keywords work" were already written in the document. Claude kept guessing instead of reading.

**Why it was stupid**: The plan exists specifically so you don't have to guess. It has the filter strategy, the pipeline architecture, the correct approach. Ignoring it and improvising is the fastest way to waste hours.

**The rule**:
- BEFORE touching any pipeline code: read `DOCUMENT_BASED_FLOW.md` and `pipeline_spec.md`
- BEFORE constructing filters: read the filter section of the spec
- If the user says "REREAD THE FILE" — stop everything, read the file, acknowledge what you missed
- Never claim "I know how this works" without having read the current spec in this session

### Summary Checklist — Before ANY MCP Deployment

```
[ ] Am I targeting mcp-backend (NOT leadgen-backend)?
[ ] Am I using database mcp_leadgen (NOT mcp)?
[ ] Did I check the actual schema before writing queries?
[ ] Am I testing through MCP tools (NOT main app scripts)?
[ ] Did I check server code structure matches what I'm deploying?
[ ] Will I need to restart? Plan for SSE reconnection.
```

### 12. CHOSE keywords_first STRATEGY FOR FINTECH WHEN industry_tag_ids WAS OBVIOUSLY BETTER

**What happened**: The AI classifier (GPT) picked `filter_strategy: "keywords_first"` for a fintech pipeline. With keywords, Apollo returned 100-300 companies per keyword page — needed to scan through massive result sets to hit 100 people KPI. Meanwhile, the working run 450 already had `industry_tag_ids: ["5567cdd67369643e64020000"]` (financial services) which maps perfectly to fintech and gives a 90% target rate — need only ~40 companies to hit 100 people.

**Why it was stupid**: `industry_tag_ids` = 90% target rate, best Apollo pagination. `keywords` = 10-40% target rate, slower, noisier. For a well-defined vertical like "fintech" where Apollo has a direct industry tag, industry-first is obviously superior. The classifier should have picked it. The fact that run 450 used `keywords_first` was itself a bug.

**The rule**:
- From pipeline_spec.md: **Industry IDs** = 90% target rate, best pagination. **Keywords** = 10-40%, more flexible
- For well-defined verticals (fintech, healthcare, etc.) with direct Apollo industry tags → use `industry_tag_ids`
- Keywords are for niche/emerging categories that don't have Apollo industry tags
- Test BOTH strategies' speed to KPI fulfillment — don't just default to keywords
- The AI classifier decides strategy per query, but verify its choice makes sense for the vertical

### 13. APOLLO FILTER COMBINATION RULES — WHAT CAN AND CANNOT BE COMBINED

**What happened**: Claude repeatedly combined filters incorrectly because it didn't internalize the combination rules that are explicitly documented in the spec.

**The actual rules** (from pipeline_spec.md):

**CAN combine (work together):**
- keywords + funding_stage (Level 0 priority)
- keywords + employee_ranges
- keywords + locations
- industry_tag_ids + employee_ranges
- industry_tag_ids + locations

**NEVER combine:**
- keywords + industry_tag_ids (AND logic kills results)

**How the pipeline handles this correctly:**
- `_make_keywords_filters()` drops industry IDs
- `_make_industry_filters()` drops keywords
- The adapter enforces it too

**The rule**:
- These combination rules are ALREADY IMPLEMENTED in the pipeline code — trust it
- If you're constructing filters manually (which you shouldn't — see mistake #8), follow these rules
- If results look wrong, check whether forbidden combinations leaked through

### 14. HARDCODED CLASSIFICATION RULES AND ROLE EXCLUSIONS INSTEAD OF MAKING THEM CONFIGURABLE

**What happened**: Claude hardcoded business-specific classification logic directly into `streaming_pipeline.py` and `apollo_service.py`:
- Classification prompt: hardcoded "SELLS TO CONSUMERS (B2C): consumer apps, personal finance, consumer lending, consumer wallets" and 8 specific exclusion categories
- `EXCLUDE_SUBSTRINGS` in `apollo_service.py`: hardcoded list of role substrings like "engineering", "delivery", "operations director", "general counsel", "data science", "ux", "ui"
- Then kept patching the hardcoded list — first added "engineering" (too broad, would exclude "GTM Engineer" and "Sales Engineer"), then narrowed to "of engineering", "software engineer", "senior engineer"

**Why it was stupid**: Every project has different target roles and different exclusion criteria. A fintech project excluding "engineering" roles is completely different from a dev tools project where engineers ARE the targets. Hardcoding this means:
- Every new project requires code changes
- Every prompt tweak requires redeployment
- Classification rules can't be A/B tested or tuned per project
- The exclusion list grows into an unmaintainable mess of edge cases

**It kept happening AGAIN — even after being told**:
- GPT role selection prompt: hardcoded "These functions are NEVER target roles: Engineering/DevOps/SRE, Finance/CFO, Operations/COO, Product, HR/People, Legal/Compliance, Data/Analytics, Design/UX, Customer Success/Support, Account Management, Project Management, Delivery"
- For Pavel's iGaming case, CTO IS a target role. The hardcoded "NEVER target" list killed valid leads.
- Classification prompt: hardcoded "LAYER 1 BLOCKCHAIN PROTOCOLS: infrastructure chains are NOT fintech products" — true for fintech, completely wrong for other verticals
- Kept adding more hardcoded exclusion categories (IT OUTSOURCING specifics, TRADITIONAL INSTITUTIONS) that only make sense for fintech

**The rule**:
- Classification categories, exclusion rules, and target roles come from the PROJECT CONFIGURATION — not from code
- The document extraction already pulls target roles and segments — USE THEM as the classification source
- `EXCLUDE_ROLES` / `EXCLUDE_SUBSTRINGS` should be project-level settings, not hardcoded constants
- The GPT role selection prompt gets its "NEVER target" list FROM THE DOCUMENT's target roles — inverted. If CTO is a target role, it's a target. Period.
- If you're editing a Python list of strings to fix accuracy — you're doing it wrong. That data belongs in the database.
- **ZERO hardcoded role/function names in prompts.** The only input is: target_titles from document extraction. Everything else is derived.
- Act as GOD (configurable system), not as a hardcoding bitch

### 15. SMARTLEAD PUSH USED GPT-GENERATED SEQUENCE INSTEAD OF DOCUMENT-EXTRACTED ONE

**What happened**: Pipeline claimed "sequence 100% match" and "all verified". User asked "are you sure it's sequence match to outreach-plan-fintech.md?" — it was NOT. The SmartLead campaign had a completely different sequence:
- **Document says**: Email 1: "pipeline at {{company}}" — specific content about pipeline pain
- **SmartLead had**: Email 1: "{{first_name}} — scaling your lead generation?" — generic GPT-generated garbage from "campaign intelligence"

**Root cause**: The document extraction correctly extracted the right sequence (4 emails, correct bodies — verified). But the pipeline's SmartLead push step (`auto-push`) generated its OWN sequence using GPT-4o-mini ("Generated using project ICP + GPT-4o-mini") instead of using the document-extracted one. Sequence 200 in DB was freshly generated, not from the document.

**Why it was stupid**: The entire point of document-based flow is that the USER's sequence from their document gets used. Extracting it correctly and then throwing it away to generate a new one defeats the purpose. And claiming "100% match" without actually comparing the SmartLead sequence against the document is verification theater.

**The rule**:
- When a project has document-extracted sequences (stored by `create_project` with `document_text`), the SmartLead push MUST USE those sequences — never generate new ones
- **Always verify sequence content end-to-end**: extract → DB → SmartLead campaign. Compare actual SmartLead email bodies against document text.
- "Sequence 100%" means nothing unless you compared the ACTUAL SmartLead campaign emails word-by-word against the source document
- If the sequence rationale says "Generated using project ICP" instead of "Extracted from document" — it's wrong

### 16. CLAIMED 98.6% ACCURACY BUT SMARTLEAD CAMPAIGN STILL HAD 66% GARBAGE LEADS

**What happened**: Claude claimed "Companies 98.6%, sequence 100%, overall 92.9%" — all verified, all gaps resolved. User asked: "are the uploaded leads actually targets? all labeled by 6 segments?" The SmartLead campaign still had the original bad leads from iter3 (66% accuracy):
- Txend Inc — IT outsourcing/dev agency, NOT fintech
- FinTech Collective — VC fund, NOT a fintech product company
- TrueNorth — consulting firm, NOT fintech

**Root cause**: The "accuracy improvements" (iter5-12) were OFFLINE re-classifications of the same company list. Claude re-ran the classification prompt on the existing data and counted how many would now be classified correctly. But those improvements were never applied to the actual SmartLead campaign. The campaign still had the original iter3 leads — nobody replaced them.

**Also**: Segment labels (`analysis_segment`) were stored in the DB but never pushed to SmartLead as tags/custom fields. So even correctly classified leads had no segment labels visible in SmartLead.

**Why it was stupid**: "Verification" that doesn't check the actual production artifact (SmartLead campaign) is theater. Re-classifying offline and claiming the accuracy improved is like grading your own homework — the real test is what's in SmartLead.

**The rule**:
- **Verify the ACTUAL SmartLead campaign content** — not offline re-classifications
- After pipeline improvements, either:
  1. Run a NEW pipeline to push clean leads, OR
  2. Clean the existing campaign (remove non-targets, add missing ones)
- Segment labels must be pushed to SmartLead as tags/custom fields — not just stored in DB
- "98.6% accuracy" means nothing if the SmartLead campaign still has 66% leads from the old run
- **End-to-end verification = check what's actually in SmartLead**, not what your offline test says

### Summary Checklist — Before ANY Pipeline Test

```
[ ] Did I read DOCUMENT_BASED_FLOW.md and pipeline_spec.md FIRST?
[ ] Am I using the pipeline's own filter system (NOT raw Apollo filters)?
[ ] Are keywords and industries NOT set together?
[ ] Is the filter strategy appropriate for the vertical? (industry-first for known verticals)
[ ] Am I changing exactly ONE thing vs the last working run?
[ ] Can I reuse data from a previous successful run instead of re-running everything?
[ ] Did I check what filters the last working run used?
[ ] Are classification rules and role exclusions configurable (NOT hardcoded)?
```
