# Deliryo Search Report — Yandex Saturation Analysis

## Results Summary (2026-02-10)

| Metric | Value |
|---|---|
| Total targets found | **306** |
| Total domains discovered | 17,876 |
| Total domains analyzed (GPT scored) | 7,700 |
| Total search queries executed | 6,388 |
| Search jobs | 14 |
| Runtime | ~8 hours total (multiple runs) |

## Strategy Effectiveness Leaderboard

| Strategy | Queries | Targets | Hit Rate | Notes |
|---|---|---|---|---|
| gpt_round_21 | 79 | +8 | **10.1%** | GPT finds niche terms humans miss |
| gpt_round_2 | 73 | +5 | 6.8% | Early GPT round, lots of fresh territory |
| alternative (VC/PE/hedge) | 16 | +1 | 6.2% | Small but efficient |
| core_combos | 192 | +10 | 5.2% | Industry terms × modifiers — bread and butter |
| gpt_round_26 | 76 | +4 | 5.3% | Later GPT rounds still productive |
| russia_regions | 1,216 | +6 | 0.5% | All 85 federal subjects, low yield per query |
| regulatory | 20 | +3 | 15.0%* | *From first run only, second run 0% (already harvested) |
| english queries | 24 | +1 | 4.2% | International-facing Russian firms |

## Yandex Search Limitations

### 1. Result Saturation
After ~6,000 queries, Yandex returns **>90% duplicate domains**. The search index for Russian wealth management is finite — there are only so many pages indexed for these terms.

### 2. Rate Limiting
- 8 concurrent workers is the sweet spot
- 20 workers → 400+ HTTP 429 errors with 5-second backoffs
- Occasional timeouts even at 8 workers (2-5% of requests)

### 3. Regional Coverage Gaps
- Major cities (Moscow, SPb, Ekaterinburg) are well-indexed
- Smaller regions (<300K population) return mostly generic local businesses
- Many wealth management firms only have Moscow-centric web presence regardless of actual office location

### 4. Content Type Limitations
- Yandex indexes websites well but misses:
  - LinkedIn company profiles (blocked by robots.txt)
  - Professional registry databases (dynamic content)
  - Closed conference attendee lists
  - Industry reports behind paywalls

### 5. Query Diversity Ceiling
- GPT-generated queries hit diminishing returns after ~25 rounds
- 5 consecutive zero-gain rounds triggered auto-stop
- The GPT prompt has been optimized with confirmed target examples but still converges on similar query patterns

## Recommended Next Steps to Reach 1,000 Targets

### Tier 1 — High Impact
1. **Google Search API** — Different index, different ranking = different results for same queries
2. **CBR Registry Scraping** — Central Bank of Russia publishes licensed financial entities at cbr.ru
3. **НАУФОР Member Directory** — Professional association with full member lists
4. **Investfunds.ru Scraping** — Comprehensive fund/management company database

### Tier 2 — Medium Impact
5. **LinkedIn Sales Navigator** — Company search with industry filters
6. **SPARK/Контур** — Russian business registry with OKVED codes for financial services
7. **Conference Attendee Lists** — SPEAR'S Russia, Frank RG, private banking forums

### Tier 3 — Long Tail
8. **Telegram Channel Parsing** — Many Russian wealth managers are active on Telegram
9. **vc.ru / RBC Company Pages** — Tech/business media company profiles
10. **Expand Target Definition** — Include adjacent categories (fintech, robo-advisors, insurance brokers)

## Technical Architecture

Scripts used:
- `scripts/deliryo_turbo_search.py` — Initial batch search (deprecated)
- `scripts/deliryo_smart_search.py` — v1 with 8 strategies (deprecated)
- `scripts/deliryo_smart_search_v2.py` — Current: 12 strategies + GPT rounds, strategy leaderboard

All data stored in PostgreSQL:
- `domains` table: 17,876 unique domains (global)
- `search_results` table: 7,700 scored results for project_id=18
- `search_queries` table: 6,388 queries with status tracking
- `search_jobs` table: Job metadata with strategy_stats in config JSON

### Query Anchors Pattern (Reusable)
For any geography, the approach is:
1. List ALL administrative regions/cities ("query anchors")
2. Multiply × industry terms
3. Track effectiveness per anchor
4. This pattern works for: Russia (85 subjects), UAE (7 emirates), DACH (Länder/Kantone), etc.
