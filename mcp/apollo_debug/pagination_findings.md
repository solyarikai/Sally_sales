# Apollo API Pagination — Real Test Results
**Date**: 2026-03-31 18:25 UTC
**Account**: pn3 (user_id 179)

## How Apollo Pagination Works

- Endpoint: `POST /api/v1/mixed_companies/search`
- Auth: `X-Api-Key` header (NOT in JSON body — changed recently, body auth returns 422)
- Params: `page` (1-indexed), `per_page` (max 100)
- Response includes `pagination.total_entries` and `pagination.total_pages`
- **1 credit per API call** (per page fetched)

## Key Finding: Apollo Does NOT Return Full Pages

Apollo reports `total_entries=3,395` but returns only **56-85 companies per page** even with `per_page=100`.
This means Apollo is filtering internally beyond what the search params specify.

**per_page=25 returns 0** — appears broken or account-specific limitation.
**per_page=100 works** — but returns variable 4-90 results per page.

## Test 1: IT Consulting — Miami, FL

```json
{
  "q_organization_keyword_tags": ["information technology & services", "IT consulting", "software development"],
  "organization_locations": ["Miami, Florida, United States"],
  "organization_num_employees_ranges": ["11,200"]
}
```

**Apollo total_entries: 3,395**

| Page | Returned | New Unique | Cumulative Unique | Dupes |
|------|----------|-----------|-------------------|-------|
| 1 | 4 | 4 | 4 | 0 |
| 2 | 9 | 6 | 10 | 3 |
| 3 | 29 | 28 | 38 | 1 |
| 4 | 56 | 52 | 90 | 4 |
| 5 | 69 | 64 | 154 | 5 |
| 6 | 71 | 69 | 223 | 2 |
| 7 | 79 | 76 | 299 | 3 |
| 8 | 85 | 81 | 380 | 4 |
| 9 | 82 | 75 | 455 | 7 |
| 10 | 84 | 80 | 535 | 4 |
| 11 | 85 | 82 | 617 | 3 |

**Result: 617 unique companies from 11 pages (11 credits)**
**Effective rate: ~56 unique/page**

## Test 2: Video Production — London, UK

```json
{
  "q_organization_keyword_tags": ["media production", "video production", "film production", "content creation"],
  "organization_locations": ["London, England, United Kingdom"],
  "organization_num_employees_ranges": ["11,200"]
}
```

**Apollo total_entries: 4,245**

| Page | Returned | New Unique | Cumulative Unique |
|------|----------|-----------|-------------------|
| 1 | 13 | 13 | 13 |
| 2 | 55 | 51 | 64 |
| 3 | 66 | 63 | 127 |
| 4 | 65 | 64 | 191 |
| 5 | 71 | 67 | 258 |
| 6 | 78 | 74 | 332 |
| 7 | 88 | 83 | 415 |
| 8 | 88 | 85 | 500 |
| 9 | 90 | 84 | 584 |
| 10 | 90 | 88 | 672 |
| 11 | 88 | 81 | 753 |

**Result: 753 unique companies from 11 pages (11 credits)**
**Effective rate: ~68 unique/page**

## Revised Estimation: How to Get 1000 Companies

| Metric | Miami IT | London Video |
|--------|----------|--------------|
| Unique per page (avg) | ~56 | ~68 |
| Pages for 1000 companies | ~18 | ~15 |
| Credits for search | 18 | 15 |
| Target rate (observed) | ~23% | ~45% |
| Expected targets from 1000 | ~230 | ~450 |
| Contacts (3/company) | ~690 | ~1350 |

## Revised Cost to Get 100 Contacts Per Segment

| Step | Miami IT | London Video |
|------|----------|--------------|
| Companies needed (at target rate) | 34 / 23% = ~150 | 34 / 45% = ~76 |
| Pages needed | ~3 pages | ~2 pages |
| Search credits | 3 | 2 |
| Exploration credits | 5 | 5 |
| People email credits | 100 | 100 |
| **Total credits** | **108** | **107** |
| **Total cost** | **~$1.08** | **~$1.07** |

## Pagination Behavior Summary

1. `per_page=100` is the ONLY working value (25 returns 0)
2. Apollo returns 50-90 per page, NOT 100 — plan for ~60 effective
3. ~5% cross-page duplicates — client-side dedup is essential
4. Page 1 returns very few results (4-13) — pages 3+ stabilize at 70-90
5. `total_entries` is a rough estimate, NOT the actual accessible count
6. To get N unique companies: plan for N/60 pages
