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
| Sequence A: all 4 emails with subjects + bodies | 4 |
| Campaign settings correct | 1 |
| **Total** | **13** |

### Test Method
1. Send full document to each model with extraction prompt
2. Parse JSON response
3. Score against ground truth
4. Log: model, tokens, cost, time, score per field
5. Save to `mcp/tests/results/doc_extract_{MODEL}_{TIMESTAMP}.json`

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

## Reference Data

- **Website**: getsally.io
- **Document**: `mcp/outreach-plan-fintech.md`
- **Email accounts**: all with "rinat" in name (campaign 3070916)
- **Expected**: 1 campaign, 6 segment labels, Sequence A, 100+ people
- **KPI**: default (100 people, 3/company)
- **Time target**: <5 minutes per segment
