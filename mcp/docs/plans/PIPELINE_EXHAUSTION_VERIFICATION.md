# Pipeline Exhaustion Verification Plan

## Requirements
1. At least 20 keywords generated before pipeline starts
2. Keywords regenerated when 20 consecutive pages yield 0 new companies
3. Pipeline stops after 5 regeneration attempts with 20 empty pages each
4. Each strategy gets its own regeneration budget

## Constants
- `EXHAUSTION_THRESHOLD = 20` — consecutive empty pages before regeneration
- `MAX_KEYWORD_REGENERATIONS = 5` — max regeneration attempts per strategy
- `MAX_PHASE2_PAGES = 200` — global safety cap (productive pages only)

## All Bugs Found & Fixed (3 verification passes)

### Pass 1
| # | Severity | Issue | Fix |
|---|----------|-------|-----|
| 1 | Critical | `total_pages_all` blocked regeneration | Only productive pages count toward cap |
| 2 | High | `keyword_regenerations` carried across strategies | Reset per strategy |

### Pass 2
| # | Severity | Issue | Fix |
|---|----------|-------|-----|
| 3 | High | Regeneration repeated previously tried keywords | `all_tried_keywords` set tracks globally |
| 4 | Medium | `UserServiceContext` got string user_id | `int()` with fallback |
| 5 | Medium | No keyword count warning in preview | Warning if <20 keywords |
| 6 | Medium | Strategy message truncated to 5 keywords | Show all keywords |

### Pass 3
| # | Severity | Issue | Fix |
|---|----------|-------|-----|
| 7 | High | After regen, industry_tag_ids still set on strategy_filters. Apollo applies industry+keywords as AND, narrowing results instead of broadening | `strategy_filters.pop("organization_industry_tag_ids")` after regeneration |
| 8 | Low | `continue` after regen skipped `_persist_progress()` | Added `await self._persist_progress()` before continue |

## Verification Checklist
- [x] filter_mapper GPT prompt asks for 20-30 keywords
- [x] Unverified keywords added to reach 20 minimum
- [x] EXHAUSTION_THRESHOLD = 20
- [x] keyword_regenerations resets per strategy
- [x] Exhaustion pages don't count toward MAX_PHASE2_PAGES
- [x] all_tried_keywords tracks everything across all regenerations
- [x] GPT regeneration prompt shows ALL previously tried keywords
- [x] UserServiceContext gets int user_id
- [x] Strategy message shows all keywords
- [x] Warning if <20 keywords
- [x] Industry tags dropped after regeneration (keywords-only search)
- [x] Progress persisted after regeneration event

## Worst Case Apollo Credits
- Per strategy: 5 regenerations x 20 empty pages = 100 wasted pages
- Two strategies = 200 wasted pages max
- Plus MAX_PHASE2_PAGES = 200 productive pages
- **Absolute worst: ~400 pages = ~400 credits ($4.00)**

## Execution Flow (verified line by line)
```
1. _feed_apollo_pages() called with filters
2. _build_strategies() → [primary, backlog] (or just [primary])
3. For each strategy:
   a. keyword_regenerations = 0, consecutive_empty = 0
   b. Track initial keywords in all_tried_keywords
   c. Fetch page → _ingest_page_results() → new_count
   d. If new_count == 0: consecutive_empty++
   e. If consecutive_empty >= 20:
      - keyword_regenerations++
      - If >= 5: break (switch strategy)
      - Else: _regenerate_keywords(filters, all_tried_keywords)
        - GPT generates 20-30 new keywords excluding ALL tried
        - Drop industry_tag_ids from filters (keywords-only after regen)
        - Reset consecutive_empty, page = 1
        - Persist progress, continue
   f. If new_count > 0: consecutive_empty = 0, productive_pages++
   g. page++
4. Pipeline stops when: KPI met OR all strategies exhausted OR productive_pages >= 200
```
