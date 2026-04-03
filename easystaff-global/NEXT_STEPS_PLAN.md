# EasyStaff Global — Next Steps Plan (March 21, 2026)

## Current State

### What we have in DB
- **331 verified targets** (Dubai 283, NYC 22, LA 26) — Opus-reviewed, false positives removed
- **8,321 new companies** from 6 cities via API (Miami 762, Riyadh 1079, London 2303, Singapore 1240, Sydney 1778, Austin 1159) — NOT YET ANALYZED
- **280 contacts** for Dubai targets (decision-makers)
- All filters, keywords, prompts stored in DB

### Credits
- **407 credits spent** today (API enrichment)
- **9,276 credits remaining** until Mar 22 reset
- 1 credit = 1 API call = up to 100 companies (per_page=100)

### Proven filter effectiveness (from 331 verified targets)
| Apollo tag on our targets | % of targets | Use as search filter? |
|---|---|---|
| information technology & services | 69% | YES — primary |
| marketing & advertising | 54% | YES — primary |
| digital marketing | 40% | YES — primary |
| consulting | 40% | YES — secondary |
| web development | 36% | YES — secondary |
| content creation | 35% | YES — secondary |
| branding | 29% | YES — secondary |
| software development | 28% | MAYBE — high noise |
| video production | 22% | MAYBE |

## Step 1: Process the 8,321 companies we already have (0 credits)

**No new Apollo credits needed.** Website scraping + GPT analysis is free/cheap.

1. Scrape websites (httpx + Apify proxy) — ~30 min
2. Analyze with V6 via negativa prompt (GPT-4o-mini, adapted per city) — ~20 min
3. Opus self-review — find false positives
4. Report: how many targets per city, per keyword, target rate per keyword

**Expected: 8,321 × ~6% target rate = ~500 new targets.**

This will also tell us EXACTLY which keywords produce targets per city (since `_keyword` is tagged on every company).

## Step 2: Decide next credit spend based on Step 1 results

After Step 1, we'll know:
- Which keywords have >5% target rate per city (worth paginating)
- Which keywords have 0% target rate (stop using)
- How many more pages exist for top keywords

**Decision point:** Should we spend 50-70 more credits per remaining city to get pages 2-5 of top keywords? Or are the page-1 results enough?

## Step 3: Remaining 4 cities (Doha, Jeddah, Berlin, Amsterdam)

Budget: ~30 credits per city = 120 credits total.
Same keyword set, page 1 only, per_page=100.
Then scrape + analyze + review.

## Step 4: After targets verified — find contacts

For verified targets from all cities:
- Extract contacts from Apollo source_data (already have people for some)
- For targets without contacts: use Apollo People API to find decision-makers

## Budget Summary

| Activity | Credits | Status |
|----------|---------|--------|
| Already spent today | 407 | Done |
| Step 1 (process existing) | 0 | Next |
| Step 3 (4 remaining cities, page 1) | ~120 | After Step 1 |
| Step 2 (paginate top keywords) | ~200-400 | After analysis |
| **Total projected** | **~730-930** | Of 9,276 remaining |

## What NOT to do
- ~~Puppeteer scraping~~ — Cloudflare blocks, account gets locked
- ~~Broad keywords (e-commerce, data analytics)~~ — 1-2% target rate, waste of credits
- ~~per_page < 100~~ — same credit cost, fewer results
- ~~Multiple cities in parallel via Puppeteer~~ — impossible with 1 account
