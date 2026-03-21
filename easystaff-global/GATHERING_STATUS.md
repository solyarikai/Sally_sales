# EasyStaff Global — Gathering Status (March 21, 2026)

## Results

| City | Raw companies | Scraped | Targets | Target rate |
|------|--------------|---------|---------|-------------|
| Dubai | 11,677 | 7,513 | 835 | 11% |
| NYC | 2,061 | 1,244 | 22 | 2% |
| LA | 1,507 | 884 | 26 | 3% |
| **TOTAL** | **15,245** | **9,641** | **883** | — |

## All stored in DB
- 15,245 unique domains in `discovered_companies`
- 9,641 with scraped website text
- 883 verified targets with CAPS_LOCKED segments
- 423 contacts for Dubai targets
- All Apollo filters stored as actual arrays (not summaries)
- All GPT prompts + responses stored in `analysis_results.raw_output`

## Blockers

### Apollo rate limiting
After scraping NYC + LA (~3,700 companies), Apollo blocks all subsequent sessions.
Symptoms: login succeeds but page navigation times out. 0 companies extracted.
Need: wait 12-24 hours between cities, or use proxy/different account.

### Remaining cities (not yet scraped)
Miami, Riyadh, London, Singapore, Sydney, Austin, Doha, Jeddah, Berlin, Amsterdam
All failed with "Navigation timeout" — Apollo anti-bot blocking.

## Pipeline infrastructure
- Background gathering works (returns immediately, executes async)
- Phase 1 fixes applied (filters backfilled, 25K duplicates removed, output refs set)
- V6 via negativa prompt with per-city geography adaptation
- Project-scoped SmartLead sync (10x faster)

## Next steps
1. Wait for Apollo cooldown, retry remaining cities one per day
2. Consider Clay TAM export as alternative source (different API, no Puppeteer)
3. Consider Google Maps API for local business discovery
4. Process existing 9,641 scraped companies through full pipeline (contacts, FindyMail)
