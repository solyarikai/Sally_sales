# Document-Based Pipeline Flow — Implementation Plan

## What This Is

User provides a strategy document (like `outreach-plan-fintech.md`) instead of answering questions one by one. The system extracts everything needed to create a project + launch pipeline automatically.

## What the Document Contains (outreach-plan-fintech.md example)

| Data | Extracted For | Example from Doc |
|------|--------------|------------------|
| Company/Website | Project creation | Sally / getsally.io (user provides) |
| Offer | Offer analysis | "done-for-you lead gen, 10-50 qualified meetings/month" |
| ICP segments | Apollo filters | Fintech, 20-500 employees, Series A-D, US/UK/EU/UAE/Singapore |
| Sub-verticals | Multiple pipeline runs | Payments, Lending, BaaS, RegTech, WealthTech, Crypto |
| Target roles | People search | VP Sales, Head of Growth, CRO, CEO, CMO |
| Funding stage | Apollo filters | Series A through Series D |
| Geography | Apollo filters | US, UK, EU, UAE, Singapore |
| Employee range | Apollo filters | 20-500 |
| Email sequences | SmartLead campaign | 3 sequences with 3-4 emails each, personalization vars |
| Personalization tiers | Sequence selection | Tier 1 (high-touch), Tier 2 (mid), Tier 3 (volume) |
| KPI targets | Pipeline KPIs | 10-50 meetings/month, 2000-3000 contacts |
| Campaign settings | SmartLead config | 30-40 emails/mailbox/day, warmup, deliverability |

## The Flow

```
1. User provides document (file upload or paste)
2. GPT extracts structured data:
   - offer, value_prop, target_audience
   - target_roles (with seniorities)
   - segments (each becomes a pipeline run)
   - sequences (email templates)
   - apollo_filters per segment
   - campaign_settings
3. System creates project with extracted data
4. Show user: "I extracted 6 segments, 3 sequences, these roles. Correct?"
5. User approves
6. For EACH segment: run the standard pipeline
   - Same flow: blacklist → accounts → tam_gather → pipeline → SmartLead
   - But automated: all segments queued sequentially
7. Each segment gets its own SmartLead campaign with matching sequence

```

## Architecture Extension

### New: Document Extraction Service
**File**: `mcp/backend/app/services/document_extractor.py`

```python
async def extract_from_document(text: str, website: str, openai_key: str, model: str) -> dict:
    """Extract project data from a strategy document.
    
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
            "segments": [
                {
                    "name": "Payments/PSPs",
                    "keywords": ["payments", "payment processing", "PSP", "cross-border payments"],
                    "locations": ["United States", "United Kingdom", "European Union", "UAE", "Singapore"],
                    "employee_range": "20,500",
                    "funding_stages": ["series_a", "series_b", "series_c", "series_d"],
                    "rationale": "Cross-border payment demand surging"
                },
                {
                    "name": "Lending/BNPL", ...
                },
                ...6 segments total
            ],
            "sequences": [
                {
                    "name": "Fintech Pipeline Pain",
                    "trigger": "General — has sales team",
                    "steps": [
                        {"day": 1, "subject": "pipeline at {{company}}", "body": "..."},
                        {"day": 3, "subject": "Re: pipeline at {{company}}", "body": "..."},
                        {"day": 7, "subject": "quick question, {{firstName}}", "body": "..."},
                        {"day": 14, "subject": "closing the loop", "body": "..."}
                    ]
                },
                {
                    "name": "Fresh Funding",
                    "trigger": "Raised funding in last 90 days",
                    "steps": [...]
                },
                {
                    "name": "Competitor Conquest",
                    "trigger": "Uses competing agency",
                    "steps": [...]
                }
            ],
            "campaign_settings": {
                "daily_limit_per_mailbox": 35,
                "warmup_days": 21,
                "tracking": false,
                "stop_on_reply": true,
                "timezone": "America/New_York"
            },
            "what_cannot_be_automated": [
                "Conference attendee lists (Money20/20, Finovate)",
                "Competitor-user detection (Belkins, CIENCE)",
                "LinkedIn manual touchpoints for Tier 1",
                "WhatsApp/Telegram channels"
            ]
        }
    """
```

### New MCP Tool: `upload_document`
**File**: `mcp/backend/app/mcp/tools.py` + `dispatcher.py`

```python
{
    "name": "upload_document",
    "description": "Upload a strategy document to extract segments, roles, sequences.",
    "inputSchema": {
        "properties": {
            "project_id": {"type": "integer"},
            "document_text": {"type": "string", "description": "Full document text"},
            "document_url": {"type": "string", "description": "URL to fetch document from"},
        }
    }
}
```

### Project Page Extension
- Show document extraction log at top of project page
- Show all extracted segments as pipeline runs
- Show extracted sequences
- Version history: each document upload creates a new extraction entry

### Multi-Segment Pipeline Queue
When document has 6 segments, the system:
1. Creates 6 GatheringRuns (all pending_approval)
2. Shows all to user for approval
3. On approval: runs them SEQUENTIALLY (saves Apollo credits, avoids rate limits)
4. Each run uses its own keywords/filters derived from segment
5. Each completed run pushes to SmartLead with matching sequence

---

## GPT Model Testing Plan

### What to Test
Extract structured data from `outreach-plan-fintech.md` using different models. Score by:
1. **Segments extracted correctly** (6 expected)
2. **Roles extracted correctly** (3 tiers expected)
3. **Sequences extracted correctly** (3 sequences, 10 emails total)
4. **Apollo filters mapped correctly** (locations, size, keywords)
5. **What-cannot-be-automated identified** (conference lists, competitor detection)

### Models to Test

| Model | Cost/1K tokens | Expected Quality |
|-------|---------------|-----------------|
| gpt-4o | $0.005 in / $0.015 out | Best quality, expensive |
| gpt-4o-mini | $0.00015 in / $0.0006 out | Good quality, cheap |
| gpt-4.1-mini | $0.0004 in / $0.0016 out | Newer, potentially better |
| gpt-4.1-nano | $0.0001 in / $0.0004 out | Cheapest, quality unknown |

### Test Methodology
1. Send the FULL document to each model with the extraction prompt
2. Parse the JSON response
3. Score each field against ground truth (manually verified)
4. Log: model, tokens used, cost, time, accuracy per field
5. Save results to `mcp/tests/results/document_extraction_MODEL_TIMESTAMP.json`

### Scoring Criteria
```
Perfect: all 6 segments, all roles, all 3 sequences with all emails, correct filters
Good: 5-6 segments, most roles, 2-3 sequences, mostly correct filters
Acceptable: 4+ segments, primary roles, at least 1 sequence
Bad: <4 segments or missing roles or no sequences
```

---

## Test Execution Plan

### Test 1: Model Comparison (extraction quality)
```
For each model:
  1. Send document + extraction prompt
  2. Parse response
  3. Score against ground truth
  4. Log results with timestamp
```

### Test 2: Full E2E Flow
```
1. Create project: getsally.io
2. Upload document: outreach-plan-fintech.md
3. System extracts 6 segments
4. User approves
5. For segment "Payments/PSPs":
   a. Blacklist: "no"
   b. Accounts: "all with rinat in name"
   c. tam_gather preview → filters, cost
   d. Approve → pipeline runs
   e. SmartLead campaign created with Sequence A
6. Verify:
   - Companies are real fintech/payments companies
   - People are VP Sales / CRO / Head of Growth
   - Sequence matches "Fintech Pipeline Pain"
   - Campaign has Rinat email accounts
   - Campaign settings match doc (no tracking, stop on reply)
```

### Test 3: Document Variations
- Test with shorter documents (just ICP + no sequences)
- Test with multiple documents (iterative enrichment)
- Test with conflicting info (document says "50-200" but user said "up to 500")

---

## Implementation Order

1. **document_extractor.py** — GPT extraction service
2. **Model comparison tests** — find best model
3. **upload_document tool** — MCP tool + dispatcher
4. **Multi-segment pipeline queue** — sequential runs from extracted segments
5. **Project page: document log** — show extraction history
6. **E2E test: fintech outreach** — full flow with Rinat accounts
7. **Sequence-to-SmartLead mapping** — extracted sequences pushed to campaigns

---

## Reference Data for Testing

- **Website**: getsally.io
- **Document**: `mcp/outreach-plan-fintech.md`
- **Email accounts**: all with "rinat" in name (from campaign 3070916)
- **Expected segments**: 6 (Payments, Lending, BaaS, RegTech, WealthTech, Crypto)
- **Expected sequences**: 3 (Pipeline Pain, Fresh Funding, Competitor Conquest)
- **Expected roles**: VP Sales, CRO, Head of Growth, CMO, CEO
- **KPI**: 100 people per segment, 3/company, default pipeline
