# Plan: EasyStaff Global — Warm Reply Analysis & Strategy Reverse-Engineering

## Context

EasyStaff Global has 170 campaigns across 28+ cities with 68,192 SmartLead leads. Analyze ALL warm conversations, enrich with Apollo company data, and reverse-engineer the growth strategy.

## KPIs

1. **`WARM_CONVERSATIONS.md`** — Every positive reply with full thread + Apollo company data
2. **`GROWTH_STRATEGY.md` extended** — Data-driven section: which industries/keywords/sizes convert, targeting adjustments
3. **100% warm reply coverage** — All 183 warm replies (61 meeting_request + 61 interested + 61 question) documented
4. **Apollo enrichment** — 141 unique company domains enriched (141/200 credits used)

## ANALYSIS RULES

- **EXCLUDE conference campaigns** (Sigma, TES, IGB, ICE) from analysis — conferences always convert better, it's obvious and not actionable for cold outreach strategy
- **INCLUDE qualified leads from shared Google Sheet** ("Easystaff Global <> Sally", Leads tab, column T = "Засчитываем")

## HARD CONSTRAINTS

- **APOLLO CREDIT LIMIT: 200 CREDITS MAX. NON-NEGOTIABLE.**
- Prioritize: meeting_request (warmest) > interested > question
- Check `discovered_companies.apollo_org_data` FIRST — reuse already-enriched data (no extra credits)
- If 200 credits exhausted → stop, document which are missing

## Status: Apollo Enrichment COMPLETE

- **141 domains enriched** using 141/200 Apollo credits
- **129 domains found** with full company data (industry, keywords, employees, revenue)
- **12 domains not found** in Apollo (small/new companies)
- **0 errors**
- Results saved to `/tmp/apollo_enrichment_results.json` on Hetzner

## Data Collected

| Metric | Count |
|--------|-------|
| Warm replies (total) | 183 |
| — meeting_request | 61 |
| — interested | 61 |
| — question | 61 |
| Unique company domains | 141 |
| Apollo enriched (found) | 129 |
| Apollo not found | 12 |
| Credits used | 141/200 |

## Remaining Steps

### Step 1: Build WARM_CONVERSATIONS.md ← NEXT
Combine:
- 183 warm replies (from `processed_replies` table)
- Thread messages (from `thread_messages` table)
- Apollo company data (from `/tmp/apollo_enrichment_results.json`)

Format each conversation:
```
### {Lead Name} — {Company} ({Domain})
Category: {meeting_request/interested/question} | Campaign: {name} | Date: {date}
Apollo: {industry} | {keywords} | {employees} | {revenue} | {city}, {country}

Thread:
→ [Out] {our message}
← [In] {their reply}
```

### Step 2: Analyze patterns
From Apollo data across 129 enriched companies, compute:
- **Industry distribution** — which industries have the most warm replies?
- **Keyword frequency** — which Apollo keywords correlate with positive responses?
- **Company size sweet spot** — employee count distribution of converters
- **Revenue brackets** — do higher-revenue companies engage more?
- **Geographic hotspots** — which cities/regions produce the most warm replies?
- **Campaign ranking** — which campaigns have the highest warm reply rate?

### Step 3: Extend GROWTH_STRATEGY.md
New section: `## Warm Reply Reverse-Engineering (2026-03-24)`
- Quantified insights from the analysis (actual numbers, not vague)
- Recommended targeting adjustments based on what converts
- New keyword/industry combinations to test
- Geographic expansion priorities based on reply patterns

## Output Files

| File | Content |
|------|---------|
| `easystaff-global/WARM_REPLY_ANALYSIS_PLAN.md` | This plan (you're reading it) |
| `easystaff-global/WARM_CONVERSATIONS.md` | All 183 warm conversations + Apollo data |
| `easystaff-global/GROWTH_STRATEGY.md` | Extended with reverse-engineered insights |

## Verification Checklist

- [ ] Warm reply count in WARM_CONVERSATIONS.md = 183 (matches DB)
- [ ] Apollo data present for 129 domains (12 marked "not found")
- [ ] Credit spend = 141 ≤ 200 (verified)
- [ ] GROWTH_STRATEGY.md has quantified insights with actual numbers
- [ ] All 170 campaigns checked (including new Petr ES * campaigns launched 2026-03-22)

## Technical Details

### Existing System Components Used (no reinvention)
- `GET /api/replies/?project_id=9` — warm reply listing
- `thread_messages` table — cached conversation history
- `ApolloService.enrich_organization(domain)` — company lookup (1 credit/domain)
- `scripts/enrich_warm_leads.py` — enrichment script with 200 credit hard cap

### Project: easystaff global (ID: 9)
- 170 campaigns in `campaign_filters`
- GetSales senders: Marina Mikhaylova, Arina Kozlova
- SmartLead campaigns: EasyStaff *, Petr ES *, UAE-Pakistan *, AU-Philippines *
