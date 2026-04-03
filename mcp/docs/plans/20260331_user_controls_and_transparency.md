# User Controls & Cost Transparency Plan
**Date**: 2026-03-31

## Requirements

User must be able to:
1. Set target contact count (default 100, can be 1000, 5000)
2. Continue gathering after initial batch ("find more")
3. See estimated Apollo cost BEFORE any credits are spent
4. Change roles/titles for people search (default C-level, adjustable)
5. Change contacts-per-company (default 3, adjustable)
6. Provide sequence approach from a file
7. All costs shown transparently at every step

---

## When MCP Shows Costs

**RULE: Every time Apollo credits will be spent, MCP shows cost estimate FIRST and waits for approval.**

### Cost checkpoints:

```
1. FILTER PREVIEW (tam_gather without confirm_filters)
   Shows:
   - Apollo filters applied
   - Total companies available in Apollo
   - Cost for default (30 targets, ~100 contacts): X credits
   - Cost for user's target (e.g. 1000 contacts): Y credits
   - Estimated target conversion rate
   User confirms → credits spent

2. EXPLORATION (tam_explore)
   Shows:
   - "Enriching top 5 targets: 5 credits"
   - "This will improve filters for better targeting"
   User confirms → credits spent

3. PEOPLE SEARCH (after companies gathered)
   Shows:
   - "Found 50 target companies"
   - "Gathering 3 contacts per company = 150 contacts"
   - "People search: FREE (mixed_people/api_search)"
   - "Roles: CEO, CTO, VP Engineering" (adjustable)
   No confirmation needed — people search is free

4. SCALE / CONTINUE (user says "find more")
   Shows:
   - "Current: 100 contacts from 34 companies"
   - "Next batch: pages 5-8 = 4 credits = ~100 more companies"
   - "Estimated: +30 targets = +90 contacts"
   - "Total after: ~190 contacts"
   User confirms → credits spent
```

---

## User Controls

### 1. Target Contact Count

```
User: "I want 1000 contacts"
MCP: "For 1000 contacts (3 per company = 334 target companies):
      - At 35% target rate: need ~950 companies from Apollo
      - That's ~10 pages = 10 credits ($0.10)
      - Plus 5 enrichment credits for exploration

      Total estimated: 15 credits ($0.15)
      Proceed?"

User: "yes"
→ Pipeline runs with max_pages calculated from target_count
```

**Implementation**: `tam_gather` already has `target_count` parameter. The filter preview calculates pages needed:
```python
target_count = args.get("target_count", 100)  # default 100 contacts
contacts_per_company = args.get("contacts_per_company", 3)
target_companies_needed = target_count // contacts_per_company  # 34
companies_needed = int(target_companies_needed / TARGET_RATE)  # 97
pages_needed = max(1, (companies_needed + per_page - 1) // per_page)  # 1
```

### 2. Continue Gathering

```
User: "find more" / "gather more" / "continue" / "I need more contacts"
MCP detects: existing run for this project
MCP: "Current run #249 has 34 targets (102 contacts).
      Next 4 pages = 4 credits = ~100 more companies → ~35 targets → ~105 contacts.
      Total after: ~207 contacts.
      Use same filters? Or adjust?"

User: "same filters, go ahead"
→ tam_gather with reuse_run_id + page_offset
```

**Implementation**: `tam_gather` already has `reuse_run_id`. Add `page_offset` to continue from where the previous run left off. Dispatcher checks for existing runs and calculates the next batch.

### 3. Change Roles/Titles

```
User: "change roles to VP Marketing and CMO"
User: "I want HR people, not technical"
User: "add Head of People Operations"

MCP: "Updated people filters:
      Titles: VP Marketing, CMO, Head of Marketing
      Seniority: vp, director, c_suite

      These will apply when gathering contacts for target companies."
```

**Implementation**: Store in `GatheringRun.people_filters` (already exists as JSONB):
```json
{
  "person_titles": ["VP Marketing", "CMO", "Head of Marketing"],
  "person_seniorities": ["vp", "director", "c_suite"],
  "contacts_per_company": 3
}
```

Agent A7 (People Filter Mapper) generates these from user's natural language + offer context.
Default: C-level for payroll, marketing heads for marketing tools, etc.

### 4. Change Contacts Per Company

```
User: "I want 5 contacts per company, not 3"
User: "just 1 contact per company is enough"

MCP: "Updated: 5 contacts per company.
      For your 34 target companies: 170 contacts (was 102).
      No additional Apollo credits needed — people search is free."
```

**Implementation**: `contacts_per_company` in `people_filters`. Default 3.

### 5. Provide Sequence Approach

```
User: "use this sequence approach: [paste text]"
User: "read my sequence from tasks/easystaff/sequence.md"
User: "here's how I want the emails to sound: [description]"

MCP: "Got it. I'll use your approach for sequence generation:
      - Tone: [extracted]
      - Structure: [extracted]
      - Key points: [extracted]

      This will be used when generating the email sequence."
```

**Implementation**: Store in `ProjectKnowledge` (category="sequence_approach"). The sequence generator (`campaign_intelligence.py`) already reads project knowledge. The agent reads the file, extracts the approach, and stores it via `provide_feedback` or `update_project`.

### 6. Change Default KPIs

```
User: "I want 50 targets minimum, not 30"
User: "target rate should be at least 50%"

MCP: "Updated KPIs:
      - Minimum targets: 50 (was 30)
      - This means: ~167 companies needed (at 30% rate)
      - Pages: 2 = 2 credits

      Current run has 34 targets. Need 16 more.
      Shall I continue gathering?"
```

**Implementation**: Store in project config or run filters. The pipeline checks KPIs after classification and suggests next steps.

---

## Agent Chain Updates

### Current agents:
```
A0: Intent Splitter (gpt-4o-mini)
A1: Industry Picker (gpt-4o-mini)
A2: Keyword Picker (gpt-4.1-mini)
A3: Size Inferrer (gpt-4o-mini)
A4: Location Extractor (regex)
A5: Target Classifier (gpt-4o-mini, tuned prompt)
A6: Filter Optimizer (gpt-4.1-mini)
A7: People Filter Mapper (gpt-4o-mini) — needs implementation
```

### New/updated agents:

**A7: People Filter Mapper** (gpt-4o-mini)
```
Input: offer text + user's role preferences (if any)
Output: {
  "person_titles": ["CEO", "CTO", "VP Engineering"],
  "person_seniorities": ["c_suite", "vp", "director"],
  "contacts_per_company": 3
}

Default behavior (no user preference):
  - Payroll product → HR roles (VP HR, CHRO, Head of People)
  - DevTools product → Tech roles (CTO, VP Engineering, Head of DevOps)
  - Marketing tool → Marketing roles (CMO, VP Marketing, Head of Growth)
  - General B2B → C-suite (CEO, CTO, COO)

When user says "change roles":
  Update people_filters on the run, re-gather people for existing targets.
```

**A8: Cost Estimator** (no GPT, pure calculation)
```
Input: target_count, contacts_per_company, target_rate, per_page
Output: {
  "companies_needed": 334,
  "pages_needed": 4,
  "search_credits": 4,
  "enrichment_credits": 5,
  "total_credits": 9,
  "total_cost_usd": 0.09,
  "people_search_cost": "FREE"
}

Called at: filter preview, continue/scale, exploration suggestion
```

---

## Flow with Controls

```
User: "find IT consulting companies in Miami, I want 500 contacts"

MCP (A0): Parses → 1 segment, target_count=500
MCP (A1-A4): Generates filters
MCP (A8): Calculates → 500/3=167 companies needed, 167/0.35=477 from Apollo, 5 pages

MCP → User:
  "Apollo search preview:
   Keywords: information technology & services, IT consulting, ...
   Location: Miami
   Size: 11-200 employees

   Available: 3,864 companies
   For 500 contacts (3 per company, ~35% target rate):
     Search: 5 pages = 5 credits ($0.05)
     Exploration: 5 credits ($0.05)
     People search: FREE
     Total: ~$0.10

   Roles (default for payroll product):
     VP HR, CHRO, Head of People Operations
     Seniority: VP, Director, C-suite

   Proceed? You can also:
   - Change target count
   - Change roles
   - Adjust filters"

User: "change roles to CTO and VP Engineering"

MCP: "Updated roles: CTO, VP Engineering, Head of Engineering
      Seniority: C-suite, VP, Director

      Same cost estimate. Proceed with gathering?"

User: "yes"

→ Pipeline runs with:
  - target_count=500
  - contacts_per_company=3
  - people_filters={titles: [CTO, VP Engineering], seniorities: [c_suite, vp, director]}
  - max_pages=5

[... gathering completes ...]

MCP → User:
  "Gathered 475 companies, 168 targets (35% rate), 504 contacts.
   Credits used: 5 search + 5 enrichment = 10 ($0.10)

   Want to:
   1. Generate email sequence
   2. Find more contacts (next 5 pages = 5 credits)
   3. Review targets in pipeline"

User: "find more, I want 1000 total"

MCP (A8): Calculates → need 496 more contacts, ~166 more targets, ~474 companies, 5 pages

MCP → User:
  "Continue gathering:
   Current: 504 contacts from 168 targets
   Next batch: pages 6-10 = 5 credits ($0.05)
   Estimated: +166 targets → +498 contacts
   Total after: ~1002 contacts

   Proceed?"

User: "yes"
→ tam_gather with reuse_run_id + page_offset=6
```

---

## Implementation Checklist

### Backend:
- [ ] `tam_gather` filter preview shows cost for user's target_count
- [ ] `tam_gather` supports `page_offset` for continue/scale
- [ ] `people_filters` stored on GatheringRun (already exists)
- [ ] A7 People Filter Mapper (gpt-4o-mini)
- [ ] A8 Cost Estimator (pure calculation)
- [ ] `provide_feedback` with type="roles" updates people_filters
- [ ] `provide_feedback` with type="sequence" stores in ProjectKnowledge
- [ ] Sequence generator reads sequence_approach from ProjectKnowledge

### MCP Tools:
- [ ] `tam_gather` preview includes cost breakdown
- [ ] `tam_gather` preview includes default roles + "you can change"
- [ ] Continue/scale shows current + projected totals
- [ ] Tool descriptions mention adjustable parameters

### Tests:
- [ ] TEST: user sets target_count=1000 → correct pages calculated
- [ ] TEST: user says "find more" → reuse_run_id + page_offset
- [ ] TEST: user changes roles → people_filters updated
- [ ] TEST: user changes contacts_per_company → affects estimate
- [ ] TEST: user provides sequence file → stored in knowledge
- [ ] TEST: cost shown at every credit-spending step
