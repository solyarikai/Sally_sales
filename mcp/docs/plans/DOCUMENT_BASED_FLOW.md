# Document-Based Pipeline Flow — Implementation Plan

## What This Is

User provides a strategy document filename in MCP chat (e.g. "launch outreach-plan-fintech.md"). Claude Code reads the file from disk, extracts everything needed, creates project + launches pipeline. No upload API needed — Claude Code has filesystem access.

## How It Works

```
User: "outreach-plan-fintech.md"

Claude Code:
  1. Reads file from disk (has filesystem access)
  2. Sends content to create_project(website: "getsally.io", document_text: <content>)
  3. GPT extracts: offer, roles, filters, sequence, campaign settings
  4. Silently skips what can't be automated (no explanations)
  5. Shows user extracted data → "Correct?"
  6. Standard flow: blacklist → accounts → pipeline → SmartLead
```

No new upload_document tool needed. `create_project` extended to accept `document_text`.

## What GPT Extracts (outreach-plan-fintech.md)

### TAKES (can automate):

| Data | Value | Used For |
|------|-------|----------|
| Offer | "Sally's done-for-you lead gen — qualified appointments through omnichannel outreach" | Offer analysis, classification prompt |
| Value prop | "10-50 qualified meetings/month within 6-8 weeks" | Sequence personalization |
| ICP | B2B fintech, 20-500 employees, Series A-D | ONE Apollo search (one segment) |
| Geography | US, UK, EU, UAE, Singapore | Apollo location filter |
| Employee range | 20-500 | Apollo size filter |
| Target roles (primary) | VP Sales, Head of Sales, CRO | People search seniority + title match |
| Target roles (secondary) | Head of Growth, VP Marketing, CMO | People search fallback |
| Target roles (tertiary) | CEO, Co-founder | People search for small companies |
| Sequence A "Pipeline Pain" | 4 emails (day 1, 3, 7, 14) | SmartLead campaign sequence |
| Campaign settings | No tracking, stop on reply, 35/mailbox/day | SmartLead campaign config |

### ONE Pipeline Run (not 6)

The document describes ONE ICP (B2B fintech) with sub-verticals as keyword hints, NOT separate campaigns. Sub-verticals (Payments, Lending, BaaS, RegTech, WealthTech, Crypto) are used as **keywords for Apollo search** — all results go into ONE campaign with Sequence A.

```
ONE project: Sally / getsally.io
ONE pipeline: fintech companies, 20-500, Series A-D, US/UK/EU/UAE/Singapore
ONE sequence: "Pipeline Pain" (4 emails)
ONE SmartLead campaign with Rinat accounts
```

## Extraction Service

**File**: `mcp/backend/app/services/document_extractor.py`

```python
async def extract_from_document(text: str, website: str, openai_key: str, model: str) -> dict:
    """Extract project data from a strategy document.
    
    Extracts what can be automated. Silently skips the rest.
    
    Returns:
        {
            "offer": "done-for-you lead gen...",
            "value_prop": "10-50 qualified meetings/month",
            "target_audience": "B2B fintech companies, Series A-D",
            "target_roles": {
                "primary": ["VP Sales", "Head of Sales", "CRO"],
                "secondary": ["Head of Growth", "VP Marketing", "CMO"],
                "tertiary": ["CEO", "Co-founder"],
                "seniorities": ["c_suite", "vp", "head", "director", "founder"]
            },
            "apollo_filters": {
                "keywords": ["fintech", "payments", "lending", "banking-as-a-service", 
                             "regtech", "insurtech", "wealthtech", "embedded finance",
                             "payment processing", "digital banking"],
                "locations": ["United States", "United Kingdom", "Germany", "France",
                              "United Arab Emirates", "Singapore"],
                "employee_range": "20,500",
                "industries": ["financial services", "banking", "insurance"]
            },
            "sequence": {
                "name": "Fintech Pipeline Pain",
                "steps": [
                    {"day": 1, "subject": "pipeline at {{company}}", "body": "Hi {{firstName}}..."},
                    {"day": 3, "subject": "Re: pipeline at {{company}}", "body": "..."},
                    {"day": 7, "subject": "quick question, {{firstName}}", "body": "..."},
                    {"day": 14, "subject": "closing the loop", "body": "..."}
                ]
            },
            "campaign_settings": {
                "daily_limit_per_mailbox": 35,
                "tracking": false,
                "stop_on_reply": true,
                "plain_text": true
            },
            # No "skipped" array — silently omits what can't be automated
        }
    """
```

## GPT Model Testing Plan

### Models to Test

| Model | Cost/1K tokens | Notes |
|-------|---------------|-------|
| gpt-4o | $0.005 in / $0.015 out | Best quality, expensive |
| gpt-4o-mini | $0.00015 in / $0.0006 out | Good quality, cheap |
| gpt-4.1-mini | $0.0004 in / $0.0016 out | Newer |
| gpt-4.1-nano | $0.0001 in / $0.0004 out | Cheapest |

### Scoring (ground truth from manual review)

| Field | Perfect Score |
|-------|--------------|
| Offer extracted correctly | 1 point |
| Target audience correct | 1 point |
| Roles: all 3 tiers with correct titles | 3 points |
| Apollo filters: keywords (10+) | 1 point |
| Apollo filters: locations (6) | 1 point |
| Apollo filters: employee range correct | 1 point |
| Sequence A: all 4 emails with subjects + bodies | 4 points |
| Campaign settings: no tracking, stop on reply, daily limit | 1 point |
| **Total** | **13 points** |

### Test Method
1. Send full document + extraction prompt to each model
2. Parse JSON response
3. Score against ground truth
4. Log: model, tokens, cost, time, score per field
5. Save to `mcp/tests/results/doc_extract_{MODEL}_{TIMESTAMP}.json`

## E2E Test Plan

```
1. User: "outreach-plan-fintech.md"
2. Claude reads file, calls create_project(website: "getsally.io", document_text: ...)
3. System shows: extracted offer, roles, filters, sequence, skipped items
4. User: "correct"
5. System: "Previous campaigns?" → User: "no"
6. System: "Email accounts?" → User: "all with rinat in name"
7. System: tam_gather preview → 1 segment, fintech keywords, cost estimate
8. User: "proceed"
9. Pipeline runs → scrape → classify → people → SmartLead
10. SmartLead campaign created with:
    - Sequence A (4 emails)
    - Rinat email accounts
    - No tracking, stop on reply
    - 100 verified contacts (default KPI)

Verify:
  - Companies are REAL fintech companies (payments, lending, etc.)
  - People are VP Sales / CRO / Head of Growth (correct roles)
  - Sequence matches doc's "Pipeline Pain" emails
  - Campaign has Rinat accounts
  - Skipped items reported to user
```

## Implementation Order

1. **document_extractor.py** — extraction service with smart skip logic
2. **Model comparison tests** — find best model for extraction
3. **Extend create_project** — accept `document_text` param
4. **Project page** — show extraction log + skipped items
5. **E2E test** — full flow with fintech doc + Rinat accounts
6. **Sequence push** — extracted sequence → SmartLead campaign

## Reference Data

- **Website**: getsally.io
- **Document**: `mcp/outreach-plan-fintech.md`
- **Email accounts**: all with "rinat" in name (campaign 3070916 reference)
- **Expected**: 1 segment, 1 sequence (A), roles VP Sales/CRO/CEO
- **KPI**: 100 people, 3/company, default pipeline
