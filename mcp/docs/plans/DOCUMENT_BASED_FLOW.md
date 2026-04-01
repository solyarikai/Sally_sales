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
  - Correct segment label assigned?
Score: % of companies that are REAL targets per document ICP.
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

## Reference Data

- **Website**: getsally.io
- **Document**: `mcp/outreach-plan-fintech.md`
- **Email accounts**: all with "rinat" in name (campaign 3070916)
- **Expected**: 1 campaign, 6 segment labels, Sequence A, 100+ people
- **KPI**: default (100 people, 3/company)
- **Time target**: <5 minutes per segment
