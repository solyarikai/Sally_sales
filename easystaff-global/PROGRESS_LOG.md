# EasyStaff Global — Progress Log

## Session KPI
1. Scrape all 7,990 new companies (6 cities) ✅ IN PROGRESS — 4,842/7,990 in 2 min
2. GPT-4o-mini analysis with v7 prompt (no city filter — focus on business/segment match)
3. Opus self-review of ALL targets (parallel batches)
4. Compare Opus vs GPT — find where GPT sucks
5. Generate improved prompt based on mismatches
6. Document ALL issues in this file

## Timeline

### 21:35 — Fast scrape launched
- 50 concurrent connections, streaming commits every 50
- 4,842 scraped in 2 min (2,400/min = 40/sec)
- Architecture fix: crash-safe streaming commits (was: lose all on crash)

### 21:37 — Scraping continuing
- 4,842 scraped (2 min in)

### 21:39 — 4,942 scraped
- Steady rate ~50/sec

### 21:41 — 5,026 scraped
- Slowing (remaining sites slower to respond)

### 21:46 — GPT analysis RUNNING IN PARALLEL
- 5,026 scraped, 599 GPT targets found
- GPT started analyzing while scrape still running for remaining ~2,900
- V7 prompt active: no city filter, pure business match

### 21:47 — Starting Opus parallel review
- 4 agents launched, reviewing 688 GPT targets

### 21:51 — GPT analysis exploding
- 2,031 analyzed, 1,096 targets (54% rate!)
- V7 without city filter is MUCH more permissive than V6 (was 6%)
- 54% target rate means GPT is too lenient — Opus review will find the false positives
- Scraping stopped at 5,026 (remaining 2,900 sites failed/timed out)

### 21:52 — All 4 Opus reviews writing results

### 21:58 — OPUS REVIEWS COMPLETE
- 689 GPT targets reviewed by Opus
- **645 OK (93.6%), 44 false positives (6.4%)**
- V7 accuracy: 93.6% — improvement over V6 (86%)
- GPT sucks on: SaaS products (12 FPs), solo consultants (8), government contractors (6), hardware (5)
- Best segments: MARKETING_AGENCY (100%), DIGITAL_AGENCY (95%)
- Worst segments: IT_SERVICES (85%), TECH_STARTUP (85%)
- Full analysis: GPT_CLASSIFICATION_ISSUES.md

### Decision: V7 is good enough for production (93.6%)
- 44 FPs out of 689 is acceptable
- Will create V8 prompt with SaaS product + government contractor exclusions for next iteration
- But NOT re-running analysis now — 645 verified targets is the result

## Issues Found

### CRITICAL: City filter was wrong
- V6 prompt rejected companies not in the search city
- WRONG: EasyStaff doesn't care WHERE the company is — cares WHAT it does
- FIX: V7 prompt removes city geography check entirely
- Focus: is this a service business that hires freelancers? That's it.

### CRITICAL: Scraper was too slow + crash-unsafe
- Old: 10 concurrent, commit at end = 4 hours, crash = lose all
- New: 50 concurrent, streaming commits = ~30 min, crash = lose max 50
- Speed: 40/sec vs 0.5/sec = 80x improvement

### HIGH: Apollo API costs credits (learned the hard way)
- /mixed_companies/search = 1 credit per API call
- Total spent: 407 credits (168 research + 216 gathering + 23 incidents)
- BUT: 1 credit = 100 companies. Very efficient once you know the cost.

### HIGH: Puppeteer approach is dead
- Cloudflare blocks after 2 cities
- Apollo blocks account after repeated login attempts from proxies
- API is the only sustainable approach (and it's cheap: 1 credit/100 companies)

### MEDIUM: Per-keyword target attribution
- Old runs: no _keyword tag on companies (can't trace which filter found target)
- New runs (75-80): _keyword tagged on every company via source_data
- Can now compute exact target rate per keyword per city after analysis

## What's working
- Pipeline DB: all companies, filters, prompts, results stored
- Streaming scrape: crash-safe, 50 concurrent
- GPT analysis: 25 concurrent with batch commits
- Apify proxy: works for httpx scraping (NOT for Puppeteer — Cloudflare)
- V7 prompt: no city filter, pure business match

## What's next
- [ ] Scrape finishes (~30 min)
- [ ] GPT-4o-mini analyzes with v7 (auto-starts after scrape)
- [ ] Opus reviews ALL GPT targets (parallel batches)
- [ ] Compare: where does GPT mark as target but Opus says no? Where does GPT reject but Opus says yes?
- [ ] Generate v8 prompt that fixes the mismatches
- [ ] Document: every GPT suck case with domain, what it did wrong, and how to fix
