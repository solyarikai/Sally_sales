# Test Plan: Mifort iGaming — Full Pipeline to SmartLead

## Scenario
User provides DETAILED segment description + example companies from `PAVEL_EXAMPLE_OF_TARGET_COMPANIES_DESCRIPTION.md`

**Offer:** Mifort (https://mifort.com/) — IT outsourcing from Tallinn. Web, Mobile, ML.
**Segment:** iGaming Providers (platform providers, game studios, aggregators, sports data, payment providers, anti-fraud, affiliate platforms, BI/analytics)
**Size:** 20-500 employees
**Geo:** Global (Malta, Gibraltar, Cyprus, Armenia, Israel, Nordics, Eastern Europe)
**Examples:** SoftSwiss, Pragmatic Play, BetConstruct, Digitain, Evoplay (all with domains)
**Exclusions:** Casino operators (Bet365, 888, LeoVegas etc.) — they USE platforms, don't BUILD them

**Email accounts:** "all emails that have pavel in name and mifort in domain"
**Reference SmartLead accounts:** https://app.smartlead.ai/app/email-campaigns-v2/3109584/email-accounts

**KPI:** 100 target people, max 3 per company (default)

## What This Tests (vs TFP test)
- `define_targets` with CASE 4 (examples + description) — TFP test only uses Case 3
- Example enrichment in Apollo (5 companies → extract common filters)
- Skip exploration phase (examples provide filter seeds)
- Detailed exclusion criteria in classification prompt
- `align_email_accounts` with multi-field filter (name + domain)

## Pre-test Setup
1. Create test user `qwe_mifort_[timestamp]@qwe.qwe` (password `qweqweqwe`)
2. Create project from https://mifort.com/ → scrape offer → confirm offer + target roles
3. Verify Apollo/OpenAI/SmartLead/Apify keys configured
4. Verify credit tracking enabled in DB

## Flow (what MCP agent does)

### Step 1: Create Project
```
create_project(name="Mifort", website="https://mifort.com/")
→ Scrape website → extract offer (IT outsourcing, dedicated teams)
→ Extract target roles (CTO, VP Engineering, Head of Development)
```

### Step 2: Confirm Offer
```
confirm_offer(approved=true)
→ Offer: IT outsourcing / dedicated dev teams
→ Roles: CTO, VP Engineering, Head of Development, Head of Product
```

### Step 3: Define Targets (CASE 4 — the key test)
User's agent reads PAVEL_EXAMPLE_OF_TARGET_COMPANIES_DESCRIPTION.md, extracts:
- segment_description: full ICP text from the file
- example_domains: ["softswiss.com", "pragmaticplay.com", "betconstruct.com", "digitain.com", "evoplay.games"]
- locations: [] (global)
- employee_range: "21,500"

```
define_targets(
  project_id=X,
  segment_description="iGaming Providers — companies that BUILD the technology layer of online gambling...",
  example_domains=["softswiss.com", "pragmaticplay.com", "betconstruct.com", "digitain.com", "evoplay.games"],
  employee_range="21,500",
  skip_exploration=true,
  confirm=true
)
```

Expected:
- Scrape 5 example websites in parallel
- Enrich 5 companies in Apollo (5 credits)
- Extract common labels: industries, keywords, sizes
- Infer segment from website text + Apollo data
- Store filters + segment on project
- Skip exploration phase flag set

### Step 4: Apollo Filter Preview
```
tam_gather(project_id=X, source_type="apollo.companies.api", query="iGaming providers")
→ Filter preview with 20+ keywords from enriched examples
→ Industry tags from Apollo enrichment
→ Size: 21-500
→ Available: N companies
→ Cost estimate: ~X credits
```

### Step 5: Align Email Accounts
```
align_email_accounts(run_id=X, account_filter="pavel mifort")
→ Match accounts with "pavel" in name AND "mifort" in domain
→ Preview: N matched accounts
→ confirm=true → mcp_draft campaign created
```

NOTE: Current `align_email_accounts` does substring match on EITHER name OR email.
User wants AND: "pavel" in name AND "mifort" in domain.
**GAP: Multi-field filter not implemented. Currently OR-based.**

### Step 6: Start Pipeline
```
run_auto_pipeline(run_id=X, confirm=true)
→ Checklist: offer ✓, filters ✓, accounts ✓, KPI: 100 people, 3/company
→ Pipeline runs in background
```

### Step 7: Pipeline Runs
- Phase 1: process existing companies (from tam_gather)
- Phase 2: Apollo pages → scrape → classify → people (parallel)
- Classification prompt includes exclusion: "Casino operators are NOT targets"
- People roles from offer: CTO, VP Engineering, Head of Development

### Step 8: KPI Hit → Auto-Push
- Sequence auto-generated from campaign intelligence
- Auto-pushed to SmartLead as DRAFT
- Email accounts from mcp_draft campaign assigned
- Contacts uploaded
- Telegram notification sent

## Questions to Answer

1. Does `define_targets` CASE 4 work correctly? Are enriched filters better than auto-generated?
2. Does the classification prompt correctly EXCLUDE casino operators (Bet365, 888, etc.)?
3. Are the 8 sub-segments (platform providers, game studios, etc.) reflected in `analysis_segment`?
4. Does `skip_exploration=true` actually skip the exploration phase?
5. Does multi-field account filter work ("pavel" + "mifort")?
6. Are target roles correct for IT outsourcing offer? (CTO, VP Engineering vs VP HR for payroll)
7. How many credits spent? Estimation vs reality?
8. Time spent? Parallelization working?
9. SmartLead campaign has correct contacts with emails?
10. Sequence quality — personalized by segment?

## Implementation Gaps Found

### GAP 1: Multi-field account filter (AND logic)
Current `align_email_accounts` does OR match: "pavel" OR "mifort" matches.
User wants AND: "pavel" in name AND "mifort" in email/domain.
**Fix needed in dispatcher.py align_email_accounts handler.**

### GAP 2: Exclusion criteria from user document
The "Shit List" section of PAVEL_EXAMPLE has explicit exclusion examples (Bet365, 888, etc.).
Currently `define_targets` stores `segment_description` on project but doesn't extract exclusion rules separately.
The classification prompt gets exclusion via `competitor_exclusion` (based on sender_company) but NOT from user-defined exclusions.
**Fix: Extract exclusion criteria from segment_description and inject into classification prompt.**

## Success Criteria
- SmartLead DRAFT campaign created with:
  - Contacts from iGaming providers (NOT casino operators)
  - Roles: CTO, VP Eng, Head of Dev
  - Email accounts matching "pavel" + "mifort"
  - God-level sequence (personalized by sub-segment)
- Credits: estimation matches reality within 20%
- Time: <10 minutes for 100 contacts
- Classification accuracy: >80% true iGaming providers, 0% casino operators
