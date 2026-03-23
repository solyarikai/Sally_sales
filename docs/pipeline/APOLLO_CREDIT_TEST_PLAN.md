# Apollo Credit Test — Measuring Actual Credit Consumption

> **STATUS: TEST EXECUTED — WAITING FOR OPERATOR TO CHECK APOLLO DASHBOARD**

## Purpose

Apollo docs don't disclose how many credits each endpoint costs. We need to measure empirically.

## What Was Done

**ONE single API call** was made. Details below.

---

## Test Call #1: `organization search`

**Timestamp:** `2026-03-21T18:33:53Z` (UTC) / `20:33:53` (Dubai/UTC+2)

**Endpoint:** `POST https://api.apollo.io/api/v1/mixed_companies/search`

**API Key:** `9yIx...WVqA` (danila@getsally.io account)

**Request body (exact):**
```json
{
  "organization_locations": ["Riyadh, SA"],
  "organization_num_employees_ranges": ["11,50"],
  "per_page": 25,
  "page": 1
}
```

**Filters applied:**
- Location: Riyadh, Saudi Arabia
- Employee count: 11-50
- Page size: 25
- Page: 1

**Response summary:**
- `total_entries`: 7,409 (companies matching filter in Apollo DB)
- `per_page`: 25 (requested)
- `results returned`: 15 (Apollo returned fewer than requested — possibly data quality)
- `page`: 1

**15 companies returned:**

| # | Company | Domain | City |
|---|---------|--------|------|
| 1 | High Links Contracting | highlinksgroup.com | Riyadh |
| 2 | MarsDevs | marsdevs.com | Riyadh |
| 3 | Sandsoft | sandsoft.com | Riyadh |
| 4 | Merkai | merkai.sa | Riyadh |
| 5 | fanZ | fanzapp.io | Riyadh |
| 6 | Basserah | basserah.com | Riyadh |
| 7 | O100 | o-100.com | Riyadh |
| 8 | Kingdom Brokerage For Insurance | kbrokerage.com | Riyadh |
| 9 | NineTenths | 9tenthsco.com | Riyadh |
| 10 | Upshifters | upshifters.net | Riyadh |
| 11 | Etegah | etegah.com | Riyadh |
| 12 | ACECO | aceco.sa | Riyadh |
| 13 | Terra Drone Arabia | terra-drone.com.sa | Riyadh |
| 14 | Rafad | rafad.sa | Riyadh |
| 15 | Amwal Tech | amwal.tech | Riyadh |

**Data returned per company:** name, domain, website_url, linkedin_url, phone, address, city, state, country, revenue, employee count, founding year, industry codes (SIC/NAICS), social links.

---

## What To Check in Apollo Dashboard

1. Go to [Apollo Settings → Plan & Billing → Credits](https://app.apollo.io/settings/plans-billing)
2. Note the **current credit balance** RIGHT NOW
3. Compare to what it was before this test

**We also made ~4 earlier calls today** (testing `search_people` and `search_organizations`) between 18:20-18:34 UTC:
- 3× `search_people` (should be FREE per docs) — returned obfuscated data
- 1× `search_organizations` with `per_page: 2` — returned 2 full companies (NYC)
- 1× `search_organizations` with `per_page: 1` — returned 1 company (Dubai)
- 1× `search_organizations` with `per_page: 25` — returned 15 companies (Riyadh) ← this test

**Total API calls today:** 6 calls (3 free search_people + 3 org search)

## ANSWER — Official Apollo API Credit Pricing (From Dashboard)

**Found in Apollo dashboard → About credits → API section:**

| Endpoint | Credits | Notes |
|----------|---------|-------|
| `/mixed_people/api_search` | **0 (FREE)** | Returns partial profile. Need `/people/match` for full. Max 100/page |
| `/mixed_companies/search` | **1 credit per PAGE returned** | Max 100 results/page. So 1 credit = up to 100 companies |
| `/people/match` | **1 credit/email + 1 credit/firmographic + 5 credits/phone** | Per NET-NEW result |
| `/people/bulk_match` | Same as above | Batched version |
| `/organizations/enrich` | **1 credit per result** | Single company by domain |
| `/organizations/bulk_enrich` | **1 credit per company** | Max 10/page |
| `/organizations/{id}/job_postings` | **1 credit per result** | Max 10,000/page |

### Key insight: `/mixed_companies/search` = 1 CREDIT PER PAGE, NOT per result!

That means:
- `per_page=100` (max) → 1 credit for 100 companies
- `per_page=10` → 1 credit for 10 companies (WASTEFUL)
- **Always use `per_page=100` to maximize value**

### Revised cost for 1M companies via API:

| Volume | Pages (at 100/page) | Credits | On Professional ($79/mo, 10K credits) |
|--------|-------------------|---------|--------------------------------------|
| 10,000 | 100 | 100 | 1 month ($79) — barely uses any credits |
| 100,000 | 1,000 | 1,000 | 1 month ($79) |
| 500,000 | 5,000 | 5,000 | 1 month ($79) |
| 1,000,000 | 10,000 | 10,000 | 1 month ($79) |

**1 MILLION COMPANIES = 10,000 CREDITS = $79 ON PROFESSIONAL PLAN.**

This changes everything. At 100 companies per credit, the API is absurdly cheap for company discovery.

### Our test calls cost:

Today's 4× `search_organizations` calls = **4 credits** (1 per page, regardless of per_page setting).
Today's 3× `search_people` calls = **0 credits**.

Total test cost: **4 credits** out of 10,182 remaining.

### CONFIRMED BY DASHBOARD (20:39 UTC+2):

Enrichment usage went from **8,373 → 8,375** after 2 `search_organizations` calls:
1. Singapore, per_page=10, returned 10 → **1 credit**
2. Miami, per_page=100, returned 86 → **1 credit**

**RESULT: 1 credit per API CALL, regardless of per_page or results returned.**

`per_page=100` is 10× more efficient than `per_page=10`. Always use max.

**Final math:**
- 1 credit = 1 page = up to 100 companies
- 10,000 credits = 1,000,000 companies
- Professional plan ($79/mo) = 10,000 credits
- **1M companies = $79**

---

## Baseline Before Test (Screenshot 2026-03-21 ~20:34 UTC+2)

**Billing period:** Feb 21, 2026 – Mar 22, 2026

**Total credits:** 29,873 used of 40,055 credits/mo → **10,182 remaining**

**Breakdown:**
| Category | Credits used |
|----------|-------------|
| Email usage | 17,764 |
| Mobile usage | 3,688 |
| Enrichment usage | 8,373 |
| AI usage | 48 |
| Dialer | 0 |
| **Total** | **29,873** |

**By team member:**
| Member | Total | Emails | Mobile | Enrichment | Power-ups |
|--------|-------|--------|--------|------------|-----------|
| Danila Sokolov | 21,500 | 17,764 | 3,688 | 0 | 48 |
| Others (API) | 8,373 | 0 | 0 | 8,373 | 0 |

**Note:** "Others" = 8,373 enrichment credits — this is ALL API usage this billing cycle (including the incident from earlier + today's test calls). Our test calls today (3× search_people + 3× search_organizations) are somewhere in that 8,373. The earlier incident burned ~25 credits on runs #64-68.

**Also note:** "Apollo account blocked" tab visible in browser — account may have been temporarily blocked earlier this cycle, possibly from the Puppeteer scraping.

---

## Next Steps After Checking Credits

Once we know the credit cost per call, update:
1. This document with findings
2. `COST_ANALYSIS_1M_COMPANIES.md` with corrected math
3. `APOLLO_CREDITS_WARNING.md` with accurate per-endpoint costs
4. `CLAUDE.md` pipeline section if needed

---

## Previous Incident Context

On March 21 earlier, ~25 credits were burned on 5 API calls returning ~75 companies (runs #64-68). That suggests roughly **5 credits per call** or **1 credit per 3 results** — but those were larger page sizes. This test should clarify.
