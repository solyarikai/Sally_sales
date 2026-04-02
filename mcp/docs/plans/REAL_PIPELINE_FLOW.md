# Real Pipeline Flow — How It Works End-to-End

## The Complete User Journey

```
1. User connects MCP (SSE token in URL)
2. User: "launch outreach-plan-fintech.md"
3. MCP extracts EVERYTHING from document
4. MCP shows extracted data → user approves
5. MCP asks: "Previous campaigns?" → user: "no"
6. MCP asks: "Which email accounts?" → user: "all with rinat"
7. MCP creates draft campaign with accounts + sequence
8. MCP runs Apollo probe (funding + industry/keywords + geo + size)
9. MCP shows: filters, total companies, cost estimate, pipeline link → user approves
10. Pipeline runs AUTONOMOUSLY (scrape → classify → people → SmartLead push)
11. Pipeline shows FINISHED state. Campaign in SmartLead as DRAFT.
```

---

## Step-by-Step Detail

### Step 1: MCP Connect
- User connects via SSE URL with token: `http://host:8002/mcp/sse?token=mcp_xxx`
- Token authenticates the session
- `get_context` returns user's projects, integrations, active state

### Step 2: User says "launch outreach-plan-fintech.md"
- Claude reads the file from disk
- Calls `create_project(website="getsally.io", document_text=<full content>)`

### Step 3: MCP Extracts Everything
Document extractor (gpt-4.1-nano) pulls:
- **Offer**: what we sell
- **Target audience**: who buys
- **8 segments**: PAYMENTS, LENDING, BaaS, REGTECH, INSURTECH, WEALTHTECH, CRYPTO/DEFI, EMBEDDED FINANCE
- **Target roles**: VP Sales, Head of Sales, CRO, Head of Growth, VP Marketing, CMO, CEO, Co-founder
- **3 sequences**: Fintech Pipeline Pain (4 emails), Fresh Funding (3), Competitor Conquest (2)
- **Campaign settings**: tracking, stop-on-reply, plain text, daily limit
- **Exclusion list**: if document has a "shit list" section (like Pavel's iGaming doc)

**Sequences are GPT-rewritten**: any unfillable variables ({{hiring_role_or_signal}}) replaced with natural text. All variables mapped to SmartLead column names ({{first_name}}, {{company_name}}).

**Stored in DB**: 
- `project.offer_summary` = all extracted data
- `generated_sequences` = sequence with steps
- Everything visible on project page

### Step 4: MCP Shows Extracted Data → User Approves
Response includes:
```
**Offer extracted from document:**
  Product: Sally's done-for-you lead gen...
  Target audience: B2B fintech companies...

**8 market segments:**
  - PAYMENTS: fintech payments, payment processing...
  - LENDING: fintech lending, loan platform...
  ...

**Target decision makers:** VP Sales, Head of Sales, CRO, ...

**Sequence: Fintech Pipeline Pain (4 emails)**
  Email 1 (Day 1): pipeline at {{company_name}}
  Email 2 (Day 3): Re: pipeline at {{company_name}}
  ...

**Campaign settings:** No tracking, Stop on reply, 35/mailbox/day

**Is this correct?**
```

User: "yes" → `confirm_offer(project_id=X, approved=true)`

### Step 5: MCP Asks About Previous Campaigns
"Have you launched campaigns for this segment before?"
User: "no" → no blacklist needed

### Step 6: MCP Asks About Email Accounts
"Which email accounts should I use?"
User: "all with rinat"
→ Queries SmartLead accounts cache (instant, no API call)
→ Finds 138 Rinat accounts
→ Creates **draft campaign** with:
  - 138 email accounts attached
  - Document-extracted sequence linked
  - Campaign settings from document

### Step 7: Apollo Probe + Filter Strategy

**Which strategy for fintech?**

Based on test results:
- **Industry-first** gives 90% target rate but Apollo returns 0 per page for keyword search (sparse pagination)
- **Keywords-first** gives 10-40% target rate but works with Apollo's keyword search
- **The actual winning strategy**: Use the filter_mapper which picks based on available taxonomy matches

**Answer: For fintech, the A11 classifier picked `keywords_first`** because "financial services" industry tag gives very broad results (93K companies). Keywords narrow better to actual fintech. The pipeline's 3-level cascade handles exhaustion:
1. Level 1: Keywords (25 pages)
2. Level 2: Keyword regeneration (5 cycles × 20 pages)
3. Level 3: Industry IDs fallback (25 pages)

**Funding filter as PRIORITIZATION (not hard filter)**:
```
Level 0: Keywords + funding_stage (Series A-D) — highest quality, funded companies first
  → When exhausted (no more funded companies matching keywords)...
Level 1: Keywords WITHOUT funding — broader pool, same keywords
  → When exhausted...
Level 2: Keyword regeneration + no funding
  → When exhausted...
Level 3: Industry IDs fallback
```

This is the SMART approach: funding prioritizes but doesn't exclude. Geo and size are HARD filters (never changed). Funding is SOFT (drops when exhausted).

**CURRENT IMPLEMENTATION**: Funding filter is supported (`organization_latest_funding_stage_cd` parameter in Apollo search) but NOT currently used as Level 0 priority. The pipeline goes straight to keywords. **GAP: Need to add funding as Level 0 before keywords**.

**Probe request**:
- `tam_gather(project_id=X)` — NO confirm_filters
- Creates pipeline in `pending_approval` status
- Probes Apollo page 1 (100 companies, 1 credit)
- Shows: total companies with funding filter, keywords, cost estimate, pipeline link

### Step 8: User Approves Filters
MCP shows:
```
Apollo probe: 540 funded fintech companies (Series A-D)
Keywords: 30 selected
Strategy: funding → keywords → industry fallback
Cost estimate: ~$1.50 (150 pages max)
Pipeline: http://host:3000/pipeline/runs/XXX

Proceed?
```

User: "yes" → `tam_gather(project_id=X, confirm_filters=true)`

### Step 9: Pipeline Runs AUTONOMOUSLY

Once confirmed, pipeline starts with ZERO more user interaction:
```
Time 0s:  100 probe companies → scrape queue (already in DB)
Time 0s:  Apollo pages 2-10 fetched in parallel (10 concurrent)
Time 1s:  First scraped websites → classification queue
Time 2s:  First classified targets → people queue  
Time 3s:  Pages arrive → more companies → scrape → classify → people
...
Time 30s: KPI met (100+ people) → pipeline stops
Time 31s: Auto-push to SmartLead:
          - Creates SmartLead campaign
          - Uses document-extracted sequence (not GPT-generated)
          - Sets campaign settings from document
          - Uploads ONLY target-company contacts with segment labels
          - Attaches 138 Rinat email accounts
          - Sets schedule (timezone from contacts geography)
Time 32s: Pipeline status = COMPLETED
```

### Step 10: Pipeline Shows FINISHED State
- Status: COMPLETED
- Duration: ~30-40 seconds
- Targets found: ~80-90
- People found: ~140-150
- SmartLead campaign link: `https://app.smartlead.ai/app/email-campaigns-v2/XXXXX/analytics`
- Campaign status: DRAFT (ready for operator to activate)

### Step 11: All Data Stored in DB
- **discovered_companies**: each company with `scraped_text`, `is_target`, `analysis_segment`, `analysis_reasoning`
- **extracted_contacts**: each person with `email`, `job_title`, `email_verified`
- **campaigns**: SmartLead external_id, leads_count, sequence_id, email_account_ids
- **gathering_runs**: status, credits_used, duration, targets_found, people_found

All visible in pipeline page UI:
- Companies list with segments, target/rejected status
- People list with roles
- Scraping status per company
- Classification reasoning per company

---

## Answers to Specific Questions

### Q: Industry-first or keywords-first for fintech?
**A: Keywords-first** was used in all successful runs. The A11 classifier chose this because "fintech" maps to very broad Apollo industries. Keywords are more specific. BUT with the funding priority layer, the cascade would be:
1. Funded + keywords (Level 0) — best quality
2. All + keywords (Level 1) — broader
3. Keywords regen (Level 2) — fresh keywords
4. Industry fallback (Level 3) — last resort

### Q: Will funding filter be applied?
**A: YES** — the document says "Series A through Series D". Apollo supports `organization_latest_funding_stage_cd` filter. It should be used as Level 0 priority (funded first), then dropped when exhausted. **Currently a gap — funding filter is supported but not used as Level 0**.

### Q: How does the draft campaign timing work?
**A: Draft campaign created AFTER email accounts selected (Step 6)**. This is correct — you need accounts before creating the campaign. The pipeline link is shown after Apollo filters approved (Step 8). SmartLead campaign created automatically after KPI hit (Step 9).

### Q: Is all data stored and visible?
**A: YES** — scraped_text, classification, segments, people all stored in discovered_companies + extracted_contacts tables. Pipeline page shows all data in columns. Clicking a company shows details.

---

## Gaps Found in Current Implementation

| # | Gap | Status |
|---|-----|--------|
| 1 | Funding filter not used as Level 0 priority | **GAP — need to implement** |
| 2 | Auto-push doesn't fire in standalone script context | Works in FastAPI context (MCP tools) |
| 3 | Agent #2 prompt consistency (temperature now 0) | **FIXED** |
| 4 | SmartLead tracking logic | **FIXED** |
| 5 | Variable name mapping | **FIXED** |
| 6 | Frontend display of extracted data | Task #30 pending |
