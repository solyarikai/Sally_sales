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

**5. Combined 6-segment classification prompt**
Must handle multi-segment classification before E2E test.

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

### Questions to Answer
1. Does organization SEARCH return funding data (stage, date, amount)?
2. Or does only enrichment return it? (enrichment = 1 credit per company = too expensive)
3. Does the funding stage filter actually work? How many companies match?
4. Is the total with funding filter still large enough for default KPI (100 people)?

### Test Plan
```
Test A: Search WITHOUT funding filter → count total, check if funding data in response
Test B: Search WITH funding filter (series_a, series_b, series_c, series_d) → count total
Test C: Compare → is filtered set big enough? Does response include funding date?
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
