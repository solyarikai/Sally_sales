# Gathering Reference — Parameters, Costs, Defaults

Everything a user (or AI agent) needs to know before starting a gathering pipeline.

---

## Required Parameters (MUST be provided by user)

| # | Parameter | Example | Why required |
|---|-----------|---------|-------------|
| 1 | **Industry / Keywords** | "IT consulting", "SaaS", "fintech" | Without this, Apollo returns random companies |
| 2 | **Location** | "United States", "Germany", "Dubai" | Without this, searches globally — too broad |
| 3 | **Company size** (employee range) | "50-200" → `["51,200"]` | A 5-person startup ≠ 500-person enterprise. This is the #1 quality filter |
| 4 | **Max pages** | 4 | Controls credit spend. Each page = 25 companies = 1 Apollo credit |

If ANY of these is missing, the system rejects the request and asks the user to specify.

## Optional Parameters (AI suggests when relevant)

| Parameter | When to suggest | Example |
|-----------|----------------|---------|
| Funding stage | User mentions "startups" or "growth stage" | `["seed", "series_a", "series_b"]` |
| Revenue range | User targets enterprise or mid-market | min: 1000000, max: 50000000 |
| Technologies | User wants companies using specific tools | `["salesforce", "hubspot"]` |
| Job postings | User wants companies actively hiring | `["engineering manager", "CTO"]` |

## Defaults

| Setting | Default | Why |
|---------|---------|-----|
| **per_page** | 25 | Apollo standard. Works reliably (lower values return empty) |
| **max_pages** | NONE — must be specified | Prevents accidental credit spend |
| **source_type** | `apollo.companies.api` | Most common. User can change to manual/CSV/sheets |

## Cost Estimates

Show this to the user BEFORE starting:

### Apollo API
| Pages | Companies | Credits | Cost |
|-------|-----------|---------|------|
| 1 | ~25 | 1 | $0 (included in plan) |
| 2 | ~50 | 2 | $0 |
| 4 | ~100 | 4 | $0 |
| 10 | ~250 | 10 | $0 |
| 20 | ~500 | 20 | $0 |
| 50 | ~1,250 | 50 | $0 |
| 100 | ~2,500 | 100 | $0 |

Apollo credits are included in the plan (not per-credit billing). But they're limited — don't waste them on unfiltered searches.

### Website Scraping
- **$0** — uses httpx (plain HTTP), no browser, no proxy credits
- ~0.3 seconds per website
- 100 companies ≈ 30 seconds

### AI Analysis (GPT-4o-mini)
- **~$0.003 per company** ($0.15/1M input tokens)
- 100 companies ≈ $0.30
- 1000 companies ≈ $3.00

### FindyMail Verification
- **$0.01 per email**
- ~3 contacts per target company
- 50 targets × 3 contacts = 150 emails ≈ **$1.50**

### GOD_SEQUENCE Generation
- **~$0.08** per sequence (Gemini 2.5 Pro)

### Total Pipeline Cost (100 companies example)
```
Apollo search:  4 credits (free with plan)
Scraping:       $0
AI analysis:    $0.30
FindyMail:      $1.50 (only for targets, ~30% = 30 companies × 3 = 90 emails)
Sequence:       $0.08
─────────────────────
Total:          ~$1.88 for 100 companies → ~30 targets → ~90 verified emails → 1 campaign
```

## Pre-Gathering Checklist

The system (AI agent or bot) must confirm ALL of these before calling `tam_gather`:

```
✓ Account exists (setup_account)
✓ Apollo key connected (configure_integration)
✓ Project created (create_project)
✓ SmartLead key connected — or user chose to skip
✓ Existing campaigns imported as blacklist — or user has none
✓ User confirmed:
  - Keywords/industry
  - Location/country
  - Company size (employee range)
  - Max pages (credit budget)
✓ Cost estimate shown and accepted
```

## What the User Sees Before Start

```
Ready to gather for 'EasyStaff Global - US IT':

  Search: IT consulting, software development
  Location: United States
  Size: 50-200 employees
  Pages: 4 (= ~100 companies, 4 Apollo credits)

  Estimated pipeline cost:
  • Apollo: 4 credits
  • Scraping: free
  • AI analysis: ~$0.30
  • FindyMail: ~$0.90 (if 30% targets)
  • Total: ~$1.20

  Blacklist: 4,200 contacts from 3 SmartLead campaigns

  → Pipeline UI: http://46.62.210.24:3000/pipeline/{runId}

  Start?
```

## After Gathering Starts

Each phase reports progress:

```
Phase 1 — Gather: 87 companies from Apollo (4 pages, 4 credits)
Phase 2 — Blacklist: 82 passed, 5 already in your campaigns
Phase 3 — Pre-filter: 78 passed (4 junk domains removed)
Phase 4 — Scrape: 72/78 websites scraped (6 errors)
Phase 5 — Analyze: 24 targets found (31% target rate, 0.82 avg confidence)

★ CHECKPOINT 2 — Review 24 targets:
  → http://46.62.210.24:3000/pipeline/{runId}

  Top targets:
  • clearscale.com — Clearscale (14 emp, San Francisco) — 92% confidence
  • tekstream.com — TekStream Solutions (6 emp, Atlanta) — 88% confidence
  • ...

  Approve targets to proceed to email verification?
```

## Source Types Available

| Source | What it does | Cost | When to use |
|--------|-------------|------|-------------|
| `apollo.companies.api` | Search Apollo by filters | Credits | Primary source for company discovery |
| `apollo.companies.emulator` | Scrape Apollo UI via Puppeteer | Free | When saving credits (slower) |
| `manual.companies.manual` | Provide domain list directly | Free | When you already have a list |
| `csv.companies.manual` | Upload CSV file | Free | Importing from another tool |
| `google_sheets.companies.manual` | Import from Google Sheet | Free | Importing shared lists |
| `clay.companies.emulator` | Clay TAM export | ~$0.01/co | Alternative to Apollo |
